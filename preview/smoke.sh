#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
compose() { docker compose --env-file preview/.env -f compose.preview.yaml "$@"; }

printf 'System: '
compose exec -T edge wget -qO- http://127.0.0.1:8080/api/system
printf '\nMap sample: '
compose exec -T edge wget -qO- 'http://127.0.0.1:8080/api/map/explore?country=CZ&west=13.9&south=49.9&east=14.9&north=50.4&zoom=10&limit=6' | head -c 350
printf '\nDashboard sample: '
compose exec -T edge wget -qO- http://127.0.0.1:8080/api/dashboard | head -c 350
printf '\nBlocked write: '
response="$(compose exec -T edge wget -S -O /dev/null --post-data='{}' http://127.0.0.1:8080/api/bookings 2>&1 || true)"
printf '%s\n' "$response" | grep -q '403 Forbidden'
printf '403 Forbidden\n'
