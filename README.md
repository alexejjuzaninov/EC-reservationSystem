# EC Reservation System

An English-language EV charging marketplace built with Spring Boot 3.5, Java 21, PostgreSQL 16 with PostGIS, a physical read replica, Redis, Flyway, and a responsive web app. The previous Python prototype and its documentation are preserved in [old/](old/); the Spring Boot project lives at the repository root.

EC operates its own chargers. Private hosts and companies can list theirs for drivers to reserve, with a 12% EC commission on partner bookings. Booking, availability, moderation, notifications, search, and access rules work against local data. Payments, station telemetry, business metrics, and Kafka delivery are clearly marked simulations.

## Start

Docker Desktop is required. From this folder:

    docker compose up -d --build

Open http://localhost:18080. First startup creates the primary and streaming read replica, runs 21 Flyway migrations, and seeds about 141,000 fictional chargers plus sample bookings, notifications, schedule blocks, and saved chargers. The first run can take a few minutes. Data persists in Docker volumes.

    docker compose down

The local ports are 18080 for the app, 56432 for PostgreSQL primary, 56433 for its replica, and 57379 for Redis. All bind to `127.0.0.1`.

## Explore the role-specific workspaces

Use the account picker in the top bar:

| Role | Demo account | Workspace |
|---|---|---|
| Driver | Anna or Mark | Search the map, save chargers, reserve a slot, get directions, see the next charge, trips, and notifications. Their saved lists are separate; two drivers can demonstrate slot conflicts. |
| Private host | Ilya | Add a charger, set access instructions and weekly opening hours, block specific dates, manage availability, see incoming bookings and estimated share. |
| Company | VoltHouse s.r.o. | Fleet table, bulk availability controls, per-station schedules, reservations, and payout preview. |
| EC network | EC Network | Operate EC-owned chargers and review network activity. |
| Administrator | Elena | Review partner listings, search and paginate every station, inspect any station's simulated telemetry and schedule, control availability, and monitor platform health. |

Drivers can create additional demo driver, host, and company profiles through the app. A new partner station enters the admin review queue; approval makes it visible on the public map. The location picker supports Czechia and the United States. Private access instructions appear only in a confirmed driver's booking.

Filters use custom dropdowns. Booking and station scheduling use custom day and time pickers. Hosts, companies, EC operators, and admins can block future hours for maintenance or private use; blocks cannot overlap confirmed bookings, and drivers cannot reserve blocked time. Reservation lists and the admin station directory are paginated by the API. The admin directory also supports country, operator, status, name, city, and owner search, plus a direct page jump. Simulated telemetry can be opened for any listed station.

Drivers can save a charger from the map and return to it from Saved chargers. The saved list is stored per demo profile and loaded in one bounded catalog query. The trip page highlights the nearest upcoming reservation, puts upcoming bookings before history, and offers a directions link. Directions use station coordinates saved with each booking, so fictional street names do not misdirect the route. Google Maps needs internet access; booking and saved places work locally.

Map counts are grouped in projected screen-sized cells with PostGIS and cached in Redis. At closer zoom, individual price markers and station cards appear. The city picker covers 50 Czech locations; typing a listed place recenters the map. The map remains searchable if Redis is unavailable. Map outlines are served locally; OpenStreetMap background tiles need internet access. Czech city centers are derived from [GeoNames](https://www.geonames.org/export/) under CC BY 4.0; all chargers and street addresses are fictional.

## Check the local stack

Run `docker compose ps` and open `http://localhost:18080/api/system`. The response reports the primary, replica, Redis, and which capabilities are simulated.

To intentionally erase all local demo changes, including accounts and bookings:

    docker compose down -v
    docker compose up -d

The volume reset removes this Compose project's local data.

## API and architecture

The UI uses the local REST API. GET /api/users lists demo accounts. The X-Demo-User header selects an account for manual testing; omitted headers use Anna. Main endpoints cover /api/map/explore, /api/stations, /api/stations/{id}/availability, /api/stations/availability-batch, /api/stations/{id}/weekly-hours, /api/stations/{id}/blocks, /api/saved-stations, /api/bookings, /api/bookings/page, /api/admin/stations, /api/notifications, /api/dashboard, and /api/system. Admin review and owner controls have dedicated endpoints.

See [architecture](docs/architecture.md) for storage boundaries and data flow.

The public read-only deployment uses a separate Compose stack, database snapshot, and Cloudflare Tunnel. Its operational notes are in [preview/README.md](preview/README.md). Local preview secrets and snapshot artifacts are excluded from Git.

## Preview limits

The account picker is a testing aid, not authentication. A public deployment needs OIDC/JWT, secrets management, request limits, and operational controls. No payment provider, OCPP hardware, SMS/email/push service, or Kafka broker is connected. Compose credentials are for local development only.
