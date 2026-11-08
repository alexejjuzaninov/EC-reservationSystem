CREATE TABLE reservation.station_time_blocks (
  id UUID PRIMARY KEY,
  station_id UUID NOT NULL,
  owner_id UUID NOT NULL,
  start_at TIMESTAMPTZ NOT NULL,
  end_at TIMESTAMPTZ NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT valid_station_block CHECK (start_at < end_at AND end_at <= start_at + interval '14 days'),
  CONSTRAINT no_overlapping_station_blocks EXCLUDE USING gist
    (station_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
);
CREATE INDEX station_time_blocks_lookup_idx ON reservation.station_time_blocks (station_id, start_at);
GRANT SELECT, INSERT, DELETE ON reservation.station_time_blocks TO booking_app;
GRANT SELECT ON reservation.station_time_blocks TO replica_reader;
