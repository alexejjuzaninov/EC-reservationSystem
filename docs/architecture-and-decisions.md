# Architecture and Decisions

## C01: Stack decision

We chose Python 3.12 + FastAPI + SQLAlchemy + PostgreSQL + pytest instead of the default Java
/ Spring Boot stack. Reason: the team already works with Python, while no member has practical
experience with Spring. A familiar stack lets us spend C01 on the reservation domain and on the
engineering spike rather than on framework setup.

Trade-off: we support this stack ourselves, without the teacher's reference setup. FastAPI gives us
request validation (Pydantic) and an OpenAPI schema out of the box, which covers what the CP1
walking skeleton needs. PostgreSQL is kept from the recommended stack, so the persistence layer
stays comparable to other teams.

## C02: výchozí stav pro C03

Aplikace C02 (`reservation.py`) je záměrně jednoduchá: jeden modul, data jen v paměti, jeden zámek pro všechny operace. Webová ukázka `app/index.html` obsahuje stejná pravidla přepsaná do JavaScriptu. Architektonické drivery D1 až D5, které z C02 vyplynuly, jsou v `README.md` a v `docs/evidence-and-evolution.md`. Architektura z C03 se doplní sem.
