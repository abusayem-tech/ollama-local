param(
    [string]$ApiKey = "",
    [string]$AllowOrigins = "*",
    [string]$Host = "0.0.0.0",
    [int]$Port = 8080,
    [string]$OllamaHost = "127.0.0.1",
    [int]$OllamaPort = 11434
)

$ErrorActionPreference = 'Stop'

python -m pip install -r requirements.txt | Out-Null

$repoRoot = Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH = "$repoRoot"

$env:API_KEY = $ApiKey
$env:ALLOW_ORIGINS = $AllowOrigins
$env:SERVER_HOST = $Host
$env:SERVER_PORT = $Port
$env:OLLAMA_HOST = $OllamaHost
$env:OLLAMA_PORT = $OllamaPort

python -m server.main


