ALTER TABLE identity.users DROP CONSTRAINT users_kind_check;
ALTER TABLE identity.users ADD CONSTRAINT users_kind_check
  CHECK (kind IN ('DRIVER', 'PERSON', 'COMPANY', 'PLATFORM', 'ADMIN'));
INSERT INTO identity.users VALUES
  ('10000000-0000-0000-0000-000000000005', 'Марк', 'DRIVER'),
  ('10000000-0000-0000-0000-000000000006', 'Елена · администратор', 'ADMIN');

ALTER TABLE catalog.stations
  ADD COLUMN listing_status TEXT NOT NULL DEFAULT 'APPROVED'
    CHECK (listing_status IN ('PENDING', 'APPROVED', 'REJECTED'));
CREATE INDEX stations_pending_idx ON catalog.stations (created_at DESC)
  WHERE listing_status = 'PENDING';
CREATE TABLE catalog.outbox (
  id UUID PRIMARY KEY,
  station_id UUID NOT NULL,
  owner_id UUID NOT NULL,
  event_type TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  notification_processed_at TIMESTAMPTZ
);
GRANT SELECT, INSERT, UPDATE ON catalog.outbox TO catalog_app;

ALTER TABLE reservation.outbox
  ADD COLUMN billing_processed_at TIMESTAMPTZ,
  ADD COLUMN notification_processed_at TIMESTAMPTZ;
UPDATE reservation.outbox SET billing_processed_at = processed_at WHERE processed_at IS NOT NULL;

CREATE ROLE notification_app LOGIN PASSWORD 'local_notification';
CREATE SCHEMA notification;
CREATE TABLE notification.messages (
  id UUID PRIMARY KEY,
  event_id UUID NOT NULL,
  user_id UUID NOT NULL,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  booking_id UUID,
  station_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  read_at TIMESTAMPTZ,
  UNIQUE (event_id, user_id)
);
CREATE INDEX notifications_user_idx ON notification.messages (user_id, created_at DESC);
GRANT USAGE ON SCHEMA notification TO notification_app;
GRANT SELECT, INSERT, UPDATE ON notification.messages TO notification_app;
