"""Doplňkové integrační ověření dvou žádostí a plánovače expirace."""
import time
from overeni_rezervaci import api, sql, find_slot, booking_state, events, charge, expect, STATION, ANNA, MARK, ILYA


def make_pending(actor, payload):
    code, draft = api("/bookings", actor=actor, body=payload)
    expect("vytvoření návrhu", code, 201)
    booking_id = draft["id"]
    code, answer = api(f"/bookings/{booking_id}/confirm", actor=actor, body={})
    expect("podání žádosti", code, 200)
    expect("žádost čeká", answer["status"], "PENDING_APPROVAL")
    return booking_id


def main():
    start, end = find_slot()
    payload = {"stationId": STATION, "startAt": start, "endAt": end}
    first = make_pending(ANNA, payload)
    second = make_pending(MARK, payload)
    expect("dvě čekající žádosti mohou sdílet slot", booking_state(second), "PENDING_APPROVAL")
    code, _ = api(f"/bookings/{first}/decision", actor=ILYA, body={"approve": True})
    expect("schválení první žádosti", code, 200)
    code, _ = api(f"/bookings/{second}/decision", actor=ILYA, body={"approve": True})
    expect("schválení druhé žádosti je konflikt", code, 409)
    expect("druhá zůstává čekající", booking_state(second), "PENDING_APPROVAL")
    code, _ = api(f"/bookings/{first}/cancel", actor=ANNA, body={})
    expect("první rezervace se uvolní", code, 200)
    code, _ = api(f"/bookings/{second}/decision", actor=ILYA, body={"approve": True})
    expect("druhá žádost jde po uvolnění schválit", code, 200)
    expect("druhá je potvrzena", booking_state(second), "CONFIRMED")
    code, _ = api(f"/bookings/{second}/cancel", actor=MARK, body={})
    expect("úklid druhé rezervace", code, 200)

    expiring = make_pending(ANNA, payload)
    changed = sql("UPDATE reservation.bookings SET start_at = now() - interval '90 minutes', "
                  f"end_at = now() - interval '30 minutes' WHERE id = '{expiring}'")
    expect("přesun testovací žádosti do minulosti", changed, "UPDATE 1")
    for _ in range(40):
        if booking_state(expiring) == "EXPIRED":
            break
        time.sleep(2)
    expect("plánovač ukončil nevyřízenou žádost", booking_state(expiring), "EXPIRED")
    expect("expirace má událost", events(expiring), "REQUESTED,EXPIRED")
    expect("expirace nemá platbu", charge(expiring), "")
    print("TEST OK; záznamy:", first, second, expiring)


if __name__ == "__main__":
    main()
