import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.db import Base
from src.models import ChargingStation, User

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:swi@localhost:5432/reservations_test"
)


def at(hour: int) -> datetime:
    return datetime(2026, 10, 6, hour, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE reservations, charging_stations, users RESTART IDENTITY CASCADE"))
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def data(session_factory):
    """Jedna stanice a dva uživatelé zapsaní do databáze."""
    with session_factory() as s:
        station = ChargingStation(connector_type="AC 22 kW", power_kw=22, location="P1-A", active=True)
        alice = User(email="alice@example.com", vehicle_type="Skoda Enyaq")
        bob = User(email="bob@example.com", vehicle_type="Hyundai Kona")
        s.add_all([station, alice, bob])
        s.commit()
        return station.id, alice.id, bob.id
