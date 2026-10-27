param([int]$Port = 8501)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$alternatePython = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
$existingPython = Join-Path (Split-Path $PSScriptRoot -Parent) 'datapilot-ai\venv\Scripts\python.exe'
if (Test-Path -LiteralPath $localPython) { $runtimePython = $localPython }
elseif (Test-Path -LiteralPath $alternatePython) { $runtimePython = $alternatePython }
elseif (Test-Path -LiteralPath $existingPython) { $runtimePython = $existingPython }
else { $runtimePython = 'python' }
& $runtimePython app.py --port $Port
