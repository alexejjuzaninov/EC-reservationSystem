#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
test -f preview/.env || { echo 'Missing preview/.env' >&2; exit 1; }
test -f preview/artifacts/source-data.dump || { echo 'Missing preview/artifacts/source-data.dump' >&2; exit 1; }
chmod 600 preview/.env preview/artifacts/source-data.dump
set -a
. ./preview/.env
set +a
compose() { docker compose --env-file preview/.env -f compose.preview.yaml "$@"; }

compose build app
compose up -d db-primary db-replica redis
compose --profile setup run --rm migrate

primary_id="$(compose ps -q db-primary)"
docker cp preview/artifacts/source-data.dump "$primary_id:/tmp/source-data.dump"
compose exec -T db-primary psql -v ON_ERROR_STOP=1 -U postgres -d ec_reservation < preview/restore.sql
compose exec -T db-primary pg_restore --exit-on-error --data-only --no-owner --no-privileges -U postgres -d ec_reservation /tmp/source-data.dump
compose exec -T db-primary psql -v ON_ERROR_STOP=1 -U postgres -d ec_reservation < preview/polish-data.sql
compose exec -T db-primary psql -v ON_ERROR_STOP=1 -v preview_password="$PREVIEW_DB_PASSWORD" -U postgres -d ec_reservation < preview/lockdown.sql
compose exec -T db-primary rm -f /tmp/source-data.dump

compose up -d app edge
ready=0
attempt=0
while [ "$attempt" -lt 30 ]; do
  if compose exec -T edge wget -qO- http://127.0.0.1:8080/api/system; then
    ready=1
    break
  fi
  attempt=$((attempt + 1))
  sleep 2
done
test "$ready" -eq 1 || { echo 'Preview did not become healthy.' >&2; exit 1; }
echo
echo 'Preview stack is ready. Add a dedicated Cloudflare tunnel token and start the tunnel service separately.'
