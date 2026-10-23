"""Reservation API (C03 G2): HTTP vstup, validace tvaru požadavku, převod chyb na odpovědi.

Závisí jen na Reservation Management (service) a doménových typech. Uživatele určuje
hlavička X-User-Id; skutečná identita je otevřená otázka TBD-01.
"""
from datetime import datetime
from typing import Callable, List

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel

from .domain import Reservation, ReservationError
from .service import ReservationService

ERROR_STATUS = {
    "UNAUTHORIZED": 403,
    "UNKNOWN_STATION": 404,
    "UNKNOWN_RESERVATION": 404,
    "INVALID_INTERVAL": 422,
    "INVALID_DURATION": 422,
    "START_IN_PAST": 422,
}  # ostatní kódy (OVERLAP, DAILY_LIMIT, INACTIVE_STATION, INVALID_STATE, TOO_LATE, EXPIRED) → 409


class ReservationIn(BaseModel):
    station_id: str
    start_time: AwareDatetime
    end_time: AwareDatetime


class ReservationOut(BaseModel):
    id: int
    user_id: str
    station_id: str
    start_time: datetime
    end_time: datetime
    state: str
    created_at: datetime


class AvailabilityOut(BaseModel):
    station_id: str
    result: str  # AVAILABLE / UNAVAILABLE


class ErrorOut(BaseModel):
    code: str
    message: str
    related: List[int]


def _out(reservation: Reservation) -> ReservationOut:
    return ReservationOut(
        id=reservation.id,
        user_id=reservation.user_id,
        station_id=reservation.station_id,
        start_time=reservation.start_time,
        end_time=reservation.end_time,
        state=reservation.state.value,
        created_at=reservation.created_at,
    )


def create_app(service: Callable[[], ReservationService], **kwargs) -> FastAPI:
    app = FastAPI(title="Rezervace nabíjecích stanic", **kwargs)

    @app.exception_handler(ReservationError)
    def reservation_error(_: Request, exc: ReservationError) -> JSONResponse:
        body = ErrorOut(code=exc.code, message=exc.message, related=exc.related)
        return JSONResponse(status_code=ERROR_STATUS.get(exc.code, 409), content=body.model_dump())

    @app.post("/reservations", status_code=201, response_model=ReservationOut)
    def create_reservation(body: ReservationIn, x_user_id: str = Header()) -> ReservationOut:
        """OP-01 Create Reservation; walking skeleton z C01."""
        return _out(service().create(x_user_id, body.station_id, body.start_time, body.end_time))

    @app.get("/reservations/{reservation_id}", response_model=ReservationOut)
    def get_reservation(reservation_id: int) -> ReservationOut:
        return _out(service().get(reservation_id))

    @app.get("/stations/{station_id}/availability", response_model=AvailabilityOut)
    def check_availability(station_id: str, start_time: AwareDatetime, end_time: AwareDatetime) -> AvailabilityOut:
        """OP-02 Check Availability."""
        return AvailabilityOut(station_id=station_id,
                               result=service().check_availability(station_id, start_time, end_time))

    @app.post("/reservations/{reservation_id}/confirm", response_model=ReservationOut)
    def confirm_reservation(reservation_id: int, x_user_id: str = Header()) -> ReservationOut:
        """OP-03 Confirm Reservation."""
        return _out(service().confirm(x_user_id, reservation_id))

    @app.post("/reservations/{reservation_id}/cancel", response_model=ReservationOut)
    def cancel_reservation(reservation_id: int, x_user_id: str = Header()) -> ReservationOut:
        """OP-04 Cancel Reservation."""
        return _out(service().cancel(x_user_id, reservation_id))

    @app.post("/reservations/{reservation_id}/approve", response_model=ReservationOut)
    def approve_reservation(reservation_id: int, x_user_id: str = Header()) -> ReservationOut:
        """OP-05 Approve Reservation."""
        return _out(service().approve(x_user_id, reservation_id))

    @app.post("/reservations/{reservation_id}/reject", response_model=ReservationOut)
    def reject_reservation(reservation_id: int, x_user_id: str = Header()) -> ReservationOut:
        """OP-05 Reject Reservation."""
        return _out(service().reject(x_user_id, reservation_id))

    return app
