-- Keep the three sample schedules useful for existing installations upgraded later.
-- Only move untouched rows that have already ended; never replace a deleted example.
WITH examples(seq, station_id, days_ahead, local_hour, duration_hours) AS (
  VALUES
    (1, '20000000-0000-0000-0000-000000000002'::uuid, 2, 10, 2),
    (2, '20000000-0000-0000-0000-000000000003'::uuid, 3, 15, 3),
    (3, '20000000-0000-0000-0000-000000000001'::uuid, 3, 9, 2)
), prepared AS (
  SELECT md5('ec-preview-schedule-v13-' || e.seq)::uuid AS id, e.station_id,
    ((current_date + e.days_ahead + make_interval(hours => e.local_hour))
      AT TIME ZONE CASE WHEN s.country_code = 'US' THEN 'America/New_York' ELSE 'Europe/Prague' END) AS new_start,
    e.duration_hours
  FROM examples e JOIN catalog.stations s ON s.id = e.station_id
), available AS (
  SELECT p.*, p.new_start + make_interval(hours => p.duration_hours) AS new_end
  FROM prepared p
)
UPDATE reservation.station_time_blocks b
SET start_at = p.new_start, end_at = p.new_end
FROM available p
WHERE b.id = p.id AND b.station_id = p.station_id AND b.end_at < now()
  AND NOT EXISTS (
    SELECT 1 FROM reservation.bookings k
    WHERE k.station_id = p.station_id AND k.status = 'CONFIRMED'
      AND k.start_at < p.new_end AND k.end_at > p.new_start
  )
  AND NOT EXISTS (
    SELECT 1 FROM reservation.station_time_blocks t
    WHERE t.station_id = p.station_id AND t.id <> p.id
      AND t.start_at < p.new_end AND t.end_at > p.new_start
  );
