"""ADR-01: invarianty BR-02 a BR-04 drží databáze sama, i když zápis obejde aplikaci.

Shodu s AllocationPolicy hlídají stejné hraniční případy: navazující interval, překryv, den v UTC.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from reservations.domain import State
from reservations.store import ReservationRow
from tests.conftest import at


def row(user, station, start, end, state=State.CONFIRMED):
    return ReservationRow(user_id=user, station_id=station, start_time=start, end_time=end,
                          state=state, created_at=at("08:00"))


def insert(system, *rows):
    with system.sessions() as s:
        s.add_all(rows)
        s.commit()


def test_br02_overlapping_confirmed_rows_are_rejected(system):
    insert(system, row("alice", "AC-1", at("09:00"), at("11:00")))
    with pytest.raises(IntegrityError, match="no_overlapping_confirmed"):
        insert(system, row("bob", "AC-1", at("10:00"), at("12:00")))


def test_br02_adjacent_confirmed_and_overlapping_drafts_are_allowed(system):
    insert(system,
           row("alice", "AC-1", at("09:00"), at("11:00")),
           row("bob", "AC-1", at("11:00"), at("13:00")),                     # navazuje: [09,11) a [11,13)
           row("bob", "AC-1", at("09:00", day=12), at("12:00", day=12)),
           row("alice", "AC-1", at("10:00", day=12), at("11:00", day=12), State.DRAFT))  # DRAFT se smí překrývat


def test_br04_second_confirmed_same_user_same_utc_day_is_rejected(system):
    insert(system, row("alice", "AC-1", at("09:00"), at("10:00")))
    with pytest.raises(IntegrityError, match="one_confirmed_per_user_day"):
        insert(system, row("alice", "DC-1", at("15:00"), at("16:00")))


def test_br04_day_boundary_is_utc_midnight(system):
    late = datetime(2026, 10, 11, 23, 30, tzinfo=timezone.utc)
    early_next = datetime(2026, 10, 12, 0, 30, tzinfo=timezone.utc)
    insert(system,
           row("alice", "AC-1", late, datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)),
           row("alice", "DC-1", early_next, datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)))
