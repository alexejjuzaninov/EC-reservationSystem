CREATE TABLE identity.saved_stations (
  user_id UUID NOT NULL,
  station_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, station_id)
);
CREATE INDEX saved_stations_recent_idx ON identity.saved_stations (user_id, created_at DESC);
GRANT SELECT, INSERT, DELETE ON identity.saved_stations TO identity_app;

-- Give the two sample drivers useful starting points without changing their bookings.
INSERT INTO identity.saved_stations (user_id, station_id) VALUES
  ('10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002'),
  ('10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000004'),
  ('10000000-0000-0000-0000-000000000005', '20000000-0000-0000-0000-000000000003')
ON CONFLICT DO NOTHING;
