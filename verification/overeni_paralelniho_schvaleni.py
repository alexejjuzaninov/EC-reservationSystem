"""Současné rozhodnutí dvou čekajících žádostí pro stejný termín."""
from concurrent.futures import ThreadPoolExecutor
from overeni_rezervaci import api, sql, find_slot, booking_state, expect, STATION, ANNA, MARK, ILYA


def pending(actor, payload):
    code, draft = api("/bookings", actor=actor, body=payload)
    expect("návrh vytvořen", code, 201)
    code, _ = api(f"/bookings/{draft['id']}/confirm", actor=actor, body={})
    expect("žádost podána", code, 200)
    return draft["id"]


def main():
    start, end = find_slot()
    payload = {"stationId": STATION, "startAt": start, "endAt": end}
    first = pending(ANNA, payload)
    second = pending(MARK, payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(api, f"/bookings/{booking_id}/decision", ILYA, {"approve": True})
                   for booking_id in (first, second)]
        codes = sorted(f.result()[0] for f in futures)
    expect("paralelní HTTP výsledky", codes, [200, 409])
    states = sorted([booking_state(first), booking_state(second)])
    expect("jeden potvrzený a jeden čekající stav", states, ["CONFIRMED", "PENDING_APPROVAL"])
    confirmed_count = sql("SELECT count(*) FROM reservation.bookings WHERE id IN "
                          f"('{first}', '{second}') AND status = 'CONFIRMED'")
    expect("DB oracle: právě jeden obsazený slot", confirmed_count, "1")
    for booking_id, actor in ((first, ANNA), (second, MARK)):
        code, _ = api(f"/bookings/{booking_id}/cancel", actor=actor, body={})
        expect("úklid žádosti", code, 200)
    print("TEST OK; záznamy:", first, second)


if __name__ == "__main__":
    main()
