#!/bin/bash
set -e
mkdir -p "$PGDATA"
chown -R postgres:postgres /var/lib/postgresql/data
chmod 700 "$PGDATA"
echo "db-primary:5432:replication:replicator:${REPLICATION_PASSWORD:-local_replication}" > /var/lib/postgresql/.pgpass
chown postgres:postgres /var/lib/postgresql/.pgpass
chmod 600 /var/lib/postgresql/.pgpass
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  until gosu postgres pg_isready -h db-primary -U postgres -d ec_reservation; do sleep 2; done
  gosu postgres pg_basebackup -h db-primary -D "$PGDATA" -U replicator -Fp -Xs -R
fi
chmod 700 "$PGDATA"
exec gosu postgres postgres -D "$PGDATA" -c hot_standby=on
