TRUNCATE TABLE
  notification.messages,
  billing.simulated_charges,
  reservation.outbox,
  reservation.bookings,
  reservation.station_time_blocks,
  reservation.weekly_station_hours,
  catalog.outbox,
  catalog.stations,
  identity.saved_stations,
  identity.users
CASCADE;
