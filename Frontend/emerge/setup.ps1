# FunRad - EMerge environment (Windows PowerShell)
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = "py"
try { & $py -3.12 --version | Out-Null } catch { $py = "python" }

Write-Host "creating .venv ..." -ForegroundColor Cyan
if ($py -eq "py") { & py -3.12 -m venv .venv } else { & python -m venv .venv }

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host ""
Write-Host "done. activate with:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "then:                 python coupler_catalogue.py"
Write-Host "                      python redesign.py redesign_configs/final51_copper9.json"
