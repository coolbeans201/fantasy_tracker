# Stage all changes and commit using COMMIT_MSG.txt at repo root.
# Run: cd C:\Users\matth\fantasy-tracker ; .\scripts\final_commit.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path "COMMIT_MSG.txt")) {
    Write-Error "COMMIT_MSG.txt is missing at the repo root."
}

Write-Host "=== git status (before) ==="
git status -sb

Write-Host "=== git add ==="
git add .

Write-Host "=== git commit ==="
git commit -F COMMIT_MSG.txt

Write-Host "=== commit ==="
git log -1 --format=fuller

Write-Host "=== git status (after) ==="
git status -sb
