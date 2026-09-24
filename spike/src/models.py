"""Perzistentní stav z Project Frame C01: User, ChargingStation, Reservation."""
import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class ReservationState(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(100))


class ChargingStation(Base):
    __tablename__ = "charging_stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_type: Mapped[str] = mapped_column(String(20))  # "AC 22 kW" / "DC 50 kW"
    power_kw: Mapped[float]
    location: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("charging_stations.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[ReservationState] = mapped_column(
        Enum(ReservationState, name="reservation_state"), default=ReservationState.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
