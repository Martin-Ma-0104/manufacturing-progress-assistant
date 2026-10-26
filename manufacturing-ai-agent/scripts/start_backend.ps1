$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$Python = Join-Path (Get-Location) "backend/.venv/Scripts/python.exe"
if (!(Test-Path $Python)) { throw "First run: py -3.12 -m venv backend/.venv; then backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt" }
& $Python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
