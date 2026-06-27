param(
  [ValidateSet("test", "prod")]
  [string]$Env = "test",
  [switch]$SkipAssetUpload,
  [switch]$DryRunAssets
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Step($Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

Set-Location $Root

Step "Selecting mini-program config: $Env"
node scripts/select_miniprogram_env.js $Env

if (-not $SkipAssetUpload) {
  Step "Uploading mini-program assets to $Env COS"
  $assetArgs = @("scripts/upload_miniprogram_assets_to_cos.py", "--env", $Env)
  if ($DryRunAssets) {
    $assetArgs += "--dry-run"
  }
  & .\.venv_codex\Scripts\python.exe @assetArgs
}

Step "Checking mini-program JavaScript syntax"
$jsFiles = Get-ChildItem -Recurse miniprogram -Filter *.js -File |
  Where-Object { $_.FullName -notmatch '\\node_modules\\' }
foreach ($file in $jsFiles) {
  node --check $file.FullName | Out-Null
}
Write-Host "JS syntax OK: $($jsFiles.Count) files" -ForegroundColor Green

Step "Checking mini-program JSON files"
node -e "const fs=require('fs'),path=require('path');function walk(d,a=[]){for(const x of fs.readdirSync(d,{withFileTypes:true})){const p=path.join(d,x.name);if(x.isDirectory()&&x.name!=='node_modules')walk(p,a);else if(x.isFile()&&p.endsWith('.json'))a.push(p)}return a}for(const f of walk('miniprogram'))JSON.parse(fs.readFileSync(f,'utf8'));console.log('JSON OK')"

Write-Host ""
Write-Host "Mini-program package config is ready for: $Env" -ForegroundColor Green
if ($Env -eq "prod") {
  Write-Host "Open WeChat DevTools and upload the miniprogram package now." -ForegroundColor Yellow
}
