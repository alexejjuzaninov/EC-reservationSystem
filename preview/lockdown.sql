ALTER ROLE identity_app NOLOGIN;
ALTER ROLE catalog_app NOLOGIN;
ALTER ROLE booking_app NOLOGIN;
ALTER ROLE billing_app NOLOGIN;
ALTER ROLE notification_app NOLOGIN;
ALTER ROLE replica_reader NOLOGIN;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER ROLE preview_reader PASSWORD :'preview_password';
