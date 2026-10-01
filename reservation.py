"""Rezervace nabíjecích stanic pro elektromobily: běžící aplikace C02 (Specification Baseline v0.2).

Doména, aktéři a pravidla jsou z C01 (docs/intent-and-change.md): firemní nabíjecí stanice,
zaměstnanci, Facility admin a externí Notification Service. Specifikace je v README.md.

Architektura je záměrně jednoduchá: jeden modul, data jen v paměti, jeden zámek pro všechny
operace. Přidělení stanice (Confirm, Approve) je od C05 navržené jako samostatná jednotka:
AllocationPolicy rozhoduje, ReservationRepository poskytuje data, e-maily odcházejí až po
uvolnění zámku. Návrh je v docs/architecture-and-decisions.md, část C05 Detailed Design.

Spuštění (Python 3.10+, bez dalších balíčků):
    python reservation.py test    # příklady ověření ze specifikace, výsledek PASS/FAIL
    python reservation.py demo    # krátká ukázka všech operací
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional, Protocol, Tuple

UTC = timezone.utc
MAX_DURATION = timedelta(hours=4)  # BR-04


class State(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"  # v0.2
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"  # v0.2
    EXPIRED = "EXPIRED"  # v0.2


# BR-03: ze kterých stavů lze rezervaci zrušit
CANCELLABLE_STATES = (State.DRAFT, State.PENDING_APPROVAL, State.CONFIRMED)


class Role(str, Enum):
    EMPLOYEE = "EMPLOYEE"  # zaměstnanec
    ADMIN = "ADMIN"  # Facility admin


@dataclass
class User:
    id: str
    role: Role
    email: str
    vehicle_type: Optional[str] = None


@dataclass
class ChargingStation:
    id: str
    connector_type: str  # "AC 22 kW" / "DC 50 kW"
    power_kw: float
    location: str
    active: bool = True
    requires_approval: bool = False  # v0.2, BR-05


@dataclass
class Reservation:
    id: str
    user_id: str
    station_id: str
    start_time: datetime
    end_time: datetime
    created_at: datetime
    state: State = State.DRAFT


class ReservationError(Exception):
    """Odmítnutá operace. `code` je stabilní kód (kontrolují ho testy), `message` vysvětlení."""

    def __init__(self, code: str, message: str, related: Optional[List[str]] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.related = related or []  # id rezervací, se kterými je konflikt


class NotificationUnavailable(Exception):
    pass


class NotificationService:
    """Simulace externí Notification Service z C01 (e-mail přes HTTP, může být nedostupná)."""

    def __init__(self, available: bool = True):
        self.available = available
        self.delivered: List[dict] = []

    def send(self, to: str, subject: str, body: str) -> None:
        if not self.available:
            raise NotificationUnavailable("Notification Service is unavailable")
        self.delivered.append({"to": to, "subject": subject, "body": body})


SUBJECTS = {
    "CONFIRMED": "Rezervace {id} je potvrzená",
    "CANCELLED": "Rezervace {id} je zrušená",
    "REJECTED": "Rezervace {id} byla zamítnuta",
}


def parse_dt(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """BR-01: polootevřené intervaly [start, end) se překrývají, jen když sdílejí nějaký okamžik."""
    return a_start < b_end and b_start < a_end


def format_interval(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return f"{start:%Y-%m-%d %H:%M}–{end:%H:%M}"
    return f"{start:%Y-%m-%d %H:%M}–{end:%Y-%m-%d %H:%M}"


def utc_day(moment: datetime):
    """BR-04: kalendářní den = datum v UTC."""
    return moment.astimezone(UTC).date()


# =============================================================================
# C05 Detailed Design: přidělení stanice (Reservation allocation)
# =============================================================================


@dataclass(frozen=True)
class AllocationDecision:
    """Výsledek AllocationPolicy.check(): povoleno, nebo kód důvodu a konfliktní rezervace."""

    allowed: bool
    code: Optional[str] = None
    related: Tuple[str, ...] = ()

    @staticmethod
    def allow() -> "AllocationDecision":
        return AllocationDecision(True)

    @staticmethod
    def deny(code: str, related: Iterable[str] = ()) -> "AllocationDecision":
        return AllocationDecision(False, code, tuple(related))


ALLOCATION_MESSAGES = {
    "INACTIVE_STATION": "Stanice je mimo provoz.",
    "OVERLAP": "Stanice je v tomto čase obsazená potvrzenou rezervací (BR-02).",
    "DAILY_LIMIT": "Uživatel už má v tento den potvrzenou rezervaci (BR-04).",
}


class AllocationPolicy:
    """Rozhodne, zda se rezervace smí stát CONFIRMED (REQ-03, REQ-06; BR-02, BR-04).

    Čistá funkce nad daty: nic nemění, nic neukládá, nečte hodiny a nevolá služby.
    Pořadí kontrol je součástí kontraktu: provoz stanice, potom BR-02, potom BR-04.
    Ze vstupu `others` bere v úvahu jen CONFIRMED rezervace různé od kandidáta.
    """

    def check(
        self, candidate: Reservation, station: ChargingStation, others: Iterable[Reservation]
    ) -> AllocationDecision:
        if not station.active:
            return AllocationDecision.deny("INACTIVE_STATION")
        confirmed = [r for r in others if r.id != candidate.id and r.state == State.CONFIRMED]
        overlapping = [
            r.id
            for r in confirmed
            if r.station_id == candidate.station_id
            and overlaps(candidate.start_time, candidate.end_time, r.start_time, r.end_time)
        ]
        if overlapping:
            return AllocationDecision.deny("OVERLAP", overlapping)
        day = utc_day(candidate.start_time)
        same_day = [
            r.id for r in confirmed if r.user_id == candidate.user_id and utc_day(r.start_time) == day
        ]
        if same_day:
            return AllocationDecision.deny("DAILY_LIMIT", same_day)
        return AllocationDecision.allow()


class ReservationRepository(Protocol):
    """Kontrakt úložiště rezervací. Dnes v paměti, v CP1 nad PostgreSQL."""

    def get(self, reservation_id: str) -> Optional[Reservation]: ...

    def add(self, reservation: Reservation) -> None: ...

    def all(self) -> List[Reservation]: ...

    def relevant_for(self, candidate: Reservation) -> List[Reservation]:
        """CONFIRMED rezervace téže stanice nebo téhož uživatele, bez kandidáta."""
        ...


class InMemoryReservationRepository:
    def __init__(self) -> None:
        self.items: Dict[str, Reservation] = {}

    def get(self, reservation_id: str) -> Optional[Reservation]:
        return self.items.get(reservation_id)

    def add(self, reservation: Reservation) -> None:
        self.items[reservation.id] = reservation

    def all(self) -> List[Reservation]:
        return list(self.items.values())

    def relevant_for(self, candidate: Reservation) -> List[Reservation]:
        return [
            r
            for r in self.items.values()
            if r.id != candidate.id
            and r.state == State.CONFIRMED
            and (r.station_id == candidate.station_id or r.user_id == candidate.user_id)
        ]


class Notifier(Protocol):
    """Kontrakt Notification Service: odeslat e-mail, nebo vyhodit výjimku."""

    def send(self, to: str, subject: str, body: str) -> None: ...


class ChargingReservationSystem:
    """Systém v paměti. Jeden zámek serializuje všechny operace (REQ-04, souběh Cancel × Confirm)."""

    def __init__(
        self,
        clock: Optional[Callable[[], datetime]] = None,
        notifier: Optional[Notifier] = None,
        repository: Optional[ReservationRepository] = None,
        policy: Optional[AllocationPolicy] = None,
    ):
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self.notifier = notifier or NotificationService()
        self.repository = repository or InMemoryReservationRepository()
        self.policy = policy or AllocationPolicy()
        self.users: Dict[str, User] = {}
        self.stations: Dict[str, ChargingStation] = {}
        self.notifications: List[dict] = []  # pokusy o e-mail (REQ-09)
        self._outbox: List[dict] = []  # e-maily čekající na odeslání po uvolnění zámku
        self._seq = 0
        self.after_checks: Optional[Callable[[], None]] = None  # háček pro test souběhu (REQ-04)

    @property
    def reservations(self) -> Dict[str, Reservation]:
        """Pohled jen pro čtení (testy, ukázka); jde přes kontrakt repository, ne přes jeho vnitřek."""
        return {r.id: r for r in self.repository.all()}

    def now(self) -> datetime:
        return self._clock()

    def seed_demo(self) -> None:
        self.users = {
            "alice": User("alice", Role.EMPLOYEE, "alice@example.com", "Škoda Enyaq"),
            "bob": User("bob", Role.EMPLOYEE, "bob@example.com", "Hyundai Kona Electric"),
            "admin": User("admin", Role.ADMIN, "admin@example.com"),
        }
        self.stations = {
            "AC-1": ChargingStation("AC-1", "AC 22 kW", 22, "Parkoviště P1, stání 1"),
            "DC-1": ChargingStation(
                "DC-1", "DC 50 kW", 50, "Parkoviště P1, stání 2", requires_approval=True
            ),
            "AC-2": ChargingStation("AC-2", "AC 22 kW", 22, "Parkoviště P2, stání 1", active=False),
        }

    # ---- OP-01 Create Reservation (REQ-01) -----------------------------------
    def create(self, user_id: str, station_id: str, start: datetime, end: datetime) -> Reservation:
        with self._lock:
            self._expire_overdue()
            self._require_role(user_id, Role.EMPLOYEE)
            self._get_station(station_id)  # stanice mimo provoz je povolená, DRAFT je jen záměr
            self._validate_interval(start, end)
            if not self.now() < start:
                raise ReservationError("START_IN_PAST", "Začátek rezervace musí být v budoucnosti (REQ-01).")
            # Překryv ani denní limit se tady nekontrolují: DRAFT stanici neblokuje.
            self._seq += 1
            reservation = Reservation(
                id=f"R{self._seq:04d}",
                user_id=user_id,
                station_id=station_id,
                start_time=start,
                end_time=end,
                created_at=self.now(),
            )
            self.repository.add(reservation)
            return reservation

    # ---- OP-02 Check Availability (REQ-02) -----------------------------------
    def check_availability(self, station_id: str, start: datetime, end: datetime) -> str:
        with self._lock:
            self._expire_overdue()
            station = self._get_station(station_id)
            self._validate_interval(start, end)
            if not station.active or self._confirmed_overlaps(station_id, start, end):
                return "UNAVAILABLE"
            return "AVAILABLE"

    # ---- OP-03 Confirm Reservation (REQ-03, REQ-03b, REQ-04) -----------------
    def confirm(self, user_id: str, reservation_id: str) -> Reservation:
        try:
            with self._lock:
                self._expire_overdue()
                self._require_role(user_id, Role.EMPLOYEE)
                reservation = self._get_reservation(reservation_id)
                if reservation.user_id != user_id:
                    raise ReservationError("UNAUTHORIZED", "Potvrdit může jen vlastník rezervace.")
                if reservation.state != State.DRAFT:
                    raise ReservationError(
                        "INVALID_STATE", f"Potvrdit lze jen DRAFT, rezervace je {reservation.state.value}."
                    )
                if not self.now() < reservation.start_time:
                    raise ReservationError("TOO_LATE", "Rezervace už začala, potvrdit ji nelze (REQ-03).")
                if self.stations[reservation.station_id].requires_approval:
                    # v0.2 (REQ-03b, BR-05): jen žádost o schválení, stanice se ještě neblokuje
                    reservation.state = State.PENDING_APPROVAL
                    return reservation
                self._check_allocation(reservation)
                if self.after_checks:
                    self.after_checks()
                reservation.state = State.CONFIRMED
                self._queue_notification(reservation, "CONFIRMED")
                return reservation
        finally:
            self._dispatch_notifications()  # e-mail až mimo zámek

    # ---- OP-05 Approve / Reject Reservation (v0.2: REQ-06, REQ-07, REQ-08) ---
    def approve(self, user_id: str, reservation_id: str) -> Reservation:
        try:
            with self._lock:
                self._expire_overdue()
                self._require_role(user_id, Role.ADMIN)
                reservation = self._get_reservation(reservation_id)
                self._require_pending(reservation)
                self._check_allocation(reservation)
                reservation.state = State.CONFIRMED
                self._queue_notification(reservation, "CONFIRMED")
                return reservation
        finally:
            self._dispatch_notifications()  # e-mail až mimo zámek

    def reject(self, user_id: str, reservation_id: str) -> Reservation:
        try:
            with self._lock:
                self._expire_overdue()
                self._require_role(user_id, Role.ADMIN)
                reservation = self._get_reservation(reservation_id)
                self._require_pending(reservation)
                reservation.state = State.REJECTED
                self._queue_notification(reservation, "REJECTED")
                return reservation
        finally:
            self._dispatch_notifications()  # e-mail až mimo zámek

    # ---- OP-04 Cancel Reservation (REQ-05) -----------------------------------
    def cancel(self, user_id: str, reservation_id: str) -> Reservation:
        try:
            with self._lock:
                self._expire_overdue()
                user = self._require_user(user_id)
                reservation = self._get_reservation(reservation_id)
                if user.role == Role.EMPLOYEE and reservation.user_id != user_id:
                    raise ReservationError("UNAUTHORIZED", "Zaměstnanec může zrušit jen vlastní rezervaci.")
                if reservation.state == State.CANCELLED:
                    return reservation  # idempotentní úspěch (BR-03): nic se nemění, e-mail se neposílá
                if reservation.state not in CANCELLABLE_STATES:
                    raise ReservationError(
                        "INVALID_STATE", f"Rezervaci ve stavu {reservation.state.value} nelze zrušit (BR-03)."
                    )
                if not self.now() < reservation.start_time:
                    raise ReservationError("TOO_LATE", "Zrušit lze jen před začátkem rezervace (BR-03).")
                reservation.state = State.CANCELLED
                self._queue_notification(reservation, "CANCELLED")
                return reservation
        finally:
            self._dispatch_notifications()  # e-mail až mimo zámek

    def list_reservations(self) -> List[Reservation]:
        with self._lock:
            self._expire_overdue()
            return self.repository.all()

    # ---- pravidla -----------------------------------------------------------
    def _expire_overdue(self) -> None:
        """BR-06: žádost, o které nikdo nerozhodl do začátku rezervace, vyprší.

        Vyhodnocuje se na začátku každé operace (líně), časovač zatím není (driver D3 pro C03).
        """
        now = self.now()
        for reservation in self.repository.all():
            if reservation.state == State.PENDING_APPROVAL and now >= reservation.start_time:
                reservation.state = State.EXPIRED

    def _check_allocation(self, reservation: Reservation) -> None:
        """Podmínky, za kterých se rezervace smí stát CONFIRMED, rozhoduje AllocationPolicy."""
        decision = self.policy.check(
            reservation, self.stations[reservation.station_id], self.repository.relevant_for(reservation)
        )
        if not decision.allowed:
            raise ReservationError(decision.code, ALLOCATION_MESSAGES[decision.code], list(decision.related))

    def _confirmed_overlaps(
        self, station_id: str, start: datetime, end: datetime, ignore_id: Optional[str] = None
    ) -> List[Reservation]:
        return [
            r
            for r in self.repository.all()
            if r.id != ignore_id
            and r.station_id == station_id
            and r.state == State.CONFIRMED
            and overlaps(start, end, r.start_time, r.end_time)
        ]

    def _validate_interval(self, start: datetime, end: datetime) -> None:
        if not start < end:
            raise ReservationError("INVALID_INTERVAL", "Začátek musí být před koncem (BR-01).")
        if end - start > MAX_DURATION:
            raise ReservationError("INVALID_DURATION", "Rezervace smí trvat nejvýše 4 hodiny (BR-04).")

    def _require_pending(self, reservation: Reservation) -> None:
        if reservation.state == State.EXPIRED:
            raise ReservationError(
                "EXPIRED", "Žádost vypršela: rezervace začala dřív, než o ní Facility admin rozhodl (BR-06)."
            )
        if reservation.state != State.PENDING_APPROVAL:
            raise ReservationError(
                "INVALID_STATE",
                f"Rozhodnout lze jen o PENDING_APPROVAL, rezervace je {reservation.state.value}.",
            )

    def _queue_notification(self, reservation: Reservation, event: str) -> None:
        """REQ-09: připraví e-mail vlastníkovi; volá se pod zámkem, odesílá se až po něm."""
        user = self.users[reservation.user_id]
        station = self.stations[reservation.station_id]
        self._outbox.append({
            "reservation_id": reservation.id,
            "event": event,
            "to": user.email,
            "subject": SUBJECTS[event].format(id=reservation.id),
            "body": (
                f"Stanice {station.id} ({station.connector_type}), "
                f"{format_interval(reservation.start_time, reservation.end_time)} UTC."
            ),
        })

    def _dispatch_notifications(self) -> None:
        """Odešle připravené e-maily mimo zámek. Žádná chyba služby nedoběhne k volajícímu."""
        with self._lock:
            pending, self._outbox = self._outbox, []
        for mail in pending:
            status = "SENT"
            try:
                self.notifier.send(mail["to"], mail["subject"], mail["body"])
            except Exception:  # NotificationUnavailable, timeout, chyba sítě...
                status = "FAILED"
            entry = {k: mail[k] for k in ("reservation_id", "event", "to", "subject")}
            entry["status"] = status
            with self._lock:
                self.notifications.append(entry)

    # ---- přístup k datům ----------------------------------------------------
    def _require_user(self, user_id: str) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise ReservationError("UNAUTHORIZED", "Neznámý uživatel.")
        return user

    def _require_role(self, user_id: str, role: Role) -> User:
        user = self._require_user(user_id)
        if user.role != role:
            if role == Role.EMPLOYEE:
                raise ReservationError("UNAUTHORIZED", "Tuto operaci provádí zaměstnanec, ne Facility admin.")
            raise ReservationError("UNAUTHORIZED", "Schvalovat a zamítat může jen Facility admin.")
        return user

    def _get_station(self, station_id: str) -> ChargingStation:
        station = self.stations.get(station_id)
        if station is None:
            raise ReservationError("UNKNOWN_STATION", "Stanice neexistuje.")
        return station

    def _get_reservation(self, reservation_id: str) -> Reservation:
        reservation = self.repository.get(reservation_id)
        if reservation is None:
            raise ReservationError("UNKNOWN_RESERVATION", "Rezervace neexistuje.")
        return reservation

    def to_dict(self, reservation: Reservation) -> dict:
        return {
            "id": reservation.id,
            "user_id": reservation.user_id,
            "station_id": reservation.station_id,
            "start_time": reservation.start_time.isoformat(),
            "end_time": reservation.end_time.isoformat(),
            "state": reservation.state.value,
            "created_at": reservation.created_at.isoformat(),
        }


# =============================================================================
# Příklady ověření (python reservation.py test). Stejné příklady běží v app/index.html.
# =============================================================================

DEMO_NOW = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)


class Clock:
    def __init__(self, instant: datetime):
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant


def demo_system() -> Tuple[ChargingReservationSystem, Clock]:
    clock = Clock(DEMO_NOW)
    system = ChargingReservationSystem(clock=clock)
    system.seed_demo()
    return system, clock


def at(hhmm: str, day: int = 11) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC)


def _error(fn: Callable[[], object]) -> Optional[ReservationError]:
    try:
        fn()
    except ReservationError as exc:
        return exc
    return None


def _code(fn: Callable[[], object]) -> Optional[str]:
    exc = _error(fn)
    return exc.code if exc else None


def _confirmed(system: ChargingReservationSystem, user: str, station: str, start: datetime, end: datetime):
    reservation = system.create(user, station, start, end)
    system.confirm(user, reservation.id)
    return reservation


def _pending(system: ChargingReservationSystem, user: str, start: datetime, end: datetime):
    reservation = system.create(user, "DC-1", start, end)
    system.confirm(user, reservation.id)
    return reservation


Check = Tuple[bool, str]


# ---- OP-01 -------------------------------------------------------------------
def c_create_ok() -> Check:
    s, _ = demo_system()
    r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
    return r.state == State.DRAFT and r.user_id == "alice", r.state.value


def c_create_drafts_may_overlap() -> Check:
    s, _ = demo_system()
    a = s.create("alice", "AC-1", at("10:00"), at("11:00"))
    b = s.create("bob", "AC-1", at("10:00"), at("11:00"))
    return a.state == b.state == State.DRAFT, f"{a.state.value}, {b.state.value}"


def c_create_start_equals_end() -> Check:
    s, _ = demo_system()
    code = _code(lambda: s.create("alice", "AC-1", at("10:00"), at("10:00")))
    return code == "INVALID_INTERVAL", str(code)


def c_create_exactly_4h() -> Check:
    s, _ = demo_system()
    r = s.create("alice", "AC-1", at("09:00"), at("13:00"))
    return r.state == State.DRAFT, r.state.value


def c_create_over_4h() -> Check:
    s, _ = demo_system()
    code = _code(lambda: s.create("alice", "AC-1", at("09:00"), at("13:30")))
    return code == "INVALID_DURATION", str(code)


def c_create_in_past() -> Check:
    s, _ = demo_system()
    code = _code(lambda: s.create("alice", "AC-1", at("07:00"), at("08:00")))
    return code == "START_IN_PAST", str(code)


def c_create_unknown_station() -> Check:
    s, _ = demo_system()
    code = _code(lambda: s.create("alice", "XX-9", at("10:00"), at("11:00")))
    return code == "UNKNOWN_STATION", str(code)


def c_create_by_admin() -> Check:
    s, _ = demo_system()
    code = _code(lambda: s.create("admin", "AC-1", at("10:00"), at("11:00")))
    return code == "UNAUTHORIZED", str(code)


# ---- OP-02 -------------------------------------------------------------------
def _with_confirmed_10_11() -> ChargingReservationSystem:
    s, _ = demo_system()
    _confirmed(s, "alice", "AC-1", at("10:00"), at("11:00"))
    return s


def c_avail_adjacent_before() -> Check:
    result = _with_confirmed_10_11().check_availability("AC-1", at("09:00"), at("10:00"))
    return result == "AVAILABLE", result


def c_avail_overlap() -> Check:
    result = _with_confirmed_10_11().check_availability("AC-1", at("10:30"), at("11:30"))
    return result == "UNAVAILABLE", result


def c_avail_adjacent_after() -> Check:
    result = _with_confirmed_10_11().check_availability("AC-1", at("11:00"), at("12:00"))
    return result == "AVAILABLE", result


def c_avail_draft_does_not_block() -> Check:
    s, _ = demo_system()
    s.create("bob", "AC-1", at("14:00"), at("15:00"))
    result = s.check_availability("AC-1", at("14:00"), at("15:00"))
    return result == "AVAILABLE", result


def c_avail_inactive_station() -> Check:
    s, _ = demo_system()
    result = s.check_availability("AC-2", at("10:00"), at("11:00"))
    return result == "UNAVAILABLE", result


# ---- OP-03 -------------------------------------------------------------------
def c_confirm_ok() -> Check:
    s, _ = demo_system()
    r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
    s.confirm("alice", r.id)
    mail = s.notifications[-1] if s.notifications else {}
    ok = (
        r.state == State.CONFIRMED
        and mail.get("event") == "CONFIRMED"
        and mail.get("to") == "alice@example.com"
        and mail.get("status") == "SENT"
    )
    return ok, f"{r.state.value}, e-mail {mail.get('status')}"


def c_confirm_overlap() -> Check:
    s, _ = demo_system()
    blocker = _confirmed(s, "bob", "AC-1", at("10:00"), at("11:00"))
    r = s.create("alice", "AC-1", at("10:30"), at("11:30"))
    exc = _error(lambda: s.confirm("alice", r.id))
    ok = exc is not None and exc.code == "OVERLAP" and exc.related == [blocker.id] and r.state == State.DRAFT
    return ok, f"{exc.code if exc else None} {exc.related if exc else ''}, {r.state.value}"


def c_confirm_adjacent() -> Check:
    s, _ = demo_system()
    _confirmed(s, "bob", "AC-1", at("09:00"), at("11:00"))
    r = s.create("alice", "AC-1", at("11:00"), at("13:00"))
    s.confirm("alice", r.id)
    return r.state == State.CONFIRMED, r.state.value


def c_confirm_daily_limit() -> Check:
    s, _ = demo_system()
    first = _confirmed(s, "alice", "AC-1", at("09:00"), at("10:00"))
    second = s.create("alice", "AC-1", at("15:00"), at("16:00"))
    exc = _error(lambda: s.confirm("alice", second.id))
    ok = exc is not None and exc.code == "DAILY_LIMIT" and exc.related == [first.id] and second.state == State.DRAFT
    return ok, f"{exc.code if exc else None}, {second.state.value}"


def c_confirm_next_day() -> Check:
    s, _ = demo_system()
    _confirmed(s, "alice", "AC-1", at("09:00"), at("10:00"))
    r = s.create("alice", "AC-1", at("15:00", day=12), at("16:00", day=12))
    s.confirm("alice", r.id)
    return r.state == State.CONFIRMED, r.state.value


def c_confirm_inactive_station() -> Check:
    s, _ = demo_system()
    r = s.create("alice", "AC-2", at("10:00"), at("11:00"))
    code = _code(lambda: s.confirm("alice", r.id))
    return code == "INACTIVE_STATION" and r.state == State.DRAFT, f"{code}, {r.state.value}"


def c_confirm_foreign() -> Check:
    s, _ = demo_system()
    r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
    code = _code(lambda: s.confirm("bob", r.id))
    return code == "UNAUTHORIZED" and r.state == State.DRAFT, f"{code}, {r.state.value}"


def c_confirm_twice() -> Check:
    s, _ = demo_system()
    r = _confirmed(s, "alice", "AC-1", at("10:00"), at("11:00"))
    code = _code(lambda: s.confirm("alice", r.id))
    return code == "INVALID_STATE" and r.state == State.CONFIRMED, f"{code}, {r.state.value}"


def c_confirm_after_start() -> Check:
    s, clock = demo_system()
    r = s.create("alice", "AC-1", at("09:00"), at("10:00"))
    clock.instant = at("09:00")
    code = _code(lambda: s.confirm("alice", r.id))
    return code == "TOO_LATE" and r.state == State.DRAFT, f"{code}, {r.state.value}"


def c_confirm_concurrent() -> Check:
    s, _ = demo_system()
    a = s.create("alice", "AC-1", at("18:00"), at("19:00"))
    b = s.create("bob", "AC-1", at("18:00"), at("19:00"))
    s.after_checks = lambda: time.sleep(0.05)  # druhý požadavek přijde, zatímco první dokončuje
    results: List[str] = []

    def run(user_id: str, reservation_id: str) -> None:
        try:
            results.append(s.confirm(user_id, reservation_id).state.value)
        except ReservationError as exc:
            results.append(exc.code)

    threads = [
        threading.Thread(target=run, args=("alice", a.id)),
        threading.Thread(target=run, args=("bob", b.id)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return sorted(results) == ["CONFIRMED", "OVERLAP"], str(results)


# ---- OP-04 -------------------------------------------------------------------
def c_cancel_draft() -> Check:
    s, _ = demo_system()
    r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
    s.cancel("alice", r.id)
    return r.state == State.CANCELLED, r.state.value


def c_cancel_confirmed_frees_station() -> Check:
    s, _ = demo_system()
    r = _confirmed(s, "alice", "AC-1", at("10:00"), at("11:00"))
    s.cancel("alice", r.id)
    result = s.check_availability("AC-1", at("10:00"), at("11:00"))
    mail = s.notifications[-1]
    ok = r.state == State.CANCELLED and result == "AVAILABLE" and mail["event"] == "CANCELLED"
    return ok, f"{r.state.value}, {result}, e-mail {mail['event']}"


def c_cancel_at_start() -> Check:
    s, clock = demo_system()
    r = _confirmed(s, "alice", "AC-1", at("09:00"), at("10:00"))
    clock.instant = at("09:00")
    code = _code(lambda: s.cancel("alice", r.id))
    return code == "TOO_LATE" and r.state == State.CONFIRMED, f"{code}, {r.state.value}"


def c_cancel_twice() -> Check:
    s, _ = demo_system()
    r = _confirmed(s, "alice", "AC-1", at("10:00"), at("11:00"))
    s.cancel("alice", r.id)
    mails = len(s.notifications)
    again = s.cancel("alice", r.id)
    return again.state == State.CANCELLED and len(s.notifications) == mails, again.state.value


def c_cancel_foreign() -> Check:
    s, _ = demo_system()
    r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
    code = _code(lambda: s.cancel("bob", r.id))
    return code == "UNAUTHORIZED" and r.state == State.DRAFT, f"{code}, {r.state.value}"


def c_cancel_by_admin() -> Check:
    s, _ = demo_system()
    r = _confirmed(s, "alice", "AC-1", at("10:00"), at("11:00"))
    s.cancel("admin", r.id)
    return r.state == State.CANCELLED, r.state.value


# ---- REQ-09 ------------------------------------------------------------------
def c_notification_unavailable() -> Check:
    s, _ = demo_system()
    s.notifier.available = False
    r = s.create("alice", "AC-1", at("10:00"), at("11:00"))
    s.confirm("alice", r.id)
    mail = s.notifications[-1]
    return r.state == State.CONFIRMED and mail["status"] == "FAILED", f"{r.state.value}, e-mail {mail['status']}"


# ---- v0.2 OP-05 ----------------------------------------------------------------
def c_v02_confirm_requests_approval() -> Check:
    s, _ = demo_system()
    r = _pending(s, "alice", at("10:00"), at("11:00"))
    return r.state == State.PENDING_APPROVAL and not s.notifications, r.state.value


def c_v02_pending_does_not_block() -> Check:
    s, _ = demo_system()
    _pending(s, "alice", at("10:00"), at("11:00"))
    result = s.check_availability("DC-1", at("10:00"), at("11:00"))
    return result == "AVAILABLE", result


def c_v02_approve() -> Check:
    s, _ = demo_system()
    r = _pending(s, "alice", at("10:00"), at("11:00"))
    s.approve("admin", r.id)
    mail = s.notifications[-1]
    ok = r.state == State.CONFIRMED and mail["event"] == "CONFIRMED" and mail["status"] == "SENT"
    return ok, f"{r.state.value}, e-mail {mail['event']}"


def c_v02_approve_by_employee() -> Check:
    s, _ = demo_system()
    r = _pending(s, "alice", at("10:00"), at("11:00"))
    code = _code(lambda: s.approve("alice", r.id))
    return code == "UNAUTHORIZED" and r.state == State.PENDING_APPROVAL, f"{code}, {r.state.value}"


def c_v02_reject() -> Check:
    s, _ = demo_system()
    r = _pending(s, "bob", at("12:00"), at("13:00"))
    s.reject("admin", r.id)
    mail = s.notifications[-1]
    return r.state == State.REJECTED and mail["event"] == "REJECTED", f"{r.state.value}, e-mail {mail['event']}"


def c_v02_approve_overlap() -> Check:
    s, _ = demo_system()
    first = _pending(s, "alice", at("10:00"), at("11:00"))
    second = _pending(s, "bob", at("10:30"), at("11:30"))
    s.approve("admin", first.id)
    exc = _error(lambda: s.approve("admin", second.id))
    ok = (
        exc is not None
        and exc.code == "OVERLAP"
        and exc.related == [first.id]
        and second.state == State.PENDING_APPROVAL
    )
    return ok, f"{exc.code if exc else None}, {second.state.value}"


def c_v02_approve_daily_limit() -> Check:
    s, _ = demo_system()
    _confirmed(s, "alice", "AC-1", at("08:30"), at("09:30"))
    r = _pending(s, "alice", at("14:00"), at("15:00"))
    code = _code(lambda: s.approve("admin", r.id))
    return code == "DAILY_LIMIT" and r.state == State.PENDING_APPROVAL, f"{code}, {r.state.value}"


def c_v02_delayed_approval() -> Check:
    s, clock = demo_system()
    r = _pending(s, "alice", at("10:00"), at("11:00"))
    clock.instant = at("09:59")
    s.approve("admin", r.id)
    return r.state == State.CONFIRMED, r.state.value


def c_v02_expired_at_start() -> Check:
    s, clock = demo_system()
    r = _pending(s, "alice", at("10:00"), at("11:00"))
    clock.instant = at("10:00")
    code = _code(lambda: s.approve("admin", r.id))
    return code == "EXPIRED" and r.state == State.EXPIRED, f"{code}, {r.state.value}"


def c_v02_cancel_pending() -> Check:
    s, _ = demo_system()
    r = _pending(s, "alice", at("10:00"), at("11:00"))
    s.cancel("alice", r.id)
    return r.state == State.CANCELLED, r.state.value


VERIFICATION: List[Tuple[str, List[Tuple[str, Callable[[], Check]]]]] = [
    ("OP-01 Create Reservation", [
        ("platný požadavek -> DRAFT", c_create_ok),
        ("dva DRAFTy na stejný čas -> vzniknou oba", c_create_drafts_may_overlap),
        ("začátek == konec -> INVALID_INTERVAL", c_create_start_equals_end),
        ("přesně 4 hodiny -> DRAFT", c_create_exactly_4h),
        ("4,5 hodiny -> INVALID_DURATION", c_create_over_4h),
        ("začátek v minulosti -> START_IN_PAST", c_create_in_past),
        ("neznámá stanice -> UNKNOWN_STATION", c_create_unknown_station),
        ("Facility admin rezervaci nevytváří -> UNAUTHORIZED", c_create_by_admin),
    ]),
    ("OP-02 Check Availability (CONFIRMED [10:00, 11:00))", [
        ("dotaz [09:00, 10:00) -> AVAILABLE", c_avail_adjacent_before),
        ("dotaz [10:30, 11:30) -> UNAVAILABLE", c_avail_overlap),
        ("dotaz [11:00, 12:00) -> AVAILABLE", c_avail_adjacent_after),
        ("DRAFT stanici neblokuje -> AVAILABLE", c_avail_draft_does_not_block),
        ("stanice mimo provoz -> UNAVAILABLE", c_avail_inactive_station),
    ]),
    ("OP-03 Confirm Reservation", [
        ("volný DRAFT -> CONFIRMED + e-mail", c_confirm_ok),
        ("překryv s potvrzenou -> OVERLAP, zůstává DRAFT", c_confirm_overlap),
        ("navazující [11:00, 13:00) -> CONFIRMED", c_confirm_adjacent),
        ("druhá potvrzená v témže dni -> DAILY_LIMIT", c_confirm_daily_limit),
        ("další den -> CONFIRMED", c_confirm_next_day),
        ("stanice mimo provoz -> INACTIVE_STATION", c_confirm_inactive_station),
        ("cizí rezervace -> UNAUTHORIZED", c_confirm_foreign),
        ("už potvrzená -> INVALID_STATE", c_confirm_twice),
        ("po začátku rezervace -> TOO_LATE", c_confirm_after_start),
        ("dvě souběžná potvrzení -> právě jedno CONFIRMED", c_confirm_concurrent),
    ]),
    ("OP-04 Cancel Reservation", [
        ("DRAFT před začátkem -> CANCELLED", c_cancel_draft),
        ("CONFIRMED -> CANCELLED, stanice volná, e-mail", c_cancel_confirmed_frees_station),
        ("v okamžiku začátku -> TOO_LATE, zůstává CONFIRMED", c_cancel_at_start),
        ("opakované zrušení -> úspěch beze změny", c_cancel_twice),
        ("cizí rezervace zaměstnancem -> UNAUTHORIZED", c_cancel_foreign),
        ("Facility admin zruší cizí rezervaci -> CANCELLED", c_cancel_by_admin),
    ]),
    ("REQ-09 Notifikace", [
        ("Notification Service nedostupná -> CONFIRMED, e-mail FAILED", c_notification_unavailable),
    ]),
    ("v0.2 OP-05 Approve / Reject Reservation", [
        ("Confirm na DC-1 -> PENDING_APPROVAL, bez e-mailu", c_v02_confirm_requests_approval),
        ("PENDING_APPROVAL stanici neblokuje -> AVAILABLE", c_v02_pending_does_not_block),
        ("schválení -> CONFIRMED + e-mail", c_v02_approve),
        ("schvaluje zaměstnanec -> UNAUTHORIZED", c_v02_approve_by_employee),
        ("zamítnutí -> REJECTED + e-mail", c_v02_reject),
        ("mezitím potvrzený překryv -> OVERLAP, zůstává PENDING", c_v02_approve_overlap),
        ("denní limit při schválení -> DAILY_LIMIT", c_v02_approve_daily_limit),
        ("zpožděné schválení v 09:59 -> CONFIRMED", c_v02_delayed_approval),
        ("rozhodnutí v 10:00 (začátek) -> EXPIRED", c_v02_expired_at_start),
        ("zrušení PENDING_APPROVAL -> CANCELLED", c_v02_cancel_pending),
    ]),
]


def run_verification() -> int:
    """Spustí příklady ověření ze specifikace. Vrací 0, jen když všechny projdou."""
    total = passed = 0
    print("Příklady ověření: Specification Baseline v0.2 (čas 2026-10-11 08:00 UTC)\n")
    for group, checks in VERIFICATION:
        print(group)
        for name, check in checks:
            total += 1
            try:
                ok, detail = check()
            except Exception as exc:  # neočekávaná výjimka = selhání příkladu
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            passed += ok
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  (výsledek: {detail})"))
        print()
    print(f"{passed}/{total} příkladů prošlo.")
    return 0 if passed == total else 1


def demo() -> None:
    s, _ = demo_system()
    print("Ukázka C02 · simulovaný čas 2026-10-11 08:00 UTC")
    print("Stanice: AC-1 (AC 22 kW), DC-1 (DC 50 kW, schvaluje Facility admin), AC-2 (mimo provoz)\n")

    def step(label: str, fn: Callable[[], object]) -> None:
        try:
            result = fn()
            if isinstance(result, Reservation):
                result = f"{result.id} {result.state.value}"
            print(f"  [OK]         {label} -> {result}")
        except ReservationError as exc:
            related = f" ({', '.join(exc.related)})" if exc.related else ""
            print(f"  [ODMÍTNUTO]  {label} -> {exc.code}{related}: {exc.message}")

    step("alice vytvoří AC-1 10:00-11:00", lambda: s.create("alice", "AC-1", at("10:00"), at("11:00")))
    step("dostupnost AC-1 10:00-11:00", lambda: s.check_availability("AC-1", at("10:00"), at("11:00")))
    step("alice potvrdí R0001", lambda: s.confirm("alice", "R0001"))
    step("dostupnost AC-1 10:30-11:30", lambda: s.check_availability("AC-1", at("10:30"), at("11:30")))
    step("bob vytvoří AC-1 10:30-11:30", lambda: s.create("bob", "AC-1", at("10:30"), at("11:30")))
    step("bob potvrdí R0002", lambda: s.confirm("bob", "R0002"))
    step("bob vytvoří DC-1 12:00-13:00", lambda: s.create("bob", "DC-1", at("12:00"), at("13:00")))
    step("bob potvrdí R0003", lambda: s.confirm("bob", "R0003"))
    step("alice schválí R0003", lambda: s.approve("alice", "R0003"))
    step("admin schválí R0003", lambda: s.approve("admin", "R0003"))
    step("alice zruší R0001", lambda: s.cancel("alice", "R0001"))
    step("dostupnost AC-1 10:30-11:30", lambda: s.check_availability("AC-1", at("10:30"), at("11:30")))

    print("\nE-maily (Notification Service):")
    for mail in s.notifications:
        print(f"  {mail['status']:<6} {mail['to']:<18} {mail['subject']}")


def main(argv: List[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) >= 2 and argv[1] == "test":
        return run_verification()
    if len(argv) >= 2 and argv[1] == "demo":
        demo()
        return 0
    print("Použití: python reservation.py [test|demo]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
