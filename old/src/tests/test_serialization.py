"""BR-03: operace nad touž rezervací jsou serializované, pozdější vidí výsledek dřívější.

Specifikace: „Confirm then Cancel gives CANCELLED; Cancel then Confirm gives INVALID_STATE.“
Testy pustí dvě operace nad stejnou rezervací tak, aby obě přečetly výchozí stav a prošly
kontrolami dřív, než kterákoli zapíše. Výsledek musí odpovídat jednomu z pořadí za sebou:
žádná operace nesmí hlásit úspěch, jehož účinek se ztratí (lost update).
"""
import threading

import pytest

from reservations.domain import Reservation, ReservationError, StaleState, State
from reservations.store import SqlReservationRepository
from tests.conftest import DEMO_NOW, at


def race(system, first, second):
    """Spustí dvě operace současně: obě přečtou stav a projdou kontrolami, než kterákoli zapíše.

    Pak zapíše `first` a teprve po jejím zápisu `second`. Bez serializace by `second` přepsala
    výsledek `first` stavem odvozeným ze starých dat; to je pořadí, ve kterém vzniká lost update.
    """
    barrier = threading.Barrier(2)
    first_written = threading.Event()
    state = threading.local()
    original = system.service.repository.save

    def ordered_save(reservation, expected):
        if not getattr(state, "waited", False):  # jen první zápis každé operace
            state.waited = True
            barrier.wait(timeout=5)
            if state.name == "second":
                assert first_written.wait(timeout=5)
        try:
            return original(reservation, expected)
        finally:
            if state.name == "first":
                first_written.set()

    system.service.repository.save = ordered_save
    results = {}

    def run(role, name, call):
        state.name = role
        try:
            results[name] = call().state.value
        except ReservationError as exc:
            results[name] = exc.code
        finally:
            if role == "first":
                first_written.set()  # i kdyby first skončila chybou, second nesmí čekat navždy

    threads = [threading.Thread(target=run, args=("first", *first)),
               threading.Thread(target=run, args=("second", *second))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    system.service.repository.save = original
    return results


def test_save_from_stale_state_is_refused_and_changes_nothing(system):
    repo = SqlReservationRepository(system.sessions)
    r = repo.add(Reservation(None, "alice", "AC-1", at("10:00"), at("11:00"), DEMO_NOW))
    r.state = State.CANCELLED
    with pytest.raises(StaleState):
        repo.save(r, expected=State.CONFIRMED)  # v databázi je DRAFT, ne CONFIRMED
    assert repo.get(r.id).state == State.DRAFT


def test_cancel_written_first_then_confirm_sees_cancelled(system):
    """Cancel → Confirm: Confirm musí dostat INVALID_STATE, ne přepsat zrušení na CONFIRMED."""
    r = system.service.create("alice", "AC-1", at("10:00"), at("11:00"))
    results = race(system,
                   ("cancel", lambda: system.service.cancel("alice", r.id)),
                   ("confirm", lambda: system.service.confirm("alice", r.id)))

    assert results == {"cancel": "CANCELLED", "confirm": "INVALID_STATE"}
    assert system.service.get(r.id).state == State.CANCELLED
    assert [m.subject for m in system.notifications.log] == [f"Rezervace {r.id} je zrušená"]


def test_cancel_written_first_then_approve_sees_cancelled(system):
    """Cancel → Approve: schválení zrušené žádosti musí skončit INVALID_STATE."""
    r = system.service.create("bob", "DC-1", at("12:00"), at("13:00"))
    system.service.confirm("bob", r.id)  # PENDING_APPROVAL
    results = race(system,
                   ("cancel", lambda: system.service.cancel("bob", r.id)),
                   ("approve", lambda: system.service.approve("admin", r.id)))

    assert results == {"cancel": "CANCELLED", "approve": "INVALID_STATE"}
    assert system.service.get(r.id).state == State.CANCELLED
    assert [m.subject for m in system.notifications.log] == [f"Rezervace {r.id} je zrušená"]


def test_confirm_written_first_then_cancel_cancels_confirmed(system):
    """Confirm → Cancel: zrušení potvrzené rezervace je povolené (BR-03), výsledek CANCELLED."""
    r = system.service.create("alice", "AC-1", at("10:00"), at("11:00"))
    results = race(system,
                   ("confirm", lambda: system.service.confirm("alice", r.id)),
                   ("cancel", lambda: system.service.cancel("alice", r.id)))

    assert results == {"confirm": "CONFIRMED", "cancel": "CANCELLED"}
    assert system.service.get(r.id).state == State.CANCELLED
    assert [m.subject for m in system.notifications.log] == [
        f"Rezervace {r.id} je potvrzená", f"Rezervace {r.id} je zrušená"]


def test_approve_written_first_then_reject_sees_confirmed(system):
    """Approve → Reject: o žádosti se rozhoduje jednou; zamítnutí po schválení je INVALID_STATE."""
    r = system.service.create("bob", "DC-1", at("12:00"), at("13:00"))
    system.service.confirm("bob", r.id)  # PENDING_APPROVAL
    results = race(system,
                   ("approve", lambda: system.service.approve("admin", r.id)),
                   ("reject", lambda: system.service.reject("admin", r.id)))

    assert results == {"approve": "CONFIRMED", "reject": "INVALID_STATE"}
    assert system.service.get(r.id).state == State.CONFIRMED
    assert len(system.notifications.log) == 1
