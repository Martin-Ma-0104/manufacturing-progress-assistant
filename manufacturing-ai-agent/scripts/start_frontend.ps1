$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "../frontend")
if (!(Test-Path "node_modules")) { throw "First run: cd frontend; npm ci" }
npm.cmd run dev
