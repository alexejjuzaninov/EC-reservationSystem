"""DR1 / ADR-01: invariant BR-04 při souběhu (BR-02 ověřuje test_op03_concurrent_confirmations).

Oba požadavky projdou kontrolou v AllocationPolicy dřív, než kterýkoli zapíše. Rozhodnout
musí unikátní index one_confirmed_per_user_day v PostgreSQL.
"""
import threading

from tests.api_helpers import act, create, pending, state
from tests.conftest import at


def test_same_user_two_stations_same_day_concurrently_only_one_confirmed(system):
    # Alice: žádost na DC-1 čeká na schválení, návrh na AC-1 potvrzuje sama; stejný den, různé stanice.
    waiting = pending(system.client, "alice", at("14:00"), at("15:00"))
    _, draft = create(system.client, "alice", "AC-1", at("10:00"), at("11:00"))

    barrier = threading.Barrier(2)
    original = system.service.policy.check

    def check_then_wait(*args):
        decision = original(*args)
        barrier.wait(timeout=5)
        return decision

    system.service.policy.check = check_then_wait
    results = {}

    def run(action, user, reservation_id):
        status, body = act(system.client, action, user, reservation_id)
        results[reservation_id] = body["state"] if status == 200 else body["code"]

    threads = [threading.Thread(target=run, args=("approve", "admin", waiting)),
               threading.Thread(target=run, args=("confirm", "alice", draft["id"]))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results.values()) == ["CONFIRMED", "DAILY_LIMIT"]
    states = {state(system.client, waiting), state(system.client, draft["id"])}
    assert "CONFIRMED" in states and len([s for s in states if s == "CONFIRMED"]) == 1
