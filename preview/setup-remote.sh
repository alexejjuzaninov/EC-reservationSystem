#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
if [ -e preview/.env ]; then
  echo 'Keeping existing preview/.env'
  exit 0
fi
command -v openssl >/dev/null 2>&1 || { echo 'openssl is required to generate credentials.' >&2; exit 1; }
{
  printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'REPLICATION_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'PREVIEW_DB_PASSWORD=%s\n' "$(openssl rand -hex 24)"
} > preview/.env
chmod 600 preview/.env
echo 'Created private preview credentials on this host.'
