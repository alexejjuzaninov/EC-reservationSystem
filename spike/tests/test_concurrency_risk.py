"""Otázka spike: mohou se dvě souběžná potvrzení prosadit obě?

Bariéra zajistí, že oba požadavky dokončí kontrolu překryvu dřív, než kterýkoli z nich zapíše.
xfail(strict=True) dokumentuje současné chování: databáze sama žádné omezení nemá.
"""
import threading

import pytest

from src.models import Reservation, ReservationState
from src.service import OverlapError, ReservationService
from tests.conftest import at


@pytest.mark.xfail(strict=True, reason="Bez DB omezení nebo zámku projdou obě potvrzení (driver pro C03 / CP1)")
def test_two_concurrent_confirmations_cannot_both_succeed(session_factory, data, monkeypatch):
    station, alice, bob = data
    with session_factory() as s:
        service = ReservationService(s)
        a = service.create(alice, station, at(9), at(11)).id
        b = service.create(bob, station, at(10), at(12)).id

    barrier = threading.Barrier(2)
    original = ReservationService._find_overlapping

    def find_then_wait(self, reservation):
        found = original(self, reservation)
        barrier.wait(timeout=5)
        return found

    monkeypatch.setattr(ReservationService, "_find_overlapping", find_then_wait)

    def confirm(reservation_id):
        with session_factory() as s:
            try:
                ReservationService(s).confirm(reservation_id)
            except OverlapError:
                pass

    threads = [threading.Thread(target=confirm, args=(rid,)) for rid in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with session_factory() as s:
        states = [s.get(Reservation, rid).state for rid in (a, b)]
    assert states.count(ReservationState.CONFIRMED) == 1
