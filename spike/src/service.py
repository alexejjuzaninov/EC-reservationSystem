"""Service vrstva spike: potvrzení rezervace s kontrolou překryvu.

Pravidlo C01: potvrzené rezervace téže stanice se nesmějí překrývat. Kontrola běží při
potvrzení, ne při vytvoření (DRAFT je jen záměr). Intervaly jsou polootevřené [start, end).
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Reservation, ReservationState


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
        if self._find_overlapping(reservation):  # kontrola ...
            raise OverlapError("Station already has a CONFIRMED reservation in this time range")
        reservation.state = ReservationState.CONFIRMED  # ... a zápis jsou dva oddělené kroky
        self.session.commit()
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
