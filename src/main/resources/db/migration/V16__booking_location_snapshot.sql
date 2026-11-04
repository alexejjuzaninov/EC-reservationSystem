ALTER TABLE reservation.bookings
  ADD COLUMN station_latitude DOUBLE PRECISION,
  ADD COLUMN station_longitude DOUBLE PRECISION;

-- Historical demo bookings receive the catalog location once. Runtime booking reads
-- continue to use their immutable reservation snapshot rather than a catalog JOIN.
UPDATE reservation.bookings b
SET station_latitude = ST_Y(s.location), station_longitude = ST_X(s.location)
FROM catalog.stations s
WHERE b.station_id = s.id AND b.station_latitude IS NULL;
