# Project Frame

## Reservation domain
Charging slots on company-owned EV charging stations. A slot is a time
window on one station, reserved in advance and paid before it becomes
binding.

## Purpose
The system serves employees and visitors who drive electric vehicles and
need a guaranteed charging slot. It prevents queueing and conflicts at a
limited number of stations by reserving time windows in advance, and it
only makes a reservation binding once payment for the slot is settled.

## Users / Stakeholders
- Driver — creates a reservation, chooses a payment method, pays, cancels.
- Facility admin — manages stations, settles manual payments, may cancel
  any reservation.

## Core concepts
Reservation, ChargingStation, User, TimeSlot, Payment

## Core operations
- Create reservation
- Confirm / approve reservation
- Cancel reservation
- Check availability

## Persistent state
Reservation: id, user_id, station_id, start_time, end_time, state,
             payment_method, created_at
ChargingStation: id, connector_type, power_kw, location, active
Payment: id, reservation_id, method (ONLINE | MANUAL), status
         (PENDING | PAID | FAILED), amount, settled_at

## State-changing operation
DRAFT
  -> RESERVED            slot is held for the user
  -> AWAITING_PAYMENT    payment method chosen, waiting for settlement
  -> APPROVED            payment confirmed (online callback or manual
                         settlement by admin)
  -> CONFIRMED           reservation is binding
  -> CANCELLED           payment failed, expired, or cancelled by user

The overlap check runs when the reservation enters RESERVED, so the slot
is protected while the user pays. A DRAFT is only an intent and may
overlap with other drafts.

## Common business rule
Confirmed reservations for the same resource must not overlap.

## Domain-specific business rule
A user may hold at most one CONFIRMED reservation per calendar day, and
its duration must not exceed 4 hours.

## External / system boundary
Payment Gateway — initiates the payment and reports its result over an
asynchronous callback. It is outside our control and may be slow,
unavailable, or answer after our timeout. (Notification Service is a
second, lower-risk dependency: e-mail on confirm and cancel.)

## Assumption
We assume the payment gateway reports every result exactly once, so we do
not need reconciliation against its own records yet.

## Unknown
We do not know how long a reservation may stay in AWAITING_PAYMENT before
the held slot is released, and what happens if the gateway callback
arrives after that timeout — the user paid, but the slot is gone.
