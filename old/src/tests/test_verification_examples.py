"""Příklady ověření ze specifikace C02 (baseline v0.2), spuštěné přes HTTP nad PostgreSQL.

Stejných 40 příkladů se stejnými názvy (docstring) má aplikace C02: `python reservation.py test`.
Očekávané výsledky jsou ze specifikace (docs/specification.md), ne z kódu.
"""
import threading

from tests.api_helpers import act, availability, confirmed, create, pending, state
from tests.conftest import at

# ---- OP-01 Create Reservation -------------------------------------------------


def test_op01_valid_request(system):
    """platný požadavek -> DRAFT"""
    status, body = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    assert status == 201 and body["state"] == "DRAFT" and body["user_id"] == "alice"


def test_op01_drafts_may_overlap(system):
    """dva DRAFTy na stejný čas -> vzniknou oba"""
    a = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    b = create(system.client, "bob", "AC-1", at("10:00"), at("11:00"))
    assert a[0] == b[0] == 201 and a[1]["state"] == b[1]["state"] == "DRAFT"


def test_op01_start_equals_end(system):
    """začátek == konec -> INVALID_INTERVAL"""
    status, body = create(system.client, "alice", "AC-1", at("10:00"), at("10:00"))
    assert status == 422 and body["code"] == "INVALID_INTERVAL"


def test_op01_exactly_4_hours(system):
    """přesně 4 hodiny -> DRAFT"""
    status, body = create(system.client, "alice", "AC-1", at("09:00"), at("13:00"))
    assert status == 201 and body["state"] == "DRAFT"


def test_op01_over_4_hours(system):
    """4,5 hodiny -> INVALID_DURATION"""
    status, body = create(system.client, "alice", "AC-1", at("09:00"), at("13:30"))
    assert status == 422 and body["code"] == "INVALID_DURATION"


def test_op01_start_in_past(system):
    """začátek v minulosti -> START_IN_PAST"""
    status, body = create(system.client, "alice", "AC-1", at("07:00"), at("08:00"))
    assert status == 422 and body["code"] == "START_IN_PAST"


def test_op01_unknown_station(system):
    """neznámá stanice -> UNKNOWN_STATION"""
    status, body = create(system.client, "alice", "XX-9", at("10:00"), at("11:00"))
    assert status == 404 and body["code"] == "UNKNOWN_STATION"


def test_op01_admin_does_not_create(system):
    """Facility admin rezervaci nevytváří -> UNAUTHORIZED"""
    status, body = create(system.client, "admin", "AC-1", at("10:00"), at("11:00"))
    assert status == 403 and body["code"] == "UNAUTHORIZED"


# ---- OP-02 Check Availability (CONFIRMED [10:00, 11:00)) ----------------------


def test_op02_adjacent_before(system):
    """dotaz [09:00, 10:00) -> AVAILABLE"""
    confirmed(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    assert availability(system.client, "AC-1", at("09:00"), at("10:00")) == "AVAILABLE"


def test_op02_overlap(system):
    """dotaz [10:30, 11:30) -> UNAVAILABLE"""
    confirmed(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    assert availability(system.client, "AC-1", at("10:30"), at("11:30")) == "UNAVAILABLE"


def test_op02_adjacent_after(system):
    """dotaz [11:00, 12:00) -> AVAILABLE"""
    confirmed(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    assert availability(system.client, "AC-1", at("11:00"), at("12:00")) == "AVAILABLE"


def test_op02_draft_does_not_block(system):
    """DRAFT stanici neblokuje -> AVAILABLE"""
    create(system.client, "bob", "AC-1", at("14:00"), at("15:00"))
    assert availability(system.client, "AC-1", at("14:00"), at("15:00")) == "AVAILABLE"


def test_op02_inactive_station(system):
    """stanice mimo provoz -> UNAVAILABLE"""
    assert availability(system.client, "AC-2", at("10:00"), at("11:00")) == "UNAVAILABLE"


# ---- OP-03 Confirm Reservation ------------------------------------------------


def test_op03_free_draft_confirmed_with_email(system):
    """volný DRAFT -> CONFIRMED + e-mail"""
    _, r = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "confirm", "alice", r["id"])
    mail = system.notifications.log[-1]
    assert status == 200 and body["state"] == "CONFIRMED"
    assert (mail.to, mail.subject, mail.status) == ("alice@example.com", f"Rezervace {r['id']} je potvrzená", "SENT")


def test_op03_overlap(system):
    """překryv s potvrzenou -> OVERLAP, zůstává DRAFT"""
    blocker = confirmed(system.client, "bob", "AC-1", at("10:00"), at("11:00"))
    _, r = create(system.client, "alice", "AC-1", at("10:30"), at("11:30"))
    status, body = act(system.client, "confirm", "alice", r["id"])
    assert status == 409 and body["code"] == "OVERLAP" and body["related"] == [blocker]
    assert state(system.client, r["id"]) == "DRAFT"


def test_op03_adjacent(system):
    """navazující [11:00, 13:00) -> CONFIRMED"""
    confirmed(system.client, "bob", "AC-1", at("09:00"), at("11:00"))
    _, r = create(system.client, "alice", "AC-1", at("11:00"), at("13:00"))
    status, body = act(system.client, "confirm", "alice", r["id"])
    assert status == 200 and body["state"] == "CONFIRMED"


def test_op03_daily_limit(system):
    """druhá potvrzená v témže dni -> DAILY_LIMIT"""
    first = confirmed(system.client, "alice", "AC-1", at("09:00"), at("10:00"))
    _, second = create(system.client, "alice", "AC-1", at("15:00"), at("16:00"))
    status, body = act(system.client, "confirm", "alice", second["id"])
    assert status == 409 and body["code"] == "DAILY_LIMIT" and body["related"] == [first]
    assert state(system.client, second["id"]) == "DRAFT"


def test_op03_next_day(system):
    """další den -> CONFIRMED"""
    confirmed(system.client, "alice", "AC-1", at("09:00"), at("10:00"))
    _, r = create(system.client, "alice", "AC-1", at("15:00", day=12), at("16:00", day=12))
    status, body = act(system.client, "confirm", "alice", r["id"])
    assert status == 200 and body["state"] == "CONFIRMED"


def test_op03_inactive_station(system):
    """stanice mimo provoz -> INACTIVE_STATION"""
    _, r = create(system.client, "alice", "AC-2", at("10:00"), at("11:00"))
    status, body = act(system.client, "confirm", "alice", r["id"])
    assert status == 409 and body["code"] == "INACTIVE_STATION"
    assert state(system.client, r["id"]) == "DRAFT"


def test_op03_foreign_reservation(system):
    """cizí rezervace -> UNAUTHORIZED"""
    _, r = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "confirm", "bob", r["id"])
    assert status == 403 and body["code"] == "UNAUTHORIZED"
    assert state(system.client, r["id"]) == "DRAFT"


def test_op03_already_confirmed(system):
    """už potvrzená -> INVALID_STATE"""
    r = confirmed(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "confirm", "alice", r)
    assert status == 409 and body["code"] == "INVALID_STATE"
    assert state(system.client, r) == "CONFIRMED"


def test_op03_after_start(system):
    """po začátku rezervace -> TOO_LATE"""
    _, r = create(system.client, "alice", "AC-1", at("09:00"), at("10:00"))
    system.clock.instant = at("09:00")
    status, body = act(system.client, "confirm", "alice", r["id"])
    assert status == 409 and body["code"] == "TOO_LATE"
    assert state(system.client, r["id"]) == "DRAFT"


def test_op03_concurrent_confirmations(system):
    """dvě souběžná potvrzení -> právě jedno CONFIRMED"""
    _, a = create(system.client, "alice", "AC-1", at("18:00"), at("19:00"))
    _, b = create(system.client, "bob", "AC-1", at("18:00"), at("19:00"))
    # Oba požadavky dokončí kontrolu v AllocationPolicy dřív, než kterýkoli zapíše:
    # obě vidí „volno“ a rozhodnout musí databáze (ADR-01).
    barrier = threading.Barrier(2)
    original = system.service.policy.check

    def check_then_wait(*args):
        decision = original(*args)
        barrier.wait(timeout=5)
        return decision

    system.service.policy.check = check_then_wait
    results = []

    def run(user, reservation_id):
        status, body = act(system.client, "confirm", user, reservation_id)
        results.append(body["state"] if status == 200 else body["code"])

    threads = [threading.Thread(target=run, args=("alice", a["id"])),
               threading.Thread(target=run, args=("bob", b["id"]))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["CONFIRMED", "OVERLAP"]


# ---- OP-04 Cancel Reservation -------------------------------------------------


def test_op04_cancel_draft(system):
    """DRAFT před začátkem -> CANCELLED"""
    _, r = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "cancel", "alice", r["id"])
    assert status == 200 and body["state"] == "CANCELLED"


def test_op04_cancel_confirmed_frees_station(system):
    """CONFIRMED -> CANCELLED, stanice volná, e-mail"""
    r = confirmed(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "cancel", "alice", r)
    assert status == 200 and body["state"] == "CANCELLED"
    assert availability(system.client, "AC-1", at("10:00"), at("11:00")) == "AVAILABLE"
    assert system.notifications.log[-1].subject == f"Rezervace {r} je zrušená"


def test_op04_cancel_at_start(system):
    """v okamžiku začátku -> TOO_LATE, zůstává CONFIRMED"""
    r = confirmed(system.client, "alice", "AC-1", at("09:00"), at("10:00"))
    system.clock.instant = at("09:00")
    status, body = act(system.client, "cancel", "alice", r)
    assert status == 409 and body["code"] == "TOO_LATE"
    assert state(system.client, r) == "CONFIRMED"


def test_op04_cancel_twice(system):
    """opakované zrušení -> úspěch beze změny"""
    r = confirmed(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    act(system.client, "cancel", "alice", r)
    mails = len(system.notifications.log)
    status, body = act(system.client, "cancel", "alice", r)
    assert status == 200 and body["state"] == "CANCELLED" and len(system.notifications.log) == mails


def test_op04_cancel_foreign_by_employee(system):
    """cizí rezervace zaměstnancem -> UNAUTHORIZED"""
    _, r = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "cancel", "bob", r["id"])
    assert status == 403 and body["code"] == "UNAUTHORIZED"
    assert state(system.client, r["id"]) == "DRAFT"


def test_op04_cancel_by_admin(system):
    """Facility admin zruší cizí rezervaci -> CANCELLED"""
    r = confirmed(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "cancel", "admin", r)
    assert status == 200 and body["state"] == "CANCELLED"


# ---- REQ-09 Notifikace --------------------------------------------------------


def test_req09_notification_service_unavailable(system):
    """Notification Service nedostupná -> CONFIRMED, e-mail FAILED"""
    system.email.available = False
    _, r = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))
    status, body = act(system.client, "confirm", "alice", r["id"])
    assert status == 200 and body["state"] == "CONFIRMED"
    assert system.notifications.log[-1].status == "FAILED"


# ---- v0.2 OP-05 Approve / Reject ----------------------------------------------


def test_v02_confirm_requests_approval(system):
    """Confirm na DC-1 -> PENDING_APPROVAL, bez e-mailu"""
    pending(system.client, "alice", at("10:00"), at("11:00"))
    assert system.notifications.log == []


def test_v02_pending_does_not_block(system):
    """PENDING_APPROVAL stanici neblokuje -> AVAILABLE"""
    pending(system.client, "alice", at("10:00"), at("11:00"))
    assert availability(system.client, "DC-1", at("10:00"), at("11:00")) == "AVAILABLE"


def test_v02_approve(system):
    """schválení -> CONFIRMED + e-mail"""
    r = pending(system.client, "alice", at("10:00"), at("11:00"))
    status, body = act(system.client, "approve", "admin", r)
    mail = system.notifications.log[-1]
    assert status == 200 and body["state"] == "CONFIRMED"
    assert (mail.subject, mail.status) == (f"Rezervace {r} je potvrzená", "SENT")


def test_v02_approve_by_employee(system):
    """schvaluje zaměstnanec -> UNAUTHORIZED"""
    r = pending(system.client, "alice", at("10:00"), at("11:00"))
    status, body = act(system.client, "approve", "alice", r)
    assert status == 403 and body["code"] == "UNAUTHORIZED"
    assert state(system.client, r) == "PENDING_APPROVAL"


def test_v02_reject(system):
    """zamítnutí -> REJECTED + e-mail"""
    r = pending(system.client, "bob", at("12:00"), at("13:00"))
    status, body = act(system.client, "reject", "admin", r)
    assert status == 200 and body["state"] == "REJECTED"
    assert system.notifications.log[-1].subject == f"Rezervace {r} byla zamítnuta"


def test_v02_approve_overlap(system):
    """mezitím potvrzený překryv -> OVERLAP, zůstává PENDING"""
    first = pending(system.client, "alice", at("10:00"), at("11:00"))
    second = pending(system.client, "bob", at("10:30"), at("11:30"))
    act(system.client, "approve", "admin", first)
    status, body = act(system.client, "approve", "admin", second)
    assert status == 409 and body["code"] == "OVERLAP" and body["related"] == [first]
    assert state(system.client, second) == "PENDING_APPROVAL"


def test_v02_approve_daily_limit(system):
    """denní limit při schválení -> DAILY_LIMIT"""
    confirmed(system.client, "alice", "AC-1", at("08:30"), at("09:30"))
    r = pending(system.client, "alice", at("14:00"), at("15:00"))
    status, body = act(system.client, "approve", "admin", r)
    assert status == 409 and body["code"] == "DAILY_LIMIT"
    assert state(system.client, r) == "PENDING_APPROVAL"


def test_v02_delayed_approval(system):
    """zpožděné schválení v 09:59 -> CONFIRMED"""
    r = pending(system.client, "alice", at("10:00"), at("11:00"))
    system.clock.instant = at("09:59")
    status, body = act(system.client, "approve", "admin", r)
    assert status == 200 and body["state"] == "CONFIRMED"


def test_v02_expired_at_start(system):
    """rozhodnutí v 10:00 (začátek) -> EXPIRED"""
    r = pending(system.client, "alice", at("10:00"), at("11:00"))
    system.clock.instant = at("10:00")
    status, body = act(system.client, "approve", "admin", r)
    assert status == 409 and body["code"] == "EXPIRED"
    assert state(system.client, r) == "EXPIRED"


def test_v02_cancel_pending(system):
    """zrušení PENDING_APPROVAL -> CANCELLED"""
    r = pending(system.client, "alice", at("10:00"), at("11:00"))
    status, body = act(system.client, "cancel", "alice", r)
    assert status == 200 and body["state"] == "CANCELLED"
