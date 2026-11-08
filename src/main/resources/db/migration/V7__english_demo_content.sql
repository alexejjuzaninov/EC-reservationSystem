UPDATE identity.users SET name = CASE id
  WHEN '10000000-0000-0000-0000-000000000001' THEN 'Anna'
  WHEN '10000000-0000-0000-0000-000000000002' THEN 'Ilya'
  WHEN '10000000-0000-0000-0000-000000000005' THEN 'Mark'
  WHEN '10000000-0000-0000-0000-000000000006' THEN 'Elena · administrator'
  ELSE name END
WHERE id IN (
  '10000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000002',
  '10000000-0000-0000-0000-000000000005',
  '10000000-0000-0000-0000-000000000006'
);

UPDATE catalog.stations SET
  name = CASE id
    WHEN '20000000-0000-0000-0000-000000000002' THEN 'Stromovka Home Charger'
    ELSE name END,
  owner_name = CASE WHEN owner_id = '10000000-0000-0000-0000-000000000002' THEN 'Ilya' ELSE owner_name END,
  access_note = CASE id
    WHEN '20000000-0000-0000-0000-000000000001' THEN 'Enter through the courtyard, bay 04'
    WHEN '20000000-0000-0000-0000-000000000002' THEN 'Ring apartment 12'
    WHEN '20000000-0000-0000-0000-000000000003' THEN 'Car park B, level -1'
    WHEN '20000000-0000-0000-0000-000000000004' THEN 'Open 24/7'
    ELSE access_note END
WHERE synthetic = FALSE;

UPDATE catalog.stations SET
  name = 'Demo charger ' || substring(name FROM '[0-9]+$'),
  owner_name = CASE owner_kind
    WHEN 'PLATFORM' THEN 'Demo network '
    WHEN 'COMPANY' THEN 'Demo company '
    ELSE 'Demo host ' END || substring(owner_name FROM '[0-9]+$'),
  access_note = 'Fictional location for the map preview'
WHERE synthetic = TRUE;
