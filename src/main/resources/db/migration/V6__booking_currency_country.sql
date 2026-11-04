ALTER TABLE reservation.bookings
  ADD COLUMN country_code CHAR(2) NOT NULL DEFAULT 'CZ'
    CHECK (country_code IN ('CZ', 'US'));
