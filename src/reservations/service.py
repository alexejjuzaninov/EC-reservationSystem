"""Reservation Management (C03 G2): oprávnění, životní cyklus rezervace, vypršení žádostí.

Vlastní všechny přechody stavů (C03 G3). Pravidla alokace vyhodnocuje AllocationPolicy,
invarianty BR-02 a BR-04 při souběhu zaručuje schéma databáze za ReservationRepository
(ADR-01). Kontroly, kódy chyb a jejich pořadí jsou stejné jako v aplikaci C02 (reservation.py).
"""
import functools
from datetime import datetime
from typing import Callable, List, Optional, Protocol

from .domain import (
    ALLOCATION_MESSAGES,
    CANCELLABLE_STATES,
    MAX_DURATION,
    UTC,
    AllocationPolicy,
    ChargingStation,
    Reservation,
    ReservationError,
    Role,
    StaleState,
    State,
    User,
    overlaps,
)

OPERATION_ATTEMPTS = 3  # operace se při souběžné změně téže rezervace opakuje (BR-03)

SUBJECTS = {
    "CONFIRMED": "Rezervace {id} je potvrzená",
    "CANCELLED": "Rezervace {id} je zrušená",
    "REJECTED": "Rezervace {id} byla zamítnuta",
}


class ReservationRepository(Protocol):
    """Kontrakt Reservation Store. Implementace: store.SqlReservationRepository."""

    def user(self, user_id: str) -> Optional[User]: ...

    def station(self, station_id: str) -> Optional[ChargingStation]: ...

    def get(self, reservation_id: int) -> Optional[Reservation]: ...

    def add(self, reservation: Reservation) -> Reservation:
        """Uloží novou rezervaci a vrátí ji s přiděleným id."""
        ...

    def save(self, reservation: Reservation, expected: State) -> None:
        """Zapíše stav rezervace, jen pokud je v úložišti pořád `expected`, jinak StaleState.

        Porušení BR-02 / BR-04 v databázi → AllocationConflict.
        """
        ...

    def relevant_for(self, candidate: Reservation) -> List[Reservation]:
        """CONFIRMED rezervace téže stanice nebo téhož uživatele, bez kandidáta."""
        ...

    def confirmed_for_station(self, station_id: str) -> List[Reservation]: ...

    def expire_pending(self, now: datetime) -> None:
        """BR-06: PENDING_APPROVAL, jejichž začátek nastal, převede na EXPIRED."""
        ...


class Notifier(Protocol):
    """Kontrakt Notification Integration: doručí e-mail; žádná chyba služby nedoběhne k volajícímu."""

    def send(self, to: str, subject: str, body: str) -> None: ...


def serialized(operation):
    """BR-03: operace nad rezervací se chovají, jako by běžely jedna po druhé.

    Když úložiště při zápisu zjistí, že stav mezitím změnila jiná operace (StaleState), operace
    se provede znovu od začátku nad aktuálním stavem; uvidí tak výsledek té dřívější.
    """

    @functools.wraps(operation)
    def run(self, *args, **kwargs):
        for attempt in range(1, OPERATION_ATTEMPTS + 1):
            try:
                return operation(self, *args, **kwargs)
            except StaleState:
                if attempt == OPERATION_ATTEMPTS:
                    raise ReservationError(
                        "INVALID_STATE", "Rezervaci mezitím změnila jiná operace, zkuste to znovu."
                    ) from None

    return run


class ReservationService:
    def __init__(
        self,
        repository: ReservationRepository,
        notifier: Notifier,
        policy: Optional[AllocationPolicy] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        self.repository = repository
        self.notifier = notifier
        self.policy = policy or AllocationPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    def now(self) -> datetime:
        return self._clock()

    # ---- OP-01 Create Reservation (REQ-01) -----------------------------------
    def create(self, user_id: str, station_id: str, start: datetime, end: datetime) -> Reservation:
        self.repository.expire_pending(self.now())
        self._require_role(user_id, Role.EMPLOYEE)
        self._get_station(station_id)  # stanice mimo provoz je povolená, DRAFT je jen záměr
        self._validate_interval(start, end)
        if not self.now() < start:
            raise ReservationError("START_IN_PAST", "Začátek rezervace musí být v budoucnosti (REQ-01).")
        # Překryv ani denní limit se tady nekontrolují: DRAFT stanici neblokuje.
        reservation = Reservation(
            id=None,
            user_id=user_id,
            station_id=station_id,
            start_time=start,
            end_time=end,
            created_at=self.now(),
        )
        return self.repository.add(reservation)

    # ---- OP-02 Check Availability (REQ-02) -----------------------------------
    def check_availability(self, station_id: str, start: datetime, end: datetime) -> str:
        self.repository.expire_pending(self.now())
        station = self._get_station(station_id)
        self._validate_interval(start, end)
        # Jen provoz stanice a BR-02; BR-04 se týká uživatele, ne stanice (ADR-01).
        blocking = [
            r
            for r in self.repository.confirmed_for_station(station_id)
            if overlaps(start, end, r.start_time, r.end_time)
        ]
        if not station.active or blocking:
            return "UNAVAILABLE"
        return "AVAILABLE"

    # ---- OP-03 Confirm Reservation (REQ-03, REQ-03b, REQ-04) -----------------
    @serialized
    def confirm(self, user_id: str, reservation_id: int) -> Reservation:
        self.repository.expire_pending(self.now())
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
        if self._get_station(reservation.station_id).requires_approval:
            # v0.2 (REQ-03b, BR-05): jen žádost o schválení, stanice se ještě neblokuje
            reservation.state = State.PENDING_APPROVAL
            self.repository.save(reservation, expected=State.DRAFT)
            return reservation
        return self._allocate(reservation)

    # ---- OP-05 Approve / Reject Reservation (v0.2: REQ-06, REQ-07, REQ-08) ---
    @serialized
    def approve(self, user_id: str, reservation_id: int) -> Reservation:
        self.repository.expire_pending(self.now())
        self._require_role(user_id, Role.ADMIN)
        reservation = self._get_reservation(reservation_id)
        self._require_pending(reservation)
        return self._allocate(reservation)

    @serialized
    def reject(self, user_id: str, reservation_id: int) -> Reservation:
        self.repository.expire_pending(self.now())
        self._require_role(user_id, Role.ADMIN)
        reservation = self._get_reservation(reservation_id)
        self._require_pending(reservation)
        reservation.state = State.REJECTED
        self.repository.save(reservation, expected=State.PENDING_APPROVAL)
        self._notify(reservation, "REJECTED")
        return reservation

    # ---- OP-04 Cancel Reservation (REQ-05) -----------------------------------
    @serialized
    def cancel(self, user_id: str, reservation_id: int) -> Reservation:
        self.repository.expire_pending(self.now())
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
        previous = reservation.state
        reservation.state = State.CANCELLED
        self.repository.save(reservation, expected=previous)
        self._notify(reservation, "CANCELLED")
        return reservation

    def get(self, reservation_id: int) -> Reservation:
        self.repository.expire_pending(self.now())
        return self._get_reservation(reservation_id)

    # ---- pravidla -----------------------------------------------------------
    def _allocate(self, reservation: Reservation) -> Reservation:
        """Přechod do CONFIRMED pro Confirm i Approve (stejná pravidla, C05)."""
        decision = self.policy.check(
            reservation,
            self._get_station(reservation.station_id),
            self.repository.relevant_for(reservation),
        )
        if not decision.allowed:
            raise ReservationError(decision.code, ALLOCATION_MESSAGES[decision.code], list(decision.related))
        previous = reservation.state
        reservation.state = State.CONFIRMED
        try:
            # souběžná změna téže rezervace → StaleState (BR-03); konflikt s jinou rezervací
            # odmítne databáze (ADR-01)
            self.repository.save(reservation, expected=previous)
        except ReservationError:
            reservation.state = previous
            raise
        self._notify(reservation, "CONFIRMED")  # až po COMMIT, mimo transakci (DR3)
        return reservation

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

    def _notify(self, reservation: Reservation, event: str) -> None:
        """REQ-09: e-mail vlastníkovi. Notifier žádnou chybu služby nevrací volajícímu."""
        owner = self._require_user(reservation.user_id)
        self.notifier.send(
            owner.email,
            SUBJECTS[event].format(id=reservation.id),
            f"Stanice {reservation.station_id}, {reservation.start_time:%Y-%m-%d %H:%M}–"
            f"{reservation.end_time:%H:%M} UTC.",
        )

    # ---- přístup k datům ----------------------------------------------------
    def _require_user(self, user_id: str) -> User:
        user = self.repository.user(user_id)
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
        station = self.repository.station(station_id)
        if station is None:
            raise ReservationError("UNKNOWN_STATION", "Stanice neexistuje.")
        return station

    def _get_reservation(self, reservation_id: int) -> Reservation:
        reservation = self.repository.get(reservation_id)
        if reservation is None:
            raise ReservationError("UNKNOWN_RESERVATION", "Rezervace neexistuje.")
        return reservation
