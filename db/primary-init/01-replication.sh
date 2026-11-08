#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v password="${REPLICATION_PASSWORD:-local_replication}" <<'SQL'
CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD :'password';
SQL
