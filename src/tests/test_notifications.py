"""DR3 / REQ-09: e-mail odchází až po zapsání stavu a žádná chyba služby nemění výsledek."""
from sqlalchemy import select

from reservations.store import ReservationRow
from tests.api_helpers import act, create
from tests.conftest import at


def test_email_is_sent_only_after_state_is_committed(system):
    seen = []

    def send(to, subject, body):
        # Jiné spojení vidí jen zapsaná (COMMIT) data: rezervace už musí být CONFIRMED.
        with system.sessions() as s:
            seen.append(s.scalars(select(ReservationRow.state)).one().value)

    system.email.send = send
    _, r = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    act(system.client, "confirm", "alice", r["id"])
    assert seen == ["CONFIRMED"]


def test_unexpected_notification_error_does_not_reach_caller(system):
    def broken(to, subject, body):
        raise TimeoutError("Notification Service did not answer")

    system.email.send = broken
    _, r = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "confirm", "alice", r["id"])
    assert status == 200 and body["state"] == "CONFIRMED"
    assert system.notifications.log[-1].status == "FAILED"
