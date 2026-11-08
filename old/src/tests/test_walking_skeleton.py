"""CP1 walking skeleton z C01: POST /reservations → validate → persist → return ID → automated check."""
from sqlalchemy import select

from reservations.store import ReservationRow
from tests.api_helpers import create
from tests.conftest import at


def test_post_reservation_returns_201_and_id_and_row_is_in_database(system):
    status, body = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))

    assert status == 201
    assert isinstance(body["id"], int) and body["state"] == "DRAFT"
    with system.sessions() as s:  # nové spojení: záznam je opravdu zapsaný v PostgreSQL
        row = s.scalars(select(ReservationRow).where(ReservationRow.id == body["id"])).one()
    assert (row.user_id, row.station_id, row.state.value) == ("alice", "AC-1", "DRAFT")
    assert row.start_time == at("10:00") and row.end_time == at("11:00")


def test_invalid_request_is_rejected_and_nothing_is_persisted(system):
    status, body = create(system.client, "alice", "AC-1", at("10:00"), at("10:00"))

    assert status == 422 and body["code"] == "INVALID_INTERVAL"
    with system.sessions() as s:
        assert s.scalars(select(ReservationRow)).all() == []
