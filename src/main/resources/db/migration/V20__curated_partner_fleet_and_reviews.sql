-- Every listing below is fictional and belongs to one of the switchable demo profiles.
WITH listings(seq, owner_id, owner_name, owner_kind, name, address, city, connector, power_kw,
              price_cents, country_code, latitude, longitude, listing_status) AS (
  VALUES
    (1, '10000000-0000-0000-0000-000000000003'::uuid, 'VoltHouse s.r.o.', 'COMPANY', 'Vinohrady Courtyard', 'Korunní 46', 'Praha', 'Type 2', 22, 14900, 'CZ', 50.0751, 14.4527, 'APPROVED'),
    (2, '10000000-0000-0000-0000-000000000003'::uuid, 'VoltHouse s.r.o.', 'COMPANY', 'Brno Tech Park', 'Purkyňova 99', 'Brno', 'CCS2', 100, 21900, 'CZ', 49.2266, 16.5732, 'APPROVED'),
    (3, '10000000-0000-0000-0000-000000000003'::uuid, 'VoltHouse s.r.o.', 'COMPANY', 'Ostrava Exchange', 'Nádražní 31', 'Ostrava', 'CCS2', 75, 19900, 'CZ', 49.8396, 18.2848, 'APPROVED'),
    (4, '10000000-0000-0000-0000-000000000003'::uuid, 'VoltHouse s.r.o.', 'COMPANY', 'Brooklyn Yard', 'Wythe Avenue 72', 'New York', 'CCS2', 150, 2900, 'US', 40.7187, -73.9622, 'APPROVED'),
    (5, '10000000-0000-0000-0000-000000000004'::uuid, 'EC Network', 'PLATFORM', 'Old Town Exchange', 'Revoluční 15', 'Praha', 'CCS2', 150, 25900, 'CZ', 50.0918, 14.4285, 'APPROVED'),
    (6, '10000000-0000-0000-0000-000000000004'::uuid, 'EC Network', 'PLATFORM', 'Plzeň Gate', 'Americká 20', 'Plzeň', 'CCS2', 120, 22900, 'CZ', 49.7422, 13.3846, 'APPROVED'),
    (7, '10000000-0000-0000-0000-000000000004'::uuid, 'EC Network', 'PLATFORM', 'Chicago Loop Hub', 'Wabash Avenue 105', 'Chicago', 'CCS2', 150, 3200, 'US', 41.8819, -87.6262, 'APPROVED'),
    (8, '10000000-0000-0000-0000-000000000002'::uuid, 'Ilya', 'PERSON', 'Letná Garden Plug', 'Letohradská 21', 'Praha', 'Type 2', 11, 9900, 'CZ', 50.1008, 14.4289, 'APPROVED'),
    (9, '10000000-0000-0000-0000-000000000003'::uuid, 'VoltHouse s.r.o.', 'COMPANY', 'Austin South Congress', 'South Congress Avenue 180', 'Austin', 'Type 2', 22, 1900, 'US', 30.2489, -97.7498, 'APPROVED'),
    (10, '10000000-0000-0000-0000-000000000002'::uuid, 'Ilya', 'PERSON', 'Hradčany Home Charger', 'U Brusnice 10', 'Praha', 'Type 2', 11, 10900, 'CZ', 50.0949, 14.3895, 'PENDING'),
    (11, '10000000-0000-0000-0000-000000000003'::uuid, 'VoltHouse s.r.o.', 'COMPANY', 'Liberec Plaza', 'Fügnerova 8', 'Liberec', 'CCS2', 75, 19900, 'CZ', 50.7662, 15.0541, 'PENDING'),
    (12, '10000000-0000-0000-0000-000000000003'::uuid, 'VoltHouse s.r.o.', 'COMPANY', 'Seattle Waterfront', 'Alaskan Way 214', 'Seattle', 'CCS2', 120, 2900, 'US', 47.6062, -122.3425, 'PENDING'),
    (13, '10000000-0000-0000-0000-000000000002'::uuid, 'Ilya', 'PERSON', 'České Budějovice Home Plug', 'Lannova 12', 'České Budějovice', 'Type 2', 11, 8900, 'CZ', 48.9765, 14.4787, 'PENDING'),
    (14, '10000000-0000-0000-0000-000000000003'::uuid, 'VoltHouse s.r.o.', 'COMPANY', 'South Beach Pilot', 'Collins Avenue 44', 'Miami', 'Type 2', 22, 2200, 'US', 25.7844, -80.1300, 'REJECTED')
)
INSERT INTO catalog.stations
  (id, owner_id, owner_name, owner_kind, name, address, city, connector, power_kw,
   price_per_hour_cents, access_note, active, created_at, country_code, location, synthetic, listing_status)
SELECT md5('ec-preview-v20-station-' || seq)::uuid, owner_id, owner_name, owner_kind,
  name, address, city, connector, power_kw, price_cents,
  'Fictional demo location · details shared after a confirmed reservation',
  TRUE, now() - make_interval(hours => seq * 3), country_code,
  ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), TRUE, listing_status
FROM listings
ON CONFLICT (id) DO NOTHING;

INSERT INTO catalog.outbox (id, station_id, owner_id, event_type, created_at)
SELECT md5('ec-preview-v20-submission-' || s.id)::uuid, s.id, s.owner_id,
  'STATION_SUBMITTED', s.created_at
FROM catalog.stations s
WHERE s.id IN (SELECT md5('ec-preview-v20-station-' || n)::uuid FROM generate_series(10,13) n)
ON CONFLICT (id) DO NOTHING;

WITH samples AS (
  SELECT station_no, slot_no, s.*,
    CASE WHEN mod(slot_no + station_no, 2) = 0 THEN '10000000-0000-0000-0000-000000000001'::uuid
      ELSE '10000000-0000-0000-0000-000000000005'::uuid END driver_id
  FROM generate_series(1,9) station_no
  CROSS JOIN generate_series(1,8) slot_no
  JOIN catalog.stations s ON s.id = md5('ec-preview-v20-station-' || station_no)::uuid
), prepared AS (
  SELECT x.*, u.name driver_name,
    ((current_date + (slot_no - 4) * 5 + make_interval(hours => 9 + mod(station_no, 8)))
      AT TIME ZONE CASE WHEN country_code = 'US' THEN 'America/New_York' ELSE 'Europe/Prague' END) slot_start,
    (ARRAY[45,60,90,120])[1 + mod(slot_no + station_no, 4)] duration_minutes
  FROM samples x JOIN identity.users u ON u.id = x.driver_id
)
INSERT INTO reservation.bookings
  (id, station_id, station_name, owner_id, owner_kind, driver_id, driver_name,
   start_at, end_at, status, total_cents, platform_fee_cents, created_at,
   station_address, station_city, access_note, country_code, station_latitude, station_longitude)
SELECT md5('ec-preview-v20-booking-' || station_no || '-' || slot_no)::uuid,
  id, name, owner_id, owner_kind, driver_id, driver_name,
  slot_start, slot_start + make_interval(mins => duration_minutes),
  CASE WHEN mod(station_no * 7 + slot_no, 13) = 0 THEN 'CANCELLED' ELSE 'CONFIRMED' END,
  round(price_per_hour_cents * duration_minutes / 60.0)::integer,
  CASE WHEN owner_kind = 'PLATFORM' THEN round(price_per_hour_cents * duration_minutes / 60.0)::integer
    ELSE round(price_per_hour_cents * duration_minutes / 60.0 * 0.12)::integer END,
  LEAST(now() - interval '2 hours', slot_start - make_interval(days => 2 + mod(slot_no, 4))),
  address, city, access_note, country_code, ST_Y(location), ST_X(location)
FROM prepared
ON CONFLICT (id) DO NOTHING;

INSERT INTO reservation.outbox (id, booking_id, event_type, total_cents, platform_fee_cents, created_at)
SELECT md5('ec-preview-v20-event-' || b.id)::uuid, b.id,
  CASE WHEN b.status = 'CANCELLED' THEN 'CANCELLED' ELSE 'BOOKED' END,
  b.total_cents, b.platform_fee_cents, b.created_at
FROM reservation.bookings b
WHERE b.id IN (
  SELECT md5('ec-preview-v20-booking-' || station_no || '-' || slot_no)::uuid
  FROM generate_series(1,9) station_no CROSS JOIN generate_series(1,8) slot_no)
ON CONFLICT (id) DO NOTHING;
