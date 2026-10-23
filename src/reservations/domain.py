"""Doménové pojmy (C03 C1) a Allocation Policy (C03 G2, C05).

Modul nezávisí na databázi, HTTP ani Notification Service. AllocationPolicy je převzatá
z reservation.py (C05) beze změny logiky.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, List, Optional, Tuple

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
    id: Optional[int]  # přidělí úložiště při uložení
    user_id: str
    station_id: str
    start_time: datetime
    end_time: datetime
    created_at: datetime
    state: State = State.DRAFT


class ReservationError(Exception):
    """Odmítnutá operace. `code` je stabilní kód (kontrolují ho testy), `message` vysvětlení."""

    def __init__(self, code: str, message: str, related: Optional[List[int]] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.related = related or []  # id rezervací, se kterými je konflikt


class AllocationConflict(ReservationError):
    """Zápis CONFIRMED odmítla databáze (ADR-01): souběžné potvrzení bylo zapsáno dřív."""


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """BR-01: polootevřené intervaly [start, end) se překrývají, jen když sdílejí nějaký okamžik."""
    return a_start < b_end and b_start < a_end


def utc_day(moment: datetime):
    """BR-04: kalendářní den = datum v UTC."""
    return moment.astimezone(UTC).date()


@dataclass(frozen=True)
class AllocationDecision:
    """Výsledek AllocationPolicy.check(): povoleno, nebo kód důvodu a konfliktní rezervace."""

    allowed: bool
    code: Optional[str] = None
    related: Tuple[int, ...] = ()

    @staticmethod
    def allow() -> "AllocationDecision":
        return AllocationDecision(True)

    @staticmethod
    def deny(code: str, related: Iterable[int] = ()) -> "AllocationDecision":
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
