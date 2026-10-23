"""Service vrstva spike: potvrzení rezervace s kontrolou překryvu.

Pravidlo C01: potvrzené rezervace téže stanice se nesmějí překrývat. Kontrola běží při
potvrzení, ne při vytvoření (DRAFT je jen záměr). Intervaly jsou polootevřené [start, end).
"""
import time
from datetime import datetime

from psycopg.errors import DeadlockDetected
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from .models import NO_OVERLAP_CONSTRAINT, Reservation, ReservationState

COMMIT_ATTEMPTS = 3


class OverlapError(Exception):
    pass


class ReservationService:
    def __init__(self, session: Session):
        self.session = session

    def create(self, user_id: int, station_id: int, start_time: datetime, end_time: datetime) -> Reservation:
        reservation = Reservation(
            user_id=user_id, station_id=station_id, start_time=start_time, end_time=end_time
        )
        self.session.add(reservation)
        self.session.commit()
        return reservation

    def confirm(self, reservation_id: int) -> Reservation:
        reservation = self.session.get(Reservation, reservation_id)
        if reservation.state is not ReservationState.DRAFT:
            raise ValueError(f"Cannot confirm reservation in state {reservation.state.value}")
        # 1) Rychlá kontrola v aplikaci: srozumitelná chyba v běžném (sekvenčním) případě.
        if self._find_overlapping(reservation):
            raise OverlapError("Station already has a CONFIRMED reservation in this time range")
        # 2) Autoritativní kontrola: EXCLUDE constraint v PostgreSQL. Platí i při souběhu,
        #    kdy oba požadavky v kroku 1 viděly "bez konfliktu".
        for attempt in range(1, COMMIT_ATTEMPTS + 1):
            reservation.state = ReservationState.CONFIRMED
            try:
                self.session.commit()
                return reservation
            except IntegrityError as exc:
                self.session.rollback()
                if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == NO_OVERLAP_CONSTRAINT:
                    raise OverlapError("Station already has a CONFIRMED reservation in this time range") from exc
                raise
            except OperationalError as exc:
                # Dva současné zápisy mohou při kontrole constraintu čekat jeden na druhý a PostgreSQL
                # jeden z nich ukončí deadlockem. Opakovaný zápis už uvidí výsledek druhého.
                self.session.rollback()
                if not isinstance(exc.orig, DeadlockDetected) or attempt == COMMIT_ATTEMPTS:
                    raise
                time.sleep(0.05 * attempt)
                reservation = self.session.get(Reservation, reservation_id)
        return reservation

    def _find_overlapping(self, reservation: Reservation) -> list[Reservation]:
        stmt = select(Reservation).where(
            Reservation.station_id == reservation.station_id,
            Reservation.state == ReservationState.CONFIRMED,
            Reservation.id != reservation.id,
            Reservation.start_time < reservation.end_time,
            Reservation.end_time > reservation.start_time,
        )
        return list(self.session.scalars(stmt))
