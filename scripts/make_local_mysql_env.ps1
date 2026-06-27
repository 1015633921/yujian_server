$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Source = Join-Path $Root ".env"
$Target = Join-Path $Root ".env.local"

if (!(Test-Path $Source)) {
  throw ".env not found: $Source"
}

$values = @{}
Get-Content $Source | ForEach-Object {
  $line = $_.Trim()
  if ($line -and !$line.StartsWith("#") -and $line.Contains("=")) {
    $parts = $line.Split("=", 2)
    $values[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
  }
}

foreach ($required in @("MYSQL_USER", "MYSQL_PASSWORD")) {
  if (!$values.ContainsKey($required) -or !$values[$required]) {
    throw "$required is missing in .env"
  }
}

@(
  "APP_ENV=local",
  "DATABASE_BACKEND=mysql",
  "MYSQL_HOST=127.0.0.1",
  "MYSQL_PORT=3307",
  "MYSQL_DATABASE=yujian_local",
  "MYSQL_USER=$($values["MYSQL_USER"])",
  "MYSQL_PASSWORD=$($values["MYSQL_PASSWORD"])",
  "WECHAT_PAY_TEST_MODE=true",
  "LOGISTICS_SYNC_ENABLED=false"
) | Set-Content -Path $Target -Encoding UTF8

Write-Host "Wrote $Target"
