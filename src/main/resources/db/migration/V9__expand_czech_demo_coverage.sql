-- Fictional station coordinates are sampled around real city centers from
-- GeoNames CZ country extract (https://www.geonames.org/export/), CC BY 4.0.
-- No addresses, chargers, or business records are sourced from GeoNames.
SELECT setseed(0.619);
WITH hubs(hub_no, city, latitude, longitude, latitude_spread, longitude_spread, sample_count) AS (
  VALUES
    (1, 'Praha', 50.08804, 14.42076, 0.13, 0.19, 9000),
    (2, 'Brno', 49.19522, 16.60796, 0.1, 0.15, 3000),
    (3, 'Ostrava', 49.83465, 18.28204, 0.1, 0.15, 2000),
    (4, 'Plzeň', 49.74747, 13.37759, 0.07, 0.1, 1200),
    (5, 'Olomouc', 49.59552, 17.25175, 0.07, 0.1, 1200),
    (6, 'Liberec', 50.76711, 15.05619, 0.07, 0.1, 1000),
    (7, 'České Budějovice', 48.97447, 14.47434, 0.07, 0.1, 1000),
    (8, 'Hradec Králové', 50.20923, 15.83277, 0.035, 0.055, 900),
    (9, 'Pardubice', 50.04075, 15.77659, 0.035, 0.055, 900),
    (10, 'Zlín', 49.22645, 17.67065, 0.035, 0.055, 800),
    (11, 'Ústí nad Labem', 50.6607, 14.03227, 0.035, 0.055, 800),
    (12, 'Jihlava', 49.3961, 15.59124, 0.035, 0.055, 700),
    (13, 'Karlovy Vary', 50.23271, 12.87117, 0.035, 0.055, 700),
    (14, 'Kladno', 50.14734, 14.10285, 0.035, 0.055, 700),
    (15, 'Mladá Boleslav', 50.41135, 14.90318, 0.035, 0.055, 650),
    (16, 'Kolín', 50.02806, 15.1998, 0.035, 0.055, 600),
    (17, 'Tábor', 49.41441, 14.6578, 0.035, 0.055, 600),
    (18, 'Písek', 49.3088, 14.1475, 0.035, 0.055, 500),
    (19, 'Znojmo', 48.8555, 16.0488, 0.035, 0.055, 500),
    (20, 'Třebíč', 49.21492, 15.88166, 0.035, 0.055, 500),
    (21, 'Opava', 49.93866, 17.90257, 0.035, 0.055, 600),
    (22, 'Frýdek-Místek', 49.68333, 18.35, 0.035, 0.055, 600),
    (23, 'Havířov', 49.77984, 18.43688, 0.035, 0.055, 600),
    (24, 'Přerov', 49.45511, 17.4509, 0.035, 0.055, 500),
    (25, 'Prostějov', 49.47188, 17.11184, 0.035, 0.055, 500),
    (26, 'Kroměříž', 49.29785, 17.39312, 0.035, 0.055, 450),
    (27, 'Vsetín', 49.33871, 17.99619, 0.035, 0.055, 450),
    (28, 'Děčín', 50.78215, 14.21478, 0.035, 0.055, 500),
    (29, 'Teplice', 50.6404, 13.82451, 0.035, 0.055, 500),
    (30, 'Most', 50.50301, 13.63617, 0.035, 0.055, 500),
    (31, 'Chomutov', 50.46048, 13.41779, 0.035, 0.055, 500),
    (32, 'Česká Lípa', 50.68551, 14.53764, 0.035, 0.055, 450),
    (33, 'Trutnov', 50.56101, 15.9127, 0.035, 0.055, 450),
    (34, 'Náchod', 50.4167, 16.16289, 0.035, 0.055, 450),
    (35, 'Benešov', 49.78162, 14.68697, 0.035, 0.055, 450),
    (36, 'Beroun', 49.96382, 14.072, 0.035, 0.055, 450),
    (37, 'Kutná Hora', 49.94839, 15.26816, 0.035, 0.055, 450),
    (38, 'Turnov', 50.58356, 15.15186, 0.035, 0.055, 450),
    (39, 'Šumperk', 49.96528, 16.97061, 0.035, 0.055, 450),
    (40, 'Jindřichův Hradec', 49.14404, 15.00301, 0.035, 0.055, 450),
    (41, 'Uherské Hradiště', 49.06975, 17.45969, 0.035, 0.055, 450),
    (42, 'Litoměřice', 50.53348, 14.1318, 0.035, 0.055, 450),
    (43, 'Svitavy', 49.75594, 16.46829, 0.035, 0.055, 450),
    (44, 'Cheb', 50.07963, 12.37392, 0.035, 0.055, 450),
    (45, 'Domažlice', 49.44049, 12.92976, 0.035, 0.055, 400),
    (46, 'Klatovy', 49.39552, 13.29505, 0.035, 0.055, 400),
    (47, 'Hodonín', 48.84893, 17.13244, 0.035, 0.055, 450),
    (48, 'Břeclav', 48.75897, 16.88203, 0.035, 0.055, 450),
    (49, 'Mariánské Lázně', 49.96459, 12.70118, 0.035, 0.055, 400),
    (50, 'Český Krumlov', 48.81091, 14.31521, 0.035, 0.055, 450)
), generated AS (
  SELECT h.*, g.sample_no, h.hub_no * 100000 + g.sample_no AS n
  FROM hubs h CROSS JOIN LATERAL generate_series(1, h.sample_count) AS g(sample_no)
)
INSERT INTO catalog.stations
  (id, owner_id, owner_name, owner_kind, name, address, city, connector, power_kw,
   price_per_hour_cents, access_note, active, created_at, country_code, location, synthetic)
SELECT
  md5('cz-expanded-station-' || n)::uuid,
  md5('cz-expanded-owner-' || n)::uuid,
  CASE WHEN n % 3 = 0 THEN 'Demo network #' || n
       WHEN n % 3 = 1 THEN 'Demo host #' || n ELSE 'Demo company #' || n END,
  CASE WHEN n % 3 = 0 THEN 'PLATFORM' WHEN n % 3 = 1 THEN 'PERSON' ELSE 'COMPANY' END,
  CASE WHEN n % 4 = 0 THEN 'Fast charge hub'
       WHEN n % 5 = 0 THEN 'Parkside charger'
       WHEN n % 5 = 1 THEN 'Neighborhood plug'
       WHEN n % 5 = 2 THEN 'Community charger'
       ELSE 'City charge point' END || ' #' || n,
  'Sample street ' || (sample_no % 999 + 1),
  city,
  CASE WHEN n % 4 = 0 THEN 'CCS2' ELSE 'Type 2' END,
  CASE WHEN n % 4 = 0 THEN 50 + (n % 3) * 25 ELSE 7 + (n % 4) * 5 END,
  7900 + (n % 12) * 1500,
  'Fictional location for the map preview',
  TRUE,
  '2025-01-01 00:00:00+00'::timestamptz,
  'CZ',
  ST_SetSRID(ST_MakePoint(longitude + (random() - 0.5) * longitude_spread,
                         latitude + (random() - 0.5) * latitude_spread), 4326),
  TRUE
FROM generated;

UPDATE catalog.stations
SET name = CASE WHEN substring(name FROM '[0-9]+$')::integer % 4 = 0 THEN 'Fast charge hub'
                WHEN substring(name FROM '[0-9]+$')::integer % 5 = 0 THEN 'Parkside charger'
                WHEN substring(name FROM '[0-9]+$')::integer % 5 = 1 THEN 'Neighborhood plug'
                WHEN substring(name FROM '[0-9]+$')::integer % 5 = 2 THEN 'Community charger'
                ELSE 'City charge point' END || ' #' || substring(name FROM '[0-9]+$')
WHERE synthetic = TRUE AND name LIKE 'Demo charger %';

ANALYZE catalog.stations;
