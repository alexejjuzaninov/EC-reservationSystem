-- Refresh only generated listings; manually managed listings and booking snapshots are untouched.
UPDATE catalog.stations s
SET name = (ARRAY['Courtyard charge', 'Riverside plug', 'Market square charger',
                  'Garden lane charging', 'Station park point', 'City loop charger',
                  'Cornerhouse plug', 'Canal side charging', 'Transit stop charger',
                  'Neighborhood charge', 'East gate charger', 'West end plug'])
                [1 + mod(abs(hashtext(s.id::text)), 12)] || ' · ' || s.city || ' ' ||
                (1 + mod(abs(hashtext(s.id::text || 'number')), 82)),
    address = (ARRAY['Garden Lane', 'Market Street', 'Riverside Road', 'Station Way',
                     'North Avenue', 'South Street', 'Park Road', 'Bridge Lane'])
                [1 + mod(abs(hashtext(s.id::text || 'street')), 8)] || ' ' ||
                (1 + mod(abs(hashtext(s.id::text || 'house')), 96)),
    access_note = CASE mod(abs(hashtext(s.id::text || 'access')), 5)
      WHEN 0 THEN 'Fictional location · curbside access'
      WHEN 1 THEN 'Fictional location · parking area entrance'
      WHEN 2 THEN 'Fictional location · use the marked charging bay'
      WHEN 3 THEN 'Fictional location · access from the side road'
      ELSE 'Fictional location · open parking bay' END
WHERE s.synthetic = TRUE;

-- Additional reservations give the driver, host, company and EC network views a varied history.
WITH sample AS (
  SELECT n, CASE mod(n, 4)
    WHEN 0 THEN '20000000-0000-0000-0000-000000000001'::uuid
    WHEN 1 THEN '20000000-0000-0000-0000-000000000002'::uuid
    WHEN 2 THEN '20000000-0000-0000-0000-000000000003'::uuid
    ELSE '20000000-0000-0000-0000-000000000004'::uuid END station_id,
    CASE WHEN mod(n, 2) = 0 THEN '10000000-0000-0000-0000-000000000001'::uuid
      ELSE '10000000-0000-0000-0000-000000000005'::uuid END driver_id
  FROM generate_series(1, 112) n
), prepared AS (
  SELECT x.*, s.name, s.owner_id, s.owner_kind, s.address, s.city, s.access_note,
    s.country_code, s.location, s.price_per_hour_cents, u.name driver_name,
    ((current_date + (x.n - 68) + make_interval(hours => 9 + mod(x.n * 7, 10)))
      AT TIME ZONE CASE WHEN s.country_code = 'US' THEN 'America/New_York' ELSE 'Europe/Prague' END) slot_start,
    (ARRAY[45,60,75,90,120])[1 + mod(x.n, 5)] duration_minutes
  FROM sample x JOIN catalog.stations s ON s.id = x.station_id
  JOIN identity.users u ON u.id = x.driver_id
)
INSERT INTO reservation.bookings
  (id, station_id, station_name, owner_id, owner_kind, driver_id, driver_name,
   start_at, end_at, status, total_cents, platform_fee_cents, created_at,
   station_address, station_city, access_note, country_code, station_latitude, station_longitude)
SELECT md5('ec-preview-booking-v19-' || n)::uuid, station_id, name, owner_id, owner_kind,
  driver_id, driver_name, slot_start, slot_start + make_interval(mins => duration_minutes),
  CASE WHEN mod(n, 11) = 0 THEN 'CANCELLED' ELSE 'CONFIRMED' END,
  round(price_per_hour_cents * duration_minutes / 60.0)::integer,
  CASE WHEN owner_kind = 'PLATFORM' THEN round(price_per_hour_cents * duration_minutes / 60.0)::integer
    ELSE round(price_per_hour_cents * duration_minutes / 60.0 * 0.12)::integer END,
  LEAST(now() - interval '2 hours', slot_start - make_interval(days => 1 + mod(n, 9))),
  address, city, access_note, country_code, ST_Y(location), ST_X(location)
FROM prepared p
WHERE NOT EXISTS (
  SELECT 1 FROM reservation.bookings b WHERE b.station_id = p.station_id
    AND b.status = 'CONFIRMED' AND b.start_at < p.slot_start + make_interval(mins => p.duration_minutes)
    AND b.end_at > p.slot_start)
ON CONFLICT (id) DO NOTHING;

INSERT INTO reservation.outbox (id, booking_id, event_type, total_cents, platform_fee_cents, created_at)
SELECT md5('ec-preview-booked-event-v19-' || b.id)::uuid, b.id,
  CASE WHEN b.status = 'CANCELLED' THEN 'CANCELLED' ELSE 'BOOKED' END,
  b.total_cents, b.platform_fee_cents, b.created_at
FROM reservation.bookings b
WHERE b.id IN (SELECT md5('ec-preview-booking-v19-' || n)::uuid FROM generate_series(1,112) n)
ON CONFLICT (id) DO NOTHING;

ANALYZE catalog.stations;
ANALYZE reservation.bookings;
