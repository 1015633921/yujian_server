param(
  [string]$Server = "root@43.140.34.176",
  [string]$KeyPath = "C:\Users\10156\.ssh\yujian_deploy_ed25519",
  [string]$RemoteAppDir = "/opt/yujian_server"
)

$ErrorActionPreference = "Stop"
& "$PSScriptRoot\deploy_env.ps1" -Env test -Server $Server -KeyPath $KeyPath -RemoteAppDir $RemoteAppDir
