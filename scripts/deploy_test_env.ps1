param(
  [Parameter(Mandatory = $true)]
  [string]$Server,
  [Parameter(Mandatory = $true)]
  [string]$KeyPath,
  [string]$RemoteAppDir = "/opt/yujian_server"
)

$ErrorActionPreference = "Stop"
& "$PSScriptRoot\deploy_env.ps1" -Env test -Server $Server -KeyPath $KeyPath -RemoteAppDir $RemoteAppDir
