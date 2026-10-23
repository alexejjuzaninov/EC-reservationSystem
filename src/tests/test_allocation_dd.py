"""C05: unit a component testy odvozené z Detailed Design jednotky „přidělení stanice“ (po C03).

Odpovídají testům tests/test_allocation.py pro aplikaci C02; tam, kde se návrh v C03 změnil
(zámek → databáze, fronta e-mailů → odeslání po COMMIT), ověřují nové rozhodnutí. Pokrytí
mají jinde: neočekávaná chyba Notifieru (test_notifications.py), souběh (test_op03_concurrent_*,
test_concurrency.py), deadlock (test_deadlock.py).
"""
import threading
import time
from datetime import datetime, timezone

import pytest

from reservations.domain import (
    AllocationConflict,
    AllocationDecision,
    AllocationPolicy,
    ChargingStation,
    Reservation,
    State,
)
from reservations.store import SqlReservationRepository
from tests.conftest import DEMO_NOW, at

UTC = timezone.utc
AC = ChargingStation("AC-1", "AC 22 kW", 22, "P1")
AC_OFF = ChargingStation("AC-2", "AC 22 kW", 22, "P2", active=False)


def res(rid, user, station, start, end, state=State.CONFIRMED):
    return Reservation(rid, user, station, start, end, DEMO_NOW, state)


# ---- AllocationPolicy.check(): kontrakt, větve, hranice (unit, bez databáze) ---------

policy = AllocationPolicy()
candidate = res(9, "alice", "AC-1", at("10:00"), at("11:00"), State.DRAFT)


def test_free_slot_is_allowed_and_inputs_are_not_changed():
    others = [res(1, "bob", "AC-1", at("12:00"), at("13:00"))]
    assert policy.check(candidate, AC, others) == AllocationDecision.allow()
    assert candidate.state == State.DRAFT and others[0].state == State.CONFIRMED


def test_adjacent_interval_is_not_an_overlap():  # BR-01 [start, end)
    others = [res(1, "bob", "AC-1", at("09:00"), at("10:00")), res(2, "bob", "AC-1", at("11:00"), at("12:00"))]
    assert policy.check(candidate, AC, others).allowed


def test_overlap_returns_code_and_all_conflicting_ids():  # BR-02
    others = [res(1, "bob", "AC-1", at("09:30"), at("10:30")), res(2, "bob", "AC-1", at("10:45"), at("11:15"))]
    assert policy.check(candidate, AC, others) == AllocationDecision.deny("OVERLAP", [1, 2])


def test_only_confirmed_reservations_block():
    others = [res(1, "bob", "AC-1", at("10:00"), at("11:00"), s) for s in
              (State.DRAFT, State.PENDING_APPROVAL, State.CANCELLED, State.REJECTED, State.EXPIRED)]
    assert policy.check(candidate, AC, others).allowed


def test_daily_limit_uses_utc_date_of_start():  # BR-04
    late = res(8, "alice", "AC-1", datetime(2026, 10, 11, 23, 30, tzinfo=UTC),
               datetime(2026, 10, 12, 0, 30, tzinfo=UTC), State.DRAFT)
    early_next_day = res(1, "alice", "DC-1", datetime(2026, 10, 12, 0, 30, tzinfo=UTC),
                         datetime(2026, 10, 12, 1, 0, tzinfo=UTC))
    same_day = res(2, "alice", "DC-1", at("08:30"), at("09:00"))
    assert policy.check(late, AC, [early_next_day]).allowed
    assert policy.check(late, AC, [same_day]).code == "DAILY_LIMIT"


def test_check_order_inactive_then_overlap_then_daily_limit():
    overlap_and_daily = [res(1, "alice", "AC-1", at("10:00"), at("11:00"))]
    assert policy.check(candidate, AC_OFF, overlap_and_daily).code == "INACTIVE_STATION"
    assert policy.check(candidate, AC, overlap_and_daily).code == "OVERLAP"


# ---- ReservationRepository: kontrakt nad PostgreSQL (component) -------------------------


def test_relevant_for_returns_confirmed_of_same_station_or_user_only(system):
    repo = SqlReservationRepository(system.sessions)
    cand = repo.add(res(None, "alice", "AC-1", at("10:00"), at("11:00"), State.DRAFT))
    same_station = repo.add(res(None, "bob", "AC-1", at("12:00"), at("13:00")))
    same_user = repo.add(res(None, "alice", "DC-1", at("14:00", day=12), at("15:00", day=12)))
    repo.add(res(None, "bob", "DC-1", at("10:00", day=13), at("11:00", day=13)))  # nesouvisí
    repo.add(res(None, "bob", "AC-1", at("15:00"), at("16:00"), State.DRAFT))    # není CONFIRMED
    assert sorted(r.id for r in repo.relevant_for(cand)) == sorted([same_station.id, same_user.id])


def test_save_reports_violated_invariant_as_allocation_conflict(system):  # ADR-01
    repo = SqlReservationRepository(system.sessions)
    blocker = repo.add(res(None, "bob", "AC-1", at("10:00"), at("11:00")))
    other = repo.add(res(None, "alice", "AC-1", at("10:30"), at("11:30"), State.DRAFT))
    other.state = State.CONFIRMED
    with pytest.raises(AllocationConflict) as exc:
        repo.save(other)
    assert (exc.value.code, exc.value.related) == ("OVERLAP", [blocker.id])
    assert repo.get(other.id).state == State.DRAFT


# ---- ReservationService: přechod stavu a spolupráce (component) -------------------------


def test_state_transition_draft_to_confirmed_and_one_mail(system):
    r = system.service.create("alice", "AC-1", at("10:00"), at("11:00"))
    system.service.confirm("alice", r.id)
    assert system.service.get(r.id).state == State.CONFIRMED
    assert [(m.subject, m.status) for m in system.notifications.log] == [(f"Rezervace {r.id} je potvrzená", "SENT")]


def test_rejected_allocation_leaves_reservation_draft_and_sends_nothing(system):
    blocker = system.service.create("bob", "AC-1", at("10:00"), at("11:00"))
    system.service.confirm("bob", blocker.id)
    r = system.service.create("alice", "AC-1", at("10:30"), at("11:30"))
    with pytest.raises(Exception) as exc:
        system.service.confirm("alice", r.id)
    assert (exc.value.code, exc.value.related) == ("OVERLAP", [blocker.id])
    assert system.service.get(r.id).state == State.DRAFT
    assert len(system.notifications.log) == 1  # jen e-mail za bobovo potvrzení


def test_slow_notification_does_not_delay_conflicting_confirmation(system):
    """E-mail odchází po COMMIT: během pomalého odeslání nedrží potvrzení žádnou transakci."""
    started = threading.Event()

    def slow(to, subject, body):
        started.set()
        time.sleep(1.0)

    system.email.send = slow
    a = system.service.create("alice", "AC-1", at("10:00"), at("11:00"))
    b = system.service.create("bob", "AC-1", at("10:30"), at("11:30"))
    worker = threading.Thread(target=system.service.confirm, args=("alice", a.id))
    worker.start()
    assert started.wait(2)
    t0 = time.monotonic()
    with pytest.raises(Exception) as exc:
        system.service.confirm("bob", b.id)
    elapsed = time.monotonic() - t0
    worker.join()
    assert exc.value.code == "OVERLAP" and elapsed < 0.3


def test_approve_uses_the_same_policy(system):  # jedno místo rozhodnutí pro Confirm i Approve
    calls = []
    original = system.service.policy.check

    def spy(cand, station, others):
        calls.append(cand.id)
        return original(cand, station, others)

    system.service.policy.check = spy
    r1 = system.service.create("alice", "AC-1", at("10:00"), at("11:00"))
    system.service.confirm("alice", r1.id)
    r2 = system.service.create("bob", "DC-1", at("10:00"), at("11:00"))
    system.service.confirm("bob", r2.id)  # jen žádost, policy se nevolá
    system.service.approve("admin", r2.id)
    assert calls == [r1.id, r2.id]
