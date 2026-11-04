-- A believable inbox history for the public copy only. All messages remain stored.
-- Only notifications from the deterministic seed events are changed.
UPDATE notification.messages m
SET read_at = LEAST(now(), m.created_at + interval '1 hour')
FROM reservation.bookings b
WHERE m.booking_id = b.id
  AND m.read_at IS NULL
  AND m.event_id IN (
    md5('ec-preview-booked-event-v10-' || b.id)::uuid,
    md5('ec-preview-booked-event-v19-' || b.id)::uuid,
    md5('ec-preview-v20-event-' || b.id)::uuid)
  AND mod(abs(hashtext(m.id::text)), 7) <> 0;
