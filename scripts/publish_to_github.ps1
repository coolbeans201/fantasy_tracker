# Create GitHub repo fantasy_tracker and push (safe to re-run)
# Run: cd C:\Users\matth\fantasy-tracker ; .\scripts\publish_to_github.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

function Require-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "$name is not on PATH. Install it and try again."
    }
}

Require-Command git
Require-Command gh

if (-not (Test-Path ".git")) {
    Write-Host "=== git init ==="
    git init -b main
}

function Commit-FromMessageFile {
    if (-not (Test-Path "COMMIT_MSG.txt")) {
        Write-Error "COMMIT_MSG.txt is missing. Add a commit message at the repo root."
    }
    Write-Host "=== git add & commit (COMMIT_MSG.txt) ==="
    git add .
    git commit -F COMMIT_MSG.txt
}

$hasCommit = git rev-parse HEAD 2>$null
$dirty = git status --porcelain 2>$null

if (-not $hasCommit) {
    Commit-FromMessageFile
} elseif ($dirty) {
    Commit-FromMessageFile
} else {
    Write-Host "=== working tree clean ==="
    git log -1 --oneline
}

$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Write-Host "=== creating GitHub repo and pushing ==="
    gh auth status
    gh repo create fantasy_tracker --public --source=. --remote=origin --push
} else {
    Write-Host "=== remote exists, pushing ==="
    git push -u origin main
}

Write-Host ""
Write-Host "Repository URL:"
gh repo view --json url -q .url
