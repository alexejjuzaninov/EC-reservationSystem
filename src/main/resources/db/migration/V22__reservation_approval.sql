-- Approval is a property of a station, independent of listing moderation.
ALTER TABLE catalog.stations
  ADD COLUMN requires_booking_approval BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE catalog.stations
SET requires_booking_approval = TRUE
WHERE id IN (
  '20000000-0000-0000-0000-000000000002'::uuid,
  md5('ec-preview-v20-station-8')::uuid,
  md5('ec-preview-v20-station-1')::uuid
);

ALTER TABLE reservation.bookings DROP CONSTRAINT bookings_status_check;
ALTER TABLE reservation.bookings ADD CONSTRAINT bookings_status_check
  CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'CONFIRMED', 'REJECTED', 'EXPIRED', 'CANCELLED'));
ALTER TABLE reservation.bookings
  ADD COLUMN requested_at TIMESTAMPTZ,
  ADD COLUMN decided_at TIMESTAMPTZ,
  ADD COLUMN decided_by UUID;
CREATE INDEX bookings_pending_owner_idx ON reservation.bookings (owner_id, start_at, id)
  WHERE status = 'PENDING_APPROVAL';

-- Fictional requests keep the read-only public preview demonstrable.
WITH examples(seq, station_id, driver_id, days_ahead, state) AS (
  VALUES
    (1, '20000000-0000-0000-0000-000000000002'::uuid,
      '10000000-0000-0000-0000-000000000001'::uuid, 45, 'PENDING_APPROVAL'),
    (2, md5('ec-preview-v20-station-1')::uuid,
      '10000000-0000-0000-0000-000000000005'::uuid, 46, 'PENDING_APPROVAL'),
    (3, md5('ec-preview-v20-station-8')::uuid,
      '10000000-0000-0000-0000-000000000005'::uuid, 47, 'REJECTED')
), prepared AS (
  SELECT e.*, s.*, u.name AS demo_driver_name,
    ((current_date + e.days_ahead + interval '12 hours') AT TIME ZONE 'Europe/Prague') AS slot_start
  FROM examples e
  JOIN catalog.stations s ON s.id = e.station_id
  JOIN identity.users u ON u.id = e.driver_id
)
INSERT INTO reservation.bookings
  (id, station_id, station_name, owner_id, owner_kind, driver_id, driver_name,
   start_at, end_at, status, total_cents, platform_fee_cents, created_at,
   station_address, station_city, access_note, country_code, station_latitude, station_longitude,
   requested_at, decided_at, decided_by)
SELECT md5('ec-preview-v22-approval-' || seq)::uuid,
  id, name, owner_id, owner_kind, driver_id, demo_driver_name,
  slot_start, slot_start + interval '1 hour', state, price_per_hour_cents,
  round(price_per_hour_cents * 0.12)::integer, now() - interval '1 day',
  address, city, access_note, country_code, ST_Y(location), ST_X(location),
  now() - interval '1 day',
  CASE WHEN state = 'REJECTED' THEN now() - interval '12 hours' ELSE NULL END,
  CASE WHEN state = 'REJECTED' THEN owner_id ELSE NULL END
FROM prepared
ON CONFLICT (id) DO NOTHING;
