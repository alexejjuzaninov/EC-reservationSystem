CREATE ROLE preview_reader LOGIN PASSWORD 'local_preview_reader';
GRANT CONNECT ON DATABASE ec_reservation TO preview_reader;
GRANT USAGE ON SCHEMA identity, catalog, reservation, billing, notification TO preview_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA identity, catalog, reservation, billing, notification TO preview_reader;
