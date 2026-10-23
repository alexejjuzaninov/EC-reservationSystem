"""Sestavení aplikace (composition root): propojí API, service, úložiště a notifikace.

Spuštění:  uvicorn reservations.main:app
Databáze podle proměnné DATABASE_URL (výchozí: PostgreSQL ze spike C01 na localhost:5432).
"""
from contextlib import asynccontextmanager

from .api import create_app
from .notifications import EmailServiceStub, NotificationIntegration
from .service import ReservationService
from .store import SqlReservationRepository, create_schema, make_engine, seed_demo, session_factory

engine = make_engine()
sessions = session_factory(engine)
notifications = NotificationIntegration(EmailServiceStub())
service = ReservationService(SqlReservationRepository(sessions), notifications)


@asynccontextmanager
async def lifespan(_app):
    create_schema(engine)
    seed_demo(sessions)
    yield
    engine.dispose()


app = create_app(lambda: service, lifespan=lifespan)
