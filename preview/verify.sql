SELECT json_build_object(
  'stations', (SELECT count(*) FROM catalog.stations),
  'pending_stations', (SELECT count(*) FROM catalog.stations WHERE listing_status = 'PENDING'),
  'bookings', (SELECT count(*) FROM reservation.bookings),
  'notifications', (SELECT count(*) FROM notification.messages),
  'flyway_version', (SELECT max(version::integer) FROM flyway_schema_history),
  'reader_can_update_stations', has_table_privilege('preview_reader', 'catalog.stations', 'UPDATE'),
  'reader_can_select_stations', has_table_privilege('preview_reader', 'catalog.stations', 'SELECT')
);
