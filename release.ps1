param()

$ErrorActionPreference = 'Stop'

$repoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$manifestPath = Join-Path $repoRoot 'custom_components/elco_remocon/manifest.json'
$readmePath = Join-Path $repoRoot 'README.md'

function Resolve-GhCommand {
    $command = Get-Command gh -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $fallbackPaths = @(
        'C:\Program Files\GitHub CLI\gh.exe',
        'C:\Program Files (x86)\GitHub CLI\gh.exe'
    )

    foreach ($fallbackPath in $fallbackPaths) {
        if (Test-Path -Path $fallbackPath) {
            return $fallbackPath
        }
    }

    throw 'gh is required (install GitHub CLI and run gh auth login)'
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git is required'
}

$ghCommand = Resolve-GhCommand

if (& $ghCommand auth status 2>$null) {
    # authenticated
}
else {
    throw 'gh is not authenticated. Run gh auth login first.'
}

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command python3 -ErrorAction SilentlyContinue)) {
    throw 'python is required to read the manifest version'
}

if (-not (Test-Path -Path $manifestPath)) {
    throw "Manifest not found: $manifestPath"
}

if (-not (Test-Path -Path $readmePath)) {
    throw "README not found: $readmePath"
}

Set-Location $repoRoot

if (-not (git remote get-url origin 2>$null)) {
    throw "git remote 'origin' is missing"
}

$currentBranch = git branch --show-current
if ($currentBranch -ne 'main') {
    throw "This script must be run on main (current branch: $currentBranch)"
}

$gitStatus = git status --short
if ($gitStatus) {
    throw 'Working tree is not clean. Commit or stash your changes first.'
}

$pythonCommand = 'python'
if (-not (Get-Command $pythonCommand -ErrorAction SilentlyContinue)) {
    $pythonCommand = 'python3'
}

$version = & $pythonCommand -c @"
import json
from pathlib import Path

manifest = Path(r'$manifestPath')
print(json.loads(manifest.read_text(encoding='utf-8'))['version'])
"@

$version = $version.Trim()
if (-not $version) {
    throw 'Could not read version from manifest.json'
}

$tag = "v$version"

if (git rev-parse -q --verify "refs/tags/$tag" 2>$null) {
    throw "Tag $tag already exists locally"
}

$remoteTag = git ls-remote --tags origin "refs/tags/$tag"
if ($remoteTag) {
    throw "Tag $tag already exists on origin"
}

$readmeContent = Get-Content -Raw -Path $readmePath
$sectionPattern = "(?ms)^###\s+$([regex]::Escape($tag))\r?\n(.*?)(?:\r?\n###\s+|\z)"
$match = [regex]::Match($readmeContent, $sectionPattern)
if (-not $match.Success) {
    throw "Could not find release notes for $tag in README.md"
}

$notes = $match.Groups[1].Value.Trim()
if (-not $notes) {
    throw "Release notes section for $tag is empty"
}

$notesFile = New-TemporaryFile
try {
    Set-Content -Path $notesFile -Value $notes -Encoding utf8

    git tag -a $tag -m "Release $tag"
    git push origin $tag
    & $ghCommand release create $tag --title $tag --notes-file $notesFile

    Write-Host "Created and pushed $tag and published GitHub release."
}
finally {
    Remove-Item -Path $notesFile -ErrorAction SilentlyContinue
}