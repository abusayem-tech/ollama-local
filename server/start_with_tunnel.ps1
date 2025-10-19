param(
    [string]$ApiKey = "",
    [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'

# Ensure cloudflared is available
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "cloudflared not found. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/" -ForegroundColor Yellow
}

# Open Windows Firewall for inbound port if needed
try {
    netsh advfirewall firewall add rule name="OllamaProxy $Port" dir=in action=allow protocol=TCP localport=$Port | Out-Null
} catch {}

Start-Job -ScriptBlock {
    param($ApiKey, $Port)
    $here = Split-Path $MyInvocation.MyCommand.Path -Parent
    Set-Location $here
    ./run_server.ps1 -ApiKey $ApiKey -AllowOrigins * -Host 0.0.0.0 -Port $Port -OllamaHost 127.0.0.1 -OllamaPort 11434
} -ArgumentList $ApiKey, $Port | Out-Null

Start-Sleep -Seconds 2

if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
    cloudflared tunnel --url "http://localhost:$Port"
} else {
    Write-Host "Server started on http://localhost:$Port. Install cloudflared or use ngrok to expose." -ForegroundColor Green
}


