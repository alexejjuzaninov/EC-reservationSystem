"""Souběžný zápis CONFIRMED, který PostgreSQL vyřeší deadlockem místo porušení constraintu.

EXCLUDE constraint nejdřív zapíše vlastní řádek a pak hledá konflikty; dvě transakce, které
zapisují současně, mohou čekat jedna na druhou. PostgreSQL jednu z nich ukončí chybou
DeadlockDetected. Volající musí i v tom případě dostat AllocationConflict (OVERLAP), ne obecnou
chybu databáze. Test deadlock vyvolá deterministicky:

  T2 (ručně, bez COMMIT): B = CONFIRMED
  T1 (Reservation Store): A = CONFIRMED  → A se překrývá s B → T1 čeká na T2
  T2:                     C = CONFIRMED  → C se překrývá s A → T2 čeká na T1 → deadlock
T1 čeká déle, takže deadlock odhalí a ukončí T1 (T2 má deadlock_timeout prodloužený).
"""
import threading
import time

from sqlalchemy import text

from reservations.domain import AllocationConflict, Reservation, State
from reservations.store import SqlReservationRepository
from tests.conftest import at


def draft(repo, user, start, end):
    return repo.add(Reservation(None, user, "AC-1", start, end, at("08:00")))


def wait_until_blocked(engine, outcome, timeout=5.0):
    deadline = time.monotonic() + timeout
    # AUTOCOMMIT: PostgreSQL drží pg_stat_activity v rámci jedné transakce jako snímek,
    # opakovaný dotaz v téže transakci by čekání T1 nikdy neuviděl.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        while time.monotonic() < deadline:
            waiting = conn.execute(text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock'"
            )).scalar()
            if waiting:
                return
            time.sleep(0.05)
        activity = conn.execute(text(
            "SELECT pid, state, wait_event_type, wait_event, left(query, 70) FROM pg_stat_activity "
            "WHERE datname = current_database()"
        )).all()
    raise AssertionError(f"T1 nezačala čekat na zámek; T1 skončila: {outcome.get('result')!r}; {activity}")


def test_deadlock_between_concurrent_confirmations_is_reported_as_overlap(system, engine):
    repo = SqlReservationRepository(system.sessions)
    a = draft(repo, "alice", at("10:00"), at("12:00"))
    b = draft(repo, "bob", at("09:00"), at("10:30"))    # překrývá A, ne C
    c = draft(repo, "admin", at("11:00"), at("12:00"))  # překrývá A, ne B

    outcome = {}

    def t1():
        a.state = State.CONFIRMED
        try:
            repo.save(a, expected=State.DRAFT)
            outcome["result"] = "saved"
        except Exception as exc:  # noqa: BLE001 — test zaznamená jakoukoli chybu
            outcome["result"] = exc

    t2 = engine.connect()
    worker = threading.Thread(target=t1)
    try:
        tx = t2.begin()
        t2.execute(text("SET LOCAL deadlock_timeout = '10s'"))
        t2.execute(text("UPDATE reservations SET state = 'CONFIRMED' WHERE id = :id"), {"id": b.id})
        worker.start()
        wait_until_blocked(engine, outcome)  # T1 čeká na T2 kvůli B
        t2.execute(text("UPDATE reservations SET state = 'CONFIRMED' WHERE id = :id"), {"id": c.id})
        tx.commit()  # sem se dojde, až PostgreSQL ukončí T1 deadlockem
    finally:
        t2.close()  # i při chybě: otevřená transakce by držela zámky a zablokovala další testy
        worker.join(timeout=15)
    assert not worker.is_alive(), "T1 se nedokončila"

    result = outcome["result"]
    assert isinstance(result, AllocationConflict), repr(result)
    assert result.code == "OVERLAP" and sorted(result.related) == sorted([b.id, c.id])
    assert repo.get(a.id).state == State.DRAFT
