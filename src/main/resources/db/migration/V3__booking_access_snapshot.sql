ALTER TABLE reservation.bookings
  ADD COLUMN station_address TEXT NOT NULL DEFAULT '',
  ADD COLUMN station_city TEXT NOT NULL DEFAULT '',
  ADD COLUMN access_note TEXT NOT NULL DEFAULT '';
