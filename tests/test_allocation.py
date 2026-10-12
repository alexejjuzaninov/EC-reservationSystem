"""C05: unit a component testy odvozené z Detailed Design jednotky „přidělení stanice“.

Spuštění z kořene repozitáře (jen standardní knihovna):
    python -m unittest discover -s tests -v
"""
import threading
import time
import unittest
from datetime import datetime, timezone

from reservation import (
    AllocationDecision,
    AllocationPolicy,
    ChargingReservationSystem,
    ChargingStation,
    Clock,
    DEMO_NOW,
    InMemoryReservationRepository,
    Reservation,
    ReservationError,
    State,
    at,
)

UTC = timezone.utc
AC = ChargingStation("AC-1", "AC 22 kW", 22, "P1")
AC_OFF = ChargingStation("AC-2", "AC 22 kW", 22, "P2", active=False)


def res(rid, user, station, start, end, state=State.CONFIRMED):
    return Reservation(rid, user, station, start, end, DEMO_NOW, state)


def system(notifier=None):
    s = ChargingReservationSystem(clock=Clock(DEMO_NOW), notifier=notifier)
    s.seed_demo()
    return s


class AllocationPolicyContract(unittest.TestCase):
    """Kontrakt AllocationPolicy.check(): čistá funkce, výsledek AllocationDecision."""

    def setUp(self):
        self.policy = AllocationPolicy()
        self.candidate = res("R9", "alice", "AC-1", at("10:00"), at("11:00"), State.DRAFT)

    def test_free_slot_is_allowed_and_inputs_are_not_changed(self):
        others = [res("R1", "bob", "AC-1", at("12:00"), at("13:00"))]
        decision = self.policy.check(self.candidate, AC, others)
        self.assertEqual(decision, AllocationDecision.allow())
        self.assertEqual(self.candidate.state, State.DRAFT)
        self.assertEqual(others[0].state, State.CONFIRMED)

    def test_adjacent_interval_is_not_an_overlap(self):  # BR-01 [start, end)
        others = [res("R1", "bob", "AC-1", at("09:00"), at("10:00")), res("R2", "bob", "AC-1", at("11:00"), at("12:00"))]
        self.assertTrue(self.policy.check(self.candidate, AC, others).allowed)

    def test_overlap_returns_code_and_all_conflicting_ids(self):  # BR-02
        others = [res("R1", "bob", "AC-1", at("09:30"), at("10:30")), res("R2", "bob", "AC-1", at("10:45"), at("11:15"))]
        self.assertEqual(self.policy.check(self.candidate, AC, others), AllocationDecision.deny("OVERLAP", ["R1", "R2"]))

    def test_only_confirmed_reservations_block(self):
        others = [res("R1", "bob", "AC-1", at("10:00"), at("11:00"), state) for state in
                  (State.DRAFT, State.PENDING_APPROVAL, State.CANCELLED, State.REJECTED, State.EXPIRED)]
        self.assertTrue(self.policy.check(self.candidate, AC, others).allowed)

    def test_daily_limit_uses_utc_date_of_start(self):  # BR-04
        late = res("R8", "alice", "AC-1", datetime(2026, 10, 11, 23, 30, tzinfo=UTC), datetime(2026, 10, 12, 0, 30, tzinfo=UTC), State.DRAFT)
        early_next_day = res("R1", "alice", "DC-1", datetime(2026, 10, 12, 0, 30, tzinfo=UTC), datetime(2026, 10, 12, 1, 0, tzinfo=UTC))
        same_day = res("R2", "alice", "DC-1", at("08:30"), at("09:00"))
        self.assertTrue(self.policy.check(late, AC, [early_next_day]).allowed)
        self.assertEqual(self.policy.check(late, AC, [same_day]).code, "DAILY_LIMIT")

    def test_check_order_inactive_then_overlap_then_daily_limit(self):
        overlap_and_daily = [res("R1", "alice", "AC-1", at("10:00"), at("11:00"))]
        self.assertEqual(self.policy.check(self.candidate, AC_OFF, overlap_and_daily).code, "INACTIVE_STATION")
        self.assertEqual(self.policy.check(self.candidate, AC, overlap_and_daily).code, "OVERLAP")


class RepositoryContract(unittest.TestCase):
    def test_relevant_for_returns_confirmed_of_same_station_or_user_only(self):
        repo = InMemoryReservationRepository()
        cand = res("R0", "alice", "AC-1", at("10:00"), at("11:00"), State.DRAFT)
        for r in [cand,
                  res("R1", "bob", "AC-1", at("12:00"), at("13:00")),           # stejná stanice
                  res("R2", "alice", "DC-1", at("14:00"), at("15:00")),         # stejný uživatel
                  res("R3", "bob", "DC-1", at("10:00"), at("11:00")),           # nesouvisí
                  res("R4", "bob", "AC-1", at("10:00"), at("11:00"), State.DRAFT)]:
            repo.add(r)
        self.assertEqual([r.id for r in repo.relevant_for(cand)], ["R1", "R2"])


class ConfirmComponent(unittest.TestCase):
    """ChargingReservationSystem.confirm() se spolupracovníky: repository, policy, notifier."""

    def test_state_transition_draft_to_confirmed_and_mail_queued_once(self):
        s = system()
        r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
        s.confirm("alice", r.id)
        self.assertEqual(s.repository.get(r.id).state, State.CONFIRMED)
        self.assertEqual([(m["event"], m["status"]) for m in s.notifications], [("CONFIRMED", "SENT")])

    def test_rejected_allocation_leaves_reservation_draft_and_sends_nothing(self):
        s = system()
        blocker = s.create("bob", "AC-1", at("10:00"), at("11:00"))
        s.confirm("bob", blocker.id)
        r = s.create("alice", "AC-1", at("10:30"), at("11:30"))
        with self.assertRaises(ReservationError) as ctx:
            s.confirm("alice", r.id)
        self.assertEqual((ctx.exception.code, ctx.exception.related), ("OVERLAP", [blocker.id]))
        self.assertEqual(r.state, State.DRAFT)
        self.assertEqual(len(s.notifications), 1)  # jen e-mail za bobovo potvrzení

    def test_unexpected_notifier_error_does_not_reach_caller(self):  # C03 nález 3
        class Broken:
            def send(self, to, subject, body):
                raise TimeoutError("Notification Service timeout")
        s = system(notifier=Broken())
        r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
        result = s.confirm("alice", r.id)  # nesmí vyhodit TimeoutError
        self.assertEqual(result.state, State.CONFIRMED)
        self.assertEqual(s.notifications[-1]["status"], "FAILED")

    def test_slow_notifier_does_not_block_other_operations(self):  # C03 nález 2
        started = threading.Event()

        class Slow:
            def send(self, to, subject, body):
                started.set()
                time.sleep(1.0)
        s = system(notifier=Slow())
        r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
        worker = threading.Thread(target=s.confirm, args=("alice", r.id))
        worker.start()
        self.assertTrue(started.wait(2))
        t0 = time.monotonic()
        self.assertEqual(s.check_availability("DC-1", at("14:00"), at("15:00")), "AVAILABLE")
        self.assertLess(time.monotonic() - t0, 0.3)
        worker.join()

    def test_concurrent_conflicting_confirmations_allow_exactly_one(self):  # REQ-04
        s = system()
        a = s.create("alice", "AC-1", at("18:00"), at("19:00"))
        b = s.create("bob", "AC-1", at("18:00"), at("19:00"))
        s.after_checks = lambda: time.sleep(0.05)
        results = []

        def run(user, rid):
            try:
                results.append(s.confirm(user, rid).state.value)
            except ReservationError as exc:
                results.append(exc.code)
        threads = [threading.Thread(target=run, args=a_) for a_ in (("alice", a.id), ("bob", b.id))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(results), ["CONFIRMED", "OVERLAP"])

    def test_approve_uses_the_same_policy(self):  # jedno místo rozhodnutí pro Confirm i Approve
        calls = []

        class Spy(AllocationPolicy):
            def check(self, candidate, station, others):
                calls.append(candidate.id)
                return super().check(candidate, station, others)
        s = ChargingReservationSystem(clock=Clock(DEMO_NOW), policy=Spy())
        s.seed_demo()
        r1 = s.create("alice", "AC-1", at("10:00"), at("11:00"))
        s.confirm("alice", r1.id)
        r2 = s.create("bob", "DC-1", at("10:00"), at("11:00"))
        s.confirm("bob", r2.id)       # jen žádost, policy se nevolá
        s.approve("admin", r2.id)
        self.assertEqual(calls, [r1.id, r2.id])


if __name__ == "__main__":
    unittest.main()
