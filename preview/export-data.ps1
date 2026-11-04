$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$artifactDir = Join-Path $PSScriptRoot 'artifacts'
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
$container = (docker compose -f (Join-Path $projectRoot 'compose.yaml') ps -q db-primary).Trim()
if (-not $container) { throw 'Local primary database is not running.' }
$inside = '/tmp/ec-preview-source-data.dump'
docker exec $container pg_dump -U postgres -d ec_reservation -Fc --data-only --exclude-table=public.flyway_schema_history -f $inside
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed.' }
$destination = Join-Path $artifactDir 'source-data.dump'
docker cp "${container}:${inside}" $destination
if ($LASTEXITCODE -ne 0) { throw 'docker cp failed.' }
docker exec $container rm -f $inside | Out-Null
Get-FileHash $destination -Algorithm SHA256 | Select-Object Path, Hash
