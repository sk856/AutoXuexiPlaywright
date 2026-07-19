[CmdletBinding()]
param(
    [ValidatePattern('^v?\d+\.\d+\.\d+$')]
    [string]$Version = '4.0.2',
    [string]$Python = 'python',
    [string]$OutputRoot = (Join-Path $PSScriptRoot '..\..\dist-release')
)

$ErrorActionPreference = 'Stop'

$releaseRoot = $PSScriptRoot
$projectRoot = (Resolve-Path (Join-Path $releaseRoot '..\..')).Path
$normalizedVersion = $Version.TrimStart('v')
$packageName = "AutoXuexiPlaywright-v$normalizedVersion-windows-x64"
$outputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$workRoot = Join-Path $projectRoot '.release-build'
$distRoot = Join-Path $workRoot 'dist'
$buildRoot = Join-Path $workRoot 'build'
$spec = Join-Path $releaseRoot 'AutoXuexiPlaywright.spec'

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python executable was not found: $Python"
}

$browserRoot = if ($env:PLAYWRIGHT_BROWSERS_PATH) {
    $env:PLAYWRIGHT_BROWSERS_PATH
} else {
    Join-Path $env:LOCALAPPDATA 'ms-playwright'
}
if (-not (Get-ChildItem -LiteralPath $browserRoot -Directory -Filter 'firefox-*' -ErrorAction SilentlyContinue)) {
    throw "Playwright Firefox is missing under $browserRoot. Run: $Python -m playwright install firefox"
}

Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $outputRoot $packageName) -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $outputRoot "$packageName.zip") -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $workRoot, $outputRoot -Force | Out-Null

& $Python -m PyInstaller --noconfirm --clean `
    --workpath $buildRoot `
    --distpath $distRoot `
    $spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$builtApp = Join-Path $distRoot 'AutoXuexiPlaywright'
$packageRoot = Join-Path $outputRoot $packageName
Copy-Item -LiteralPath $builtApp -Destination $packageRoot -Recurse -Force

$forbiddenNames = @('config.json', 'cookies.json', 'AutoXuexiPlaywright.log', 'launcher-error.log')
$leakedFiles = Get-ChildItem -LiteralPath $packageRoot -Recurse -File | Where-Object { $_.Name -in $forbiddenNames }
if ($leakedFiles) {
    $leakedFiles | ForEach-Object FullName | Write-Error
    throw 'The release package contains a local configuration, cookie, or log file.'
}

$zipPath = Join-Path $outputRoot "$packageName.zip"
Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
$hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256

Write-Host "Package: $packageRoot"
Write-Host "Archive: $zipPath"
Write-Host "SHA256: $($hash.Hash)"
