"""Opakovatelné integrační ověření schvalované rezervace na lokálním Compose.

Spuštění: python verification/overeni_rezervaci.py
Test vytvoří několik označených demo záznamů; jejich ID vypíše na konci.
"""
import datetime as dt
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:18080/api"
STATION = "20000000-0000-0000-0000-000000000002"
ANNA = "10000000-0000-0000-0000-000000000001"
MARK = "10000000-0000-0000-0000-000000000005"
ILYA = "10000000-0000-0000-0000-000000000002"
ids = []


def api(path, actor=ANNA, body=None, method=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method or ("POST" if body is not None else "GET"),
                                 headers={"X-Demo-User": actor, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def sql(query):
    result = subprocess.run(["docker", "compose", "exec", "-T", "db-primary", "psql", "-U", "postgres",
                             "-d", "ec_reservation", "-At", "-c", query], capture_output=True,
                            text=True, check=True)
    return result.stdout.strip()


def expect(label, actual, expected):
    assert actual == expected, f"{label}: očekáváno {expected!r}, zjištěno {actual!r}"
    print(f"OK  {label}: {actual}")


def booking_state(booking_id):
    return sql(f"SELECT status FROM reservation.bookings WHERE id = '{booking_id}'")


def events(booking_id):
    return sql(f"SELECT string_agg(event_type, ',' ORDER BY created_at) FROM reservation.outbox WHERE booking_id = '{booking_id}'")


def charge(booking_id):
    return sql(f"SELECT status FROM billing.simulated_charges WHERE booking_id = '{booking_id}'")


def find_slot():
    start_day = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=65)
    for offset in range(20):
        instant = dt.datetime.combine(start_day + dt.timedelta(days=offset), dt.time(12), dt.timezone.utc)
        start = instant.isoformat().replace("+00:00", "Z")
        end = (instant + dt.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        query = urllib.parse.urlencode({"startAt": start, "endAt": end})
        status, availability = api(f"/stations/{STATION}/availability?{query}")
        if status == 200 and availability["available"]:
            return start, end
    raise RuntimeError("Nebyl nalezen volný hodinový termín pro test")


def main():
    start, end = find_slot()
    payload = {"stationId": STATION, "startAt": start, "endAt": end}
    print(f"Zkušební termín: {start} až {end}")

    status, draft = api("/bookings", body=payload)
    expect("vytvoření návrhu HTTP", status, 201)
    first = draft["id"]
    ids.append(first)
    expect("návrh v databázi", booking_state(first), "DRAFT")
    expect("návrh nemá účetní událost", events(first), "")
    expect("návrh nemá platbu", charge(first), "")

    status, pending = api(f"/bookings/{first}/confirm", body={})
    expect("potvrzení požadavku HTTP", status, 200)
    expect("stav čeká na vlastníka", pending["status"], "PENDING_APPROVAL")
    expect("stav v databázi", booking_state(first), "PENDING_APPROVAL")
    expect("čekání vytváří pouze REQUESTED", events(first), "REQUESTED")
    expect("čekání nemá platbu", charge(first), "")
    expect("přístupový pokyn není zveřejněn", pending["accessNote"], "")

    status, _ = api(f"/bookings/{first}/decision", actor=MARK, body={"approve": True})
    expect("cizí řidič nesmí schválit", status, 403)
    expect("stav po zakázaném pokusu", booking_state(first), "PENDING_APPROVAL")

    status, confirmed = api(f"/bookings/{first}/decision", actor=ILYA, body={"approve": True})
    expect("vlastník schválí HTTP", status, 200)
    expect("schválená rezervace", confirmed["status"], "CONFIRMED")
    expect("stav v databázi po schválení", booking_state(first), "CONFIRMED")
    expect("události žádost a potvrzení", events(first), "REQUESTED,BOOKED")
    status, _ = api(f"/bookings/{first}/decision", actor=ILYA, body={"approve": True})
    expect("opakované rozhodnutí je konflikt", status, 409)

    status, second = api("/bookings", actor=MARK, body=payload)
    expect("souběžný návrh lze vytvořit", status, 201)
    other = second["id"]
    ids.append(other)
    status, _ = api(f"/bookings/{other}/confirm", actor=MARK, body={})
    expect("obsazený termín nelze potvrdit", status, 409)
    expect("druhý návrh zůstává návrhem", booking_state(other), "DRAFT")

    status, cancelled = api(f"/bookings/{first}/cancel", body={})
    expect("zrušení HTTP", status, 200)
    expect("zrušená rezervace", cancelled["status"], "CANCELLED")
    status, _ = api(f"/bookings/{other}/confirm", actor=MARK, body={})
    expect("uvolněný termín jde znovu požádat", status, 200)
    expect("druhá žádost čeká", booking_state(other), "PENDING_APPROVAL")
    status, rejected = api(f"/bookings/{other}/decision", actor=ILYA, body={"approve": False})
    expect("zamítnutí HTTP", status, 200)
    expect("zamítnutý stav v databázi", booking_state(other), "REJECTED")
    expect("zamítnutí bez platby", charge(other), "")

    for _ in range(20):
        if charge(first) == "CANCELLED":
            break
        time.sleep(0.5)
    expect("simulovaná platba po zrušení", charge(first), "CANCELLED")
    print("TEST OK; vytvořené záznamy:", ", ".join(ids))


if __name__ == "__main__":
    main()
