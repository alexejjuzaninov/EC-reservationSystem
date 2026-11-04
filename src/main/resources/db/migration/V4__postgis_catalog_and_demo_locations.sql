CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE catalog.stations
  ADD COLUMN country_code CHAR(2) NOT NULL DEFAULT 'CZ',
  ADD COLUMN location geometry(Point, 4326),
  ADD COLUMN synthetic BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE catalog.stations SET location = ST_SetSRID(ST_MakePoint(14.4580, 50.0920), 4326)
  WHERE id = '20000000-0000-0000-0000-000000000001';
UPDATE catalog.stations SET location = ST_SetSRID(ST_MakePoint(14.4200, 50.1060), 4326)
  WHERE id = '20000000-0000-0000-0000-000000000002';
UPDATE catalog.stations SET location = ST_SetSRID(ST_MakePoint(16.5990, 49.1980), 4326)
  WHERE id = '20000000-0000-0000-0000-000000000003';
UPDATE catalog.stations SET location = ST_SetSRID(ST_MakePoint(14.4320, 50.0990), 4326)
  WHERE id = '20000000-0000-0000-0000-000000000004';

SELECT setseed(0.42);
WITH hubs(country_code, hub_no, city, latitude, longitude, latitude_spread, longitude_spread) AS (
  VALUES
    ('CZ',1,'Praha',50.0755,14.4378,0.25,0.42),
    ('CZ',2,'Brno',49.1951,16.6068,0.20,0.30),
    ('CZ',3,'Ostrava',49.8209,18.2625,0.18,0.26),
    ('CZ',4,'Plzeň',49.7384,13.3736,0.18,0.25),
    ('CZ',5,'Olomouc',49.5938,17.2509,0.16,0.22),
    ('CZ',6,'Liberec',50.7663,15.0543,0.15,0.20),
    ('CZ',7,'České Budějovice',48.9745,14.4743,0.16,0.22),
    ('CZ',8,'Hradec Králové',50.2092,15.8328,0.15,0.21),
    ('US',1,'New York',40.7128,-74.0060,0.38,0.55),
    ('US',2,'Los Angeles',34.0522,-118.2437,0.42,0.65),
    ('US',3,'San Francisco',37.7749,-122.4194,0.25,0.35),
    ('US',4,'Chicago',41.8781,-87.6298,0.38,0.51),
    ('US',5,'Seattle',47.6062,-122.3321,0.31,0.42),
    ('US',6,'Austin',30.2672,-97.7431,0.30,0.43),
    ('US',7,'Boston',42.3601,-71.0589,0.27,0.35),
    ('US',8,'Denver',39.7392,-104.9903,0.30,0.43),
    ('US',9,'Miami',25.7617,-80.1918,0.30,0.36),
    ('US',10,'Washington',38.9072,-77.0369,0.28,0.37),
    ('US',11,'Dallas',32.7767,-96.7970,0.37,0.51),
    ('US',12,'Atlanta',33.7490,-84.3880,0.31,0.43),
    ('US',13,'Phoenix',33.4484,-112.0740,0.38,0.50),
    ('US',14,'Portland',45.5152,-122.6784,0.30,0.39),
    ('US',15,'San Diego',32.7157,-117.1611,0.30,0.40)
), generated AS (
  SELECT n, h.*, CASE WHEN n % 4 = 0 THEN 'CCS2' ELSE 'Type 2' END AS plug
  FROM generate_series(1, 100000) AS n
  JOIN hubs h ON h.country_code = CASE WHEN n <= 25000 THEN 'CZ' ELSE 'US' END
    AND h.hub_no = CASE WHEN n <= 25000 THEN (n % 8) + 1 ELSE (n % 15) + 1 END
)
INSERT INTO catalog.stations
  (id, owner_id, owner_name, owner_kind, name, address, city, connector, power_kw,
   price_per_hour_cents, access_note, active, created_at, country_code, location, synthetic)
SELECT
  md5('demo-station-' || n)::uuid,
  md5('demo-owner-' || n)::uuid,
  CASE WHEN n % 3 = 0 THEN 'Демо-сеть #' || n WHEN n % 3 = 1 THEN 'Демо-владелец #' || n ELSE 'Демо-компания #' || n END,
  CASE WHEN n % 3 = 0 THEN 'PLATFORM' WHEN n % 3 = 1 THEN 'PERSON' ELSE 'COMPANY' END,
  'Демо-станция ' || n,
  'Demo street ' || (n % 5000 + 1),
  city,
  plug,
  CASE WHEN plug = 'CCS2' THEN 50 + (n % 4) * 25 ELSE 7 + (n % 4) * 5 END,
  CASE WHEN country_code = 'CZ' THEN 7900 + (n % 12) * 1500 ELSE 12000 + (n % 12) * 1800 END,
  'Фиктивная точка для демонстрации карты',
  TRUE,
  '2025-01-01 00:00:00+00'::timestamptz,
  country_code,
  ST_SetSRID(ST_MakePoint(longitude + (random() - 0.5) * longitude_spread,
                         latitude + (random() - 0.5) * latitude_spread), 4326),
  TRUE
FROM generated;

ALTER TABLE catalog.stations ALTER COLUMN location SET NOT NULL;
CREATE INDEX stations_location_gix ON catalog.stations USING gist (location);
CREATE INDEX stations_country_city_idx ON catalog.stations (country_code, city);
ANALYZE catalog.stations;
