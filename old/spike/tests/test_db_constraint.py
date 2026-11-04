"""Pravidlo BR-02 drží databáze sama, i když kód service vrstvu obejde."""
import pytest
from sqlalchemy.exc import IntegrityError

from src.models import Reservation, ReservationState
from tests.conftest import at


def test_database_rejects_overlapping_confirmed_rows_even_without_service(session_factory, data):
    station, alice, bob = data
    with session_factory() as s:
        s.add(Reservation(user_id=alice, station_id=station, start_time=at(9), end_time=at(11),
                          state=ReservationState.CONFIRMED))
        s.commit()
        s.add(Reservation(user_id=bob, station_id=station, start_time=at(10), end_time=at(12),
                          state=ReservationState.CONFIRMED))
        with pytest.raises(IntegrityError):
            s.commit()


def test_database_allows_adjacent_confirmed_and_overlapping_drafts(session_factory, data):
    station, alice, bob = data
    with session_factory() as s:
        s.add_all([
            Reservation(user_id=alice, station_id=station, start_time=at(9), end_time=at(11),
                        state=ReservationState.CONFIRMED),
            Reservation(user_id=bob, station_id=station, start_time=at(11), end_time=at(13),
                        state=ReservationState.CONFIRMED),   # navazuje: [09,11) a [11,13)
            Reservation(user_id=bob, station_id=station, start_time=at(9), end_time=at(12),
                        state=ReservationState.DRAFT),       # DRAFT se smí překrývat
        ])
        s.commit()
