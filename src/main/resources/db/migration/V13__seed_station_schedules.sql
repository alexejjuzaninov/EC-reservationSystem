-- Curated schedules make the owner and admin previews useful on first launch.
-- Skip any interval already booked or blocked in a persistent local database.
WITH examples(seq, station_id, days_ahead, local_hour, duration_hours, reason) AS (
  VALUES
    (1, '20000000-0000-0000-0000-000000000002'::uuid, 2, 10, 2, 'Private use'),
    (2, '20000000-0000-0000-0000-000000000003'::uuid, 3, 15, 3, 'Connector maintenance'),
    (3, '20000000-0000-0000-0000-000000000001'::uuid, 3, 9, 2, 'Site inspection')
), prepared AS (
  SELECT e.*, s.owner_id,
    ((current_date + e.days_ahead + make_interval(hours => e.local_hour))
      AT TIME ZONE CASE WHEN s.country_code = 'US' THEN 'America/New_York' ELSE 'Europe/Prague' END) AS slot_start
  FROM examples e
  JOIN catalog.stations s ON s.id = e.station_id
)
INSERT INTO reservation.station_time_blocks (id, station_id, owner_id, start_at, end_at, reason)
SELECT md5('ec-preview-schedule-v13-' || seq)::uuid, station_id, owner_id,
  slot_start, slot_start + make_interval(hours => duration_hours), reason
FROM prepared p
WHERE NOT EXISTS (
  SELECT 1 FROM reservation.bookings b
  WHERE b.station_id = p.station_id AND b.status = 'CONFIRMED'
    AND b.start_at < p.slot_start + make_interval(hours => p.duration_hours)
    AND b.end_at > p.slot_start
)
AND NOT EXISTS (
  SELECT 1 FROM reservation.station_time_blocks t
  WHERE t.station_id = p.station_id
    AND t.start_at < p.slot_start + make_interval(hours => p.duration_hours)
    AND t.end_at > p.slot_start
)
ON CONFLICT (id) DO NOTHING;
