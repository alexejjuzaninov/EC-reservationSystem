"""Volání Reservation API v testech: jeden řádek na operaci, výsledek jako (status, JSON)."""
from datetime import datetime

from fastapi.testclient import TestClient


def create(client: TestClient, user: str, station: str, start: datetime, end: datetime):
    r = client.post(
        "/reservations",
        json={"station_id": station, "start_time": start.isoformat(), "end_time": end.isoformat()},
        headers={"X-User-Id": user},
    )
    return r.status_code, r.json()


def act(client: TestClient, action: str, user: str, reservation_id: int):
    """action: confirm / cancel / approve / reject"""
    r = client.post(f"/reservations/{reservation_id}/{action}", headers={"X-User-Id": user})
    return r.status_code, r.json()


def state(client: TestClient, reservation_id: int) -> str:
    return client.get(f"/reservations/{reservation_id}").json()["state"]


def availability(client: TestClient, station: str, start: datetime, end: datetime) -> str:
    r = client.get(
        f"/stations/{station}/availability",
        params={"start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert r.status_code == 200, r.text
    return r.json()["result"]


def confirmed(client: TestClient, user: str, station: str, start: datetime, end: datetime) -> int:
    status, body = create(client, user, station, start, end)
    assert status == 201, body
    status, body = act(client, "confirm", user, body["id"])
    assert status == 200 and body["state"] == "CONFIRMED", body
    return body["id"]


def pending(client: TestClient, user: str, start: datetime, end: datetime) -> int:
    """Rezervace stanice DC-1 (vyžaduje schválení) po Confirm: PENDING_APPROVAL."""
    status, body = create(client, user, "DC-1", start, end)
    assert status == 201, body
    status, body = act(client, "confirm", user, body["id"])
    assert status == 200 and body["state"] == "PENDING_APPROVAL", body
    return body["id"]
