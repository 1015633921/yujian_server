param(
  [ValidateSet("test", "prod")]
  [string]$Env = "test",
  [string]$Server = "",
  [string]$KeyPath = "",
  [string]$RemoteAppDir = "/opt/yujian_server"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Server) -or [string]::IsNullOrWhiteSpace($KeyPath)) {
  throw "Legacy deployment requires explicit -Server and -KeyPath values. Prefer scripts/release/*."
}
if ($Env -eq "prod" -and $env:ALLOW_LEGACY_INPLACE_DEPLOY -ne "1") {
  throw "Legacy in-place production deployment is blocked. Use immutable release deployment."
}

$Root = Split-Path -Parent $PSScriptRoot
$Service = if ($Env -eq "prod") { "api" } else { "api-test" }
$PackageName = if ($Env -eq "prod") { "yujian_prod_deploy_current.tar.gz" } else { "yujian_test_deploy_current.tar.gz" }
$LocalHealth = if ($Env -eq "prod") { "http://127.0.0.1:8000/health" } else { "http://127.0.0.1:8001/health" }
$PublicHealth = if ($Env -eq "prod") { "https://api.yustream.cn/health" } else { "https://api.yustream.cn/test-api/health" }
$PackagePath = Join-Path $Root $PackageName
$RemotePackage = "/tmp/$PackageName"

function Step($Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

if (-not (Test-Path $KeyPath)) {
  throw "SSH key not found: $KeyPath"
}

Set-Location $Root

Step "Packing backend + admin static files for $Env"
if (Test-Path $PackagePath) {
  Remove-Item -LiteralPath $PackagePath -Force
}
tar -czf $PackagePath app static scripts/migrate_sqlite_to_mysql.py scripts/regenerate_material_skus_and_knowledge.py requirements.txt Dockerfile compose.yaml

Step "Uploading package to $Server"
scp -i $KeyPath $PackagePath "${Server}:$RemotePackage"

Step "Deploying and restarting $Service"
$RemoteCommand = "set -e; cd $RemoteAppDir && tar -xzf $RemotePackage -C $RemoteAppDir && docker compose build $Service && docker compose up -d $Service && docker compose ps $Service && for i in 1 2 3 4 5 6 7 8 9 10; do if curl -fsS $LocalHealth; then exit 0; fi; sleep 2; done; echo 'health check failed' >&2; exit 1"
ssh -i $KeyPath -o BatchMode=yes $Server $RemoteCommand

Step "Done"
Write-Host "$Env API: $PublicHealth" -ForegroundColor Green
