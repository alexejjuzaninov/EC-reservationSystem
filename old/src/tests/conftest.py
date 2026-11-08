import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from reservations.api import create_app
from reservations.notifications import EmailServiceStub, NotificationIntegration
from reservations.service import ReservationService
from reservations.store import SqlReservationRepository, create_schema, drop_schema, seed_demo, session_factory

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:swi@localhost:5432/reservations_app_test"
)
DEMO_NOW = datetime(2026, 10, 11, 8, 0, tzinfo=timezone.utc)  # stejný čas jako příklady C02


def at(hhmm: str, day: int = 11) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


class Clock:
    def __init__(self, instant: datetime):
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant


@dataclass
class System:
    client: TestClient
    service: ReservationService
    clock: Clock
    email: EmailServiceStub
    notifications: NotificationIntegration
    sessions: Callable[[], Session]


def _ensure_database(url: str) -> None:
    """Vytvoří testovací databázi, pokud ještě neexistuje (stačí běžící PostgreSQL ze spike C01)."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database}).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    _ensure_database(TEST_DATABASE_URL)
    eng = create_engine(TEST_DATABASE_URL)
    drop_schema(eng)
    create_schema(eng)
    yield eng
    drop_schema(eng)
    eng.dispose()


@pytest.fixture
def system(engine) -> System:
    """Prázdná databáze s ukázkovými daty C02, simulovaný čas 11. 10. 2026 08:00 UTC."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE reservations, charging_stations, users RESTART IDENTITY CASCADE"))
    sessions = session_factory(engine)
    seed_demo(sessions)
    clock = Clock(DEMO_NOW)
    email = EmailServiceStub()
    notifications = NotificationIntegration(email)
    service = ReservationService(SqlReservationRepository(sessions), notifications, clock=clock)
    client = TestClient(create_app(lambda: service))
    return System(client, service, clock, email, notifications, sessions)
