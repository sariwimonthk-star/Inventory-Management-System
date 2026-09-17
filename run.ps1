# Keep database writes and Python cache updates from restarting the app.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskFlet = Join-Path $PSScriptRoot '.venv/Scripts/flet.exe'
if (-not (Test-Path -LiteralPath $taskFlet)) { $taskFlet = 'flet' }
& $taskFlet run --recursive --ignore-dirs '.flet,storage,.git,__pycache__,views/__pycache__,tests/__pycache__,.venv,venv' main.py
exit $LASTEXITCODE
