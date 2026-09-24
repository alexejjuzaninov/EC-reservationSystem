# Project Frame

Rámec z C01 (dokument `docs/SWI-C01-reservation-system.pdf`, kapitola 3 a 4). V C02 se nemění. Specifikace C02 (baseline v0.1, změna a baseline v0.2) je v `README.md`.

## Reservation domain
Charging slots on company-owned EV charging stations.

## Purpose
The system serves employees who drive electric vehicles to work and need a guaranteed charging
slot during the working day. It prevents queueing and conflicts at a limited number of stations by
reserving time windows in advance.

## Users / Stakeholders
- Employee — creates, confirms and cancels their own reservations.
- Facility admin — manages stations and may cancel any reservation.

## Core concepts
Reservation, ChargingStation, User, TimeSlot.

## Core operations
- Create reservation (result: DRAFT)
- Confirm / approve reservation (DRAFT → CONFIRMED)
- Cancel reservation (DRAFT or CONFIRMED → CANCELLED)
- Check availability of a station within a time range

## Persistent state
```text
Reservation:     id, user_id, station_id, start_time, end_time, state, created_at
ChargingStation: id, connector_type, power_kw, location, active
User:            id, email, vehicle_type
```

## State-changing operation
`confirm(reservation_id)`: DRAFT → CONFIRMED. The overlap check runs at this moment, not at
creation time — a DRAFT is only an intent and may safely overlap with other drafts.

## Common business rule
Confirmed reservations for the same resource must not overlap.

## Domain-specific business rule
A user may hold at most one CONFIRMED reservation per calendar day, and its duration must not
exceed 4 hours.

## External / system boundary
Notification Service — sends an e-mail when a reservation is confirmed or cancelled. Accessed
over HTTP. It is outside our control and may be slow or unavailable.

## Assumption
We assume users cancel reservations they no longer need, so no-shows are rare and we do not
need an automatic release mechanism yet.

## Unknown
We do not know how the system should behave when the Notification Service is unavailable at the
moment of confirmation — should the confirmation fail, or should it succeed and notify later?

## Selected future pressure
Category: R — Risk / Higher consequence

Concrete pressure: Systém se rozšíří z interního parkoviště na veřejné stanice s placenou rezervací.
Dvojitá rezervace pak znamená, že platící zákazník přijede k obsazené stanici.

Why it is relevant to our reservation system: Dnes stojí překryv někoho pět minut čekání. Jakmile do hry vstoupí platba, stejná
chyba znamená vracení peněz, stížnosti a ztrátu důvěry. Pravidlo o překryvu proto
musí být vynuceno na jednom místě v service vrstvě a pokryto automatickým
testem, ne ponecháno na kontrole v UI.

## Změny po C01

| Kdy | Změna | Kde je popsaná |
|---|---|---|
| C02 | Neznámá z C01 rozhodnuta: při nedostupné Notification Service potvrzení platí a e-mail se zapíše jako nedoručený (REQ-09). | `README.md`, REQ-09 |
| C02 | Změna: některé stanice vyžadují schválení Facility adminem (stavy PENDING_APPROVAL, REJECTED, EXPIRED, operace Approve / Reject), baseline v0.2. | `README.md`, části Změna C02 a Baseline v0.2 |
