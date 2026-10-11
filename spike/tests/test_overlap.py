"""C01 engineering spike, varianta A: překryv potvrzených rezervací vynucený nad PostgreSQL."""
import pytest

from src.models import Reservation, ReservationState
from src.service import OverlapError, ReservationService
from tests.conftest import at


def test_overlapping_confirmation_is_rejected_and_state_persists(session_factory, data):
    station, alice, bob = data
    with session_factory() as s:
        service = ReservationService(s)
        a = service.create(alice, station, at(9), at(11))   # A 09:00-11:00
        b = service.create(bob, station, at(10), at(12))    # B 10:00-12:00, překrývá A
        c = service.create(bob, station, at(11), at(13))    # C 11:00-13:00, navazuje na A

        assert service.confirm(a.id).state is ReservationState.CONFIRMED
        with pytest.raises(OverlapError):
            service.confirm(b.id)
        assert service.confirm(c.id).state is ReservationState.CONFIRMED

    with session_factory() as fresh:  # nové načtení: stav opravdu přetrval v databázi
        assert fresh.get(Reservation, a.id).state is ReservationState.CONFIRMED
        assert fresh.get(Reservation, b.id).state is ReservationState.DRAFT
        assert fresh.get(Reservation, c.id).state is ReservationState.CONFIRMED
