$ErrorActionPreference = "Stop"

$KeyPath = "C:\Users\10156\.ssh\yujian_deploy_ed25519"
$Server = "root@43.140.34.176"
$LocalPort = 3307
$RemoteHost = "127.0.0.1"
$RemotePort = 3306

Write-Host "Starting SSH tunnel: 127.0.0.1:$LocalPort -> $Server -> ${RemoteHost}:$RemotePort"
Write-Host "Keep this window open while local API is running."

ssh -i $KeyPath `
  -o BatchMode=yes `
  -o ExitOnForwardFailure=yes `
  -N `
  -L "${LocalPort}:${RemoteHost}:${RemotePort}" `
  $Server
