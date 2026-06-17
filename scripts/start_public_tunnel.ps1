$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$cloudflared = Join-Path $projectRoot "tools\cloudflared.exe"
$stdout = Join-Path $projectRoot "cloudflared.stdout.log"
$stderr = Join-Path $projectRoot "cloudflared.stderr.log"

if (-not (Test-Path -LiteralPath $cloudflared)) {
    throw "cloudflared not found at $cloudflared"
}

Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

Start-Process `
    -FilePath $cloudflared `
    -ArgumentList "tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    if (Test-Path -LiteralPath $stderr) {
        $match = Select-String -Path $stderr -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
        if ($match) {
            $url = [regex]::Match($match.Line, "https://[a-z0-9-]+\.trycloudflare\.com").Value
            Write-Output "Public tunnel: $url"
            exit 0
        }
    }
}

throw "Tunnel URL was not generated. Check $stderr"
