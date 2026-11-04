$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
  mvn -q -DskipTests package
  if ($LASTEXITCODE -ne 0) { throw 'Maven package failed.' }
  & (Join-Path $PSScriptRoot 'export-data.ps1')
  if ($LASTEXITCODE -ne 0) { throw 'Snapshot export failed.' }
  $archive = Join-Path $PSScriptRoot 'artifacts/ec-preview-source.tar.gz'
  $files = @(
    'Dockerfile.preview', 'Dockerfile.preview.dockerignore', 'pom.xml',
    'compose.preview.yaml', 'compose.preview.tunnel.yaml',
    'src', 'db', 'target/reservation-preview-0.1.0.jar',
    'preview/deploy.sh', 'preview/setup-remote.sh', 'preview/smoke.sh', 'preview/restore.sql', 'preview/polish-data.sql', 'preview/lockdown.sql', 'preview/verify.sql',
    'preview/nginx.conf', 'preview/nginx-main.conf',
    'preview/.env.example', 'preview/README.md'
  )
  tar -czf $archive @files
  if ($LASTEXITCODE -ne 0) { throw 'Archive creation failed.' }
  Get-FileHash $archive -Algorithm SHA256 | Select-Object Path, Hash
} finally { Pop-Location }
