CREATE TABLE reservation.weekly_station_hours (
  station_id UUID NOT NULL,
  owner_id UUID NOT NULL,
  day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
  zone_id TEXT NOT NULL,
  enabled BOOLEAN NOT NULL,
  opens_minute SMALLINT NOT NULL CHECK (opens_minute BETWEEN 0 AND 1439),
  closes_minute SMALLINT NOT NULL CHECK (closes_minute BETWEEN 1 AND 1440),
  PRIMARY KEY (station_id, day_of_week),
  CHECK (opens_minute < closes_minute)
);
GRANT SELECT, INSERT, DELETE ON reservation.weekly_station_hours TO booking_app;
GRANT SELECT ON reservation.weekly_station_hours TO replica_reader;
