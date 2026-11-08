-- Generated Czech map samples use Czech-style fictional street names.
-- Curated listings and manually created stations keep their existing addresses.
UPDATE catalog.stations s
SET address = (ARRAY['Javorová', 'Lipová', 'U Parku', 'Na Stráni', 'Pod Hájem',
                     'U Nádraží', 'Školní', 'Sadová', 'Na Výsluní', 'Luční',
                     'Rybářská', 'Křižná'])
                 [1 + mod(abs(hashtext(s.id::text || 'cz-street')), 12)] || ' ' ||
                 (1 + mod(abs(hashtext(s.id::text || 'cz-house')), 96))
WHERE s.synthetic = TRUE AND s.country_code = 'CZ'
  AND s.created_at = '2025-01-01 00:00:00+00'::timestamptz;

UPDATE reservation.bookings b
SET station_address = s.address
FROM catalog.stations s
WHERE b.station_id = s.id AND s.synthetic = TRUE AND s.country_code = 'CZ'
  AND b.id IN (SELECT md5('ec-preview-booking-v10-' || n)::uuid FROM generate_series(1,16) n);
