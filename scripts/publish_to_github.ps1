# One-time: initial commit and create GitHub repo fantasy_tracker
# Run from project root: .\scripts\publish_to_github.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path "COMMIT_MSG.txt")) {
    Write-Error "COMMIT_MSG.txt not found in project root."
}

Write-Host "=== git init ==="
git init -b main

Write-Host "=== git add ==="
git add .

Write-Host "=== staged files ==="
git status --short

Write-Host "=== git commit ==="
git commit -F COMMIT_MSG.txt

Write-Host "=== commit ==="
git log -1 --format=fuller

Write-Host "=== gh repo create ==="
gh repo create fantasy_tracker --public --source=. --remote=origin --push

Write-Host "=== done ==="
gh repo view --json url -q .url
