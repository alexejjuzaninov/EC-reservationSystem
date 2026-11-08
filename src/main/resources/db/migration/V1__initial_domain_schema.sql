CREATE ROLE identity_app LOGIN PASSWORD 'local_identity';
CREATE ROLE catalog_app LOGIN PASSWORD 'local_catalog';
CREATE ROLE booking_app LOGIN PASSWORD 'local_booking';
CREATE ROLE billing_app LOGIN PASSWORD 'local_billing';
CREATE ROLE replica_reader LOGIN PASSWORD 'local_reader';

CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE SCHEMA identity;
CREATE SCHEMA catalog;
CREATE SCHEMA reservation;
CREATE SCHEMA billing;

CREATE TABLE identity.users (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('DRIVER', 'PERSON', 'COMPANY', 'PLATFORM'))
);

CREATE TABLE catalog.stations (
  id UUID PRIMARY KEY,
  owner_id UUID NOT NULL,
  owner_name TEXT NOT NULL,
  owner_kind TEXT NOT NULL CHECK (owner_kind IN ('PERSON', 'COMPANY', 'PLATFORM')),
  name TEXT NOT NULL,
  address TEXT NOT NULL,
  city TEXT NOT NULL,
  connector TEXT NOT NULL,
  power_kw INTEGER NOT NULL CHECK (power_kw > 0),
  price_per_hour_cents INTEGER NOT NULL CHECK (price_per_hour_cents >= 0),
  access_note TEXT NOT NULL DEFAULT '',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX stations_city_idx ON catalog.stations (city);

CREATE TABLE reservation.bookings (
  id UUID PRIMARY KEY,
  station_id UUID NOT NULL,
  station_name TEXT NOT NULL,
  owner_id UUID NOT NULL,
  owner_kind TEXT NOT NULL,
  driver_id UUID NOT NULL,
  driver_name TEXT NOT NULL,
  start_at TIMESTAMPTZ NOT NULL,
  end_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('CONFIRMED', 'CANCELLED')),
  total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
  platform_fee_cents INTEGER NOT NULL CHECK (platform_fee_cents >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT valid_interval CHECK (start_at < end_at AND end_at <= start_at + interval '4 hours'),
  CONSTRAINT no_overlapping_confirmed_bookings EXCLUDE USING gist
    (station_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
    WHERE (status = 'CONFIRMED')
);
CREATE INDEX bookings_driver_idx ON reservation.bookings (driver_id, start_at DESC);
CREATE INDEX bookings_owner_idx ON reservation.bookings (owner_id, start_at DESC);
CREATE TABLE reservation.outbox (
  id UUID PRIMARY KEY,
  booking_id UUID NOT NULL,
  event_type TEXT NOT NULL,
  total_cents INTEGER NOT NULL,
  platform_fee_cents INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at TIMESTAMPTZ
);
CREATE INDEX outbox_pending_idx ON reservation.outbox (created_at) WHERE processed_at IS NULL;

CREATE TABLE billing.simulated_charges (
  booking_id UUID PRIMARY KEY,
  total_cents INTEGER NOT NULL,
  platform_fee_cents INTEGER NOT NULL,
  owner_payout_cents INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('SIMULATED', 'CANCELLED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT USAGE ON SCHEMA identity TO identity_app, replica_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA identity TO identity_app, replica_reader;
GRANT USAGE ON SCHEMA catalog TO catalog_app, replica_reader;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA catalog TO catalog_app;
GRANT SELECT ON ALL TABLES IN SCHEMA catalog TO replica_reader;
GRANT USAGE ON SCHEMA reservation TO booking_app, replica_reader;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA reservation TO booking_app;
GRANT SELECT ON ALL TABLES IN SCHEMA reservation TO replica_reader;
GRANT USAGE ON SCHEMA billing TO billing_app, replica_reader;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA billing TO billing_app;
GRANT SELECT ON ALL TABLES IN SCHEMA billing TO replica_reader;

INSERT INTO identity.users VALUES
  ('10000000-0000-0000-0000-000000000001', 'Анна', 'DRIVER'),
  ('10000000-0000-0000-0000-000000000002', 'Илья', 'PERSON'),
  ('10000000-0000-0000-0000-000000000003', 'VoltHouse s.r.o.', 'COMPANY'),
  ('10000000-0000-0000-0000-000000000004', 'EC Network', 'PLATFORM');

INSERT INTO catalog.stations (id, owner_id, owner_name, owner_kind, name, address, city, connector, power_kw, price_per_hour_cents, access_note) VALUES
  ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000004', 'EC Network', 'PLATFORM', 'Karlín Hub', 'Křižíkova 14', 'Praha', 'CCS2', 120, 24900, 'Въезд со двора, место 04'),
  ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', 'Илья', 'PERSON', 'Дом у Стромовки', 'Nad Štolou 8', 'Praha', 'Type 2', 11, 8900, 'Позвоните в домофон 12'),
  ('20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000003', 'VoltHouse s.r.o.', 'COMPANY', 'Brno Campus', 'Veveří 70', 'Brno', 'CCS2', 50, 17900, 'Парковка B, уровень -1'),
  ('20000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000004', 'EC Network', 'PLATFORM', 'Letná Point', 'Milady Horákové 92', 'Praha', 'Type 2', 22, 12900, 'Доступ 24/7');
