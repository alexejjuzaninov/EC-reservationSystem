"""Reservation Store (C03 G2): trvalý stav rezervací v PostgreSQL.

Jediný modul, který zná SQL a SQLAlchemy (architektonické pravidlo, C03 L2). Vlastní
invarianty BR-02 a BR-04 ve schématu (ADR-01) a jejich porušení převádí na doménovou
chybu AllocationConflict. Ven vrací doménové objekty, ne řádky ORM.
"""
import os
from datetime import datetime
from typing import Callable, List, Optional

from sqlalchemy import (
    DDL,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    create_engine,
    event,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .domain import (
    ALLOCATION_MESSAGES,
    AllocationConflict,
    ChargingStation,
    Reservation,
    Role,
    State,
    User,
    overlaps,
    utc_day,
)

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:swi@localhost:5432/reservations"

NO_OVERLAP_CONSTRAINT = "no_overlapping_confirmed"  # BR-02
ONE_PER_DAY_INDEX = "one_confirmed_per_user_day"  # BR-04


class Base(DeclarativeBase):
    pass


# Operátor "=" nad textovým station_id v GiST indexu potřebuje rozšíření btree_gist.
event.listen(Base.metadata, "before_create", DDL("CREATE EXTENSION IF NOT EXISTS btree_gist"))


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(100))


class StationRow(Base):
    __tablename__ = "charging_stations"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    connector_type: Mapped[str] = mapped_column(String(20))
    power_kw: Mapped[float]
    location: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)
    requires_approval: Mapped[bool] = mapped_column(default=False)


class ReservationRow(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        # ADR-01, BR-02: dvě CONFIRMED rezervace téže stanice se nesmějí překrývat.
        # '[)' = polootevřený interval (BR-01), navazující časy jsou povolené.
        ExcludeConstraint(
            ("station_id", "="),
            (text("tstzrange(start_time, end_time, '[)')"), "&&"),
            using="gist",
            where=text("state = 'CONFIRMED'"),
            name=NO_OVERLAP_CONSTRAINT,
        ),
        # ADR-01, BR-04: nejvýše jedna CONFIRMED rezervace uživatele za den; den = datum začátku v UTC.
        Index(
            ONE_PER_DAY_INDEX,
            "user_id",
            text("((start_time AT TIME ZONE 'UTC')::date)"),
            unique=True,
            postgresql_where=text("state = 'CONFIRMED'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    station_id: Mapped[str] = mapped_column(ForeignKey("charging_stations.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[State] = mapped_column(Enum(State, name="reservation_state"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def make_engine(url: Optional[str] = None) -> Engine:
    return create_engine(url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def drop_schema(engine: Engine) -> None:
    Base.metadata.drop_all(engine)


def seed_demo(sessions: Callable[[], Session]) -> None:
    """Ukázková data shodná s aplikací C02: alice, bob, admin; stanice AC-1, DC-1, AC-2."""
    with sessions() as s:
        if s.get(UserRow, "alice") is not None:
            return
        s.add_all([
            UserRow(id="alice", role=Role.EMPLOYEE, email="alice@example.com", vehicle_type="Škoda Enyaq"),
            UserRow(id="bob", role=Role.EMPLOYEE, email="bob@example.com", vehicle_type="Hyundai Kona Electric"),
            UserRow(id="admin", role=Role.ADMIN, email="admin@example.com"),
            StationRow(id="AC-1", connector_type="AC 22 kW", power_kw=22, location="Parkoviště P1, stání 1"),
            StationRow(id="DC-1", connector_type="DC 50 kW", power_kw=50, location="Parkoviště P1, stání 2",
                       requires_approval=True),
            StationRow(id="AC-2", connector_type="AC 22 kW", power_kw=22, location="Parkoviště P2, stání 1",
                       active=False),
        ])
        s.commit()


def _reservation(row: ReservationRow) -> Reservation:
    return Reservation(
        id=row.id,
        user_id=row.user_id,
        station_id=row.station_id,
        start_time=row.start_time,
        end_time=row.end_time,
        created_at=row.created_at,
        state=row.state,
    )


class SqlReservationRepository:
    """Implementace kontraktu service.ReservationRepository nad PostgreSQL.

    Každá metoda je jedna krátká transakce; save() končí COMMIT, takže e-mail, který
    service pošle po save(), odchází až po zápisu (DR3).
    """

    def __init__(self, sessions: Callable[[], Session]):
        self._sessions = sessions

    def user(self, user_id: str) -> Optional[User]:
        with self._sessions() as s:
            row = s.get(UserRow, user_id)
            return User(row.id, row.role, row.email, row.vehicle_type) if row else None

    def station(self, station_id: str) -> Optional[ChargingStation]:
        with self._sessions() as s:
            row = s.get(StationRow, station_id)
            if row is None:
                return None
            return ChargingStation(row.id, row.connector_type, row.power_kw, row.location,
                                   row.active, row.requires_approval)

    def get(self, reservation_id: int) -> Optional[Reservation]:
        with self._sessions() as s:
            row = s.get(ReservationRow, reservation_id)
            return _reservation(row) if row else None

    def add(self, reservation: Reservation) -> Reservation:
        with self._sessions() as s:
            row = ReservationRow(
                user_id=reservation.user_id,
                station_id=reservation.station_id,
                start_time=reservation.start_time,
                end_time=reservation.end_time,
                state=reservation.state,
                created_at=reservation.created_at,
            )
            s.add(row)
            s.commit()
            return _reservation(row)

    def save(self, reservation: Reservation) -> None:
        with self._sessions() as s:
            try:
                s.execute(
                    update(ReservationRow)
                    .where(ReservationRow.id == reservation.id)
                    .values(state=reservation.state)
                )
                s.commit()
            except IntegrityError as exc:
                s.rollback()
                raise self._translate(exc, reservation) from exc

    def relevant_for(self, candidate: Reservation) -> List[Reservation]:
        with self._sessions() as s:
            rows = s.scalars(
                select(ReservationRow).where(
                    ReservationRow.state == State.CONFIRMED,
                    ReservationRow.id != candidate.id,
                    or_(ReservationRow.station_id == candidate.station_id,
                        ReservationRow.user_id == candidate.user_id),
                )
            )
            return [_reservation(r) for r in rows]

    def confirmed_for_station(self, station_id: str) -> List[Reservation]:
        with self._sessions() as s:
            rows = s.scalars(
                select(ReservationRow).where(
                    ReservationRow.station_id == station_id, ReservationRow.state == State.CONFIRMED
                )
            )
            return [_reservation(r) for r in rows]

    def expire_pending(self, now: datetime) -> None:
        with self._sessions() as s:
            s.execute(
                update(ReservationRow)
                .where(ReservationRow.state == State.PENDING_APPROVAL, ReservationRow.start_time <= now)
                .values(state=State.EXPIRED)
            )
            s.commit()

    def _translate(self, exc: IntegrityError, candidate: Reservation) -> Exception:
        """Porušení invariantu z ADR-01 → AllocationConflict se stejným kódem jako v AllocationPolicy."""
        name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if name == NO_OVERLAP_CONSTRAINT:
            code = "OVERLAP"
            related = [r.id for r in self.relevant_for(candidate)
                       if r.station_id == candidate.station_id
                       and overlaps(candidate.start_time, candidate.end_time, r.start_time, r.end_time)]
        elif name == ONE_PER_DAY_INDEX:
            code = "DAILY_LIMIT"
            related = [r.id for r in self.relevant_for(candidate)
                       if r.user_id == candidate.user_id and utc_day(r.start_time) == utc_day(candidate.start_time)]
        else:
            return exc  # jiné porušení integrity není doménový konflikt
        return AllocationConflict(code, ALLOCATION_MESSAGES[code], related)


def session_factory(engine: Engine) -> Callable[[], Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
