param(
    [switch]$OneFile
)

# Non-interactive, repeatable build for Windows .exe using PyInstaller
$ErrorActionPreference = 'Stop'

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found in PATH. Install Python 3.10+ and retry."
}

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller==6.10.0

$entry = "app/main.py"
$name = "OllamaGUI"
$iconPath = ""

$args = @(
    "--name", $name,
    "--noconsole",
    "--clean"
)

if ($OneFile) { $args += "--onefile" } else { $args += "--onedir" }
if ($iconPath -ne "") { $args += @("--icon", $iconPath) }

pyinstaller @args $entry

Write-Host "Build complete. Output in 'dist/$name'"


