-- Reservation examples use actual catalog records and real booking snapshots.
-- Times are spread over several weeks so the driver and owner workspaces show activity.
WITH examples(seq, station_id, driver_id, days_ahead, local_hour, minutes) AS (
  VALUES
    (1, '20000000-0000-0000-0000-000000000004'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 2, 20, 60),
    (2, '20000000-0000-0000-0000-000000000002'::uuid, '10000000-0000-0000-0000-000000000005'::uuid, 4, 8, 90),
    (3, '20000000-0000-0000-0000-000000000003'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 5, 18, 60),
    (4, '20000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000005'::uuid, 7, 7, 45),
    (5, md5('demo-station-1000')::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 9, 19, 60),
    (6, md5('demo-station-1001')::uuid, '10000000-0000-0000-0000-000000000005'::uuid, 11, 17, 90),
    (7, md5('demo-station-1002')::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 14, 7, 60),
    (8, md5('demo-station-1003')::uuid, '10000000-0000-0000-0000-000000000005'::uuid, 16, 19, 120),
    (9, md5('demo-station-1004')::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 19, 10, 45),
    (10, md5('demo-station-1005')::uuid, '10000000-0000-0000-0000-000000000005'::uuid, 22, 18, 60),
    (11, md5('demo-station-25005')::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 26, 11, 60),
    (12, md5('demo-station-25006')::uuid, '10000000-0000-0000-0000-000000000005'::uuid, 28, 15, 90),
    (13, '20000000-0000-0000-0000-000000000002'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 31, 13, 60),
    (14, '20000000-0000-0000-0000-000000000003'::uuid, '10000000-0000-0000-0000-000000000005'::uuid, 34, 10, 120),
    (15, '20000000-0000-0000-0000-000000000001'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 37, 9, 45),
    (16, '20000000-0000-0000-0000-000000000004'::uuid, '10000000-0000-0000-0000-000000000005'::uuid, 40, 11, 60)
), prepared AS (
  SELECT e.*, s.*, u.name AS demo_driver_name,
    ((current_date + e.days_ahead + make_interval(hours => e.local_hour))
      AT TIME ZONE CASE WHEN s.country_code = 'US' THEN 'America/New_York' ELSE 'Europe/Prague' END) AS slot_start,
    round(s.price_per_hour_cents * e.minutes / 60.0)::integer AS quote_cents
  FROM examples e
  JOIN catalog.stations s ON s.id = e.station_id
  JOIN identity.users u ON u.id = e.driver_id
)
INSERT INTO reservation.bookings
  (id, station_id, station_name, owner_id, owner_kind, driver_id, driver_name,
   start_at, end_at, status, total_cents, platform_fee_cents, created_at,
   station_address, station_city, access_note, country_code)
SELECT md5('ec-preview-booking-v10-' || seq)::uuid, station_id, name, owner_id, owner_kind,
  driver_id, demo_driver_name, slot_start, slot_start + make_interval(mins => minutes),
  'CONFIRMED', quote_cents,
  CASE WHEN owner_kind = 'PLATFORM' THEN quote_cents ELSE round(quote_cents * 0.12)::integer END,
  now() - make_interval(days => seq % 5), address, city, access_note, country_code
FROM prepared p
WHERE NOT EXISTS (
  SELECT 1 FROM reservation.bookings b
  WHERE b.station_id = p.station_id AND b.status = 'CONFIRMED'
    AND b.start_at < p.slot_start + make_interval(mins => p.minutes)
    AND b.end_at > p.slot_start
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO reservation.outbox (id, booking_id, event_type, total_cents, platform_fee_cents, created_at)
SELECT md5('ec-preview-booked-event-v10-' || b.id)::uuid, b.id, 'BOOKED',
  b.total_cents, b.platform_fee_cents, b.created_at
FROM reservation.bookings b
WHERE b.id IN (SELECT md5('ec-preview-booking-v10-' || n)::uuid FROM generate_series(1, 16) n)
ON CONFLICT (id) DO NOTHING;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX stations_admin_order_idx ON catalog.stations (synthetic, created_at DESC, id);
CREATE INDEX stations_admin_name_trgm_idx ON catalog.stations USING gin (name gin_trgm_ops);
CREATE INDEX stations_admin_city_trgm_idx ON catalog.stations USING gin (city gin_trgm_ops);
CREATE INDEX stations_admin_owner_trgm_idx ON catalog.stations USING gin (owner_name gin_trgm_ops);
