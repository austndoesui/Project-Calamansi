# Clean obsolete iPhone 8 and iPhone X iOS 16.7.16 staging assets.
# Safe default: preview only. Use -Execute to actually delete.
# Deliberately keeps shim boot images, kernel patches, logs, Stage87's small
# diagnostic HFS, the ios-sweet reference clone, and all Git source trees.
[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$SkipWSL
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$expectedRoot = 'F:\ROM\patching\Project-Calamansi'
if (-not [string]::Equals($projectRoot.TrimEnd('\'), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Safety stop: script must run from $expectedRoot (found $projectRoot)"
}

# Exact file paths only. Do not add broad wildcard or directory deletion
# targets: some adjacent files are the only Stage91 working artifacts.
$windowsRelativeFiles = @(
    '_build\ios16-donor\ios16-20H392-os.dmg',
    '_build\ios16-donor\ios16-20H392-systemos.dmg',
    '_build\ios16-donor\ios16-20H392-appos.dmg',
    '_build\ios16-runtime\ios16-userdata.simg',
    '_build\ios16-runtime\ios16-userdata-tail.simg'
)

$totalBytes = [long]0
$foundWindows = @()
Write-Host "Project: $projectRoot"
Write-Host "Mode: $(if ($Execute) { 'DELETE' } else { 'PREVIEW (no files removed)' })"
Write-Host ''
foreach ($relative in $windowsRelativeFiles) {
    $path = Join-Path $projectRoot $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Write-Host "KEEP / ABSENT: $path"
        continue
    }
    $item = Get-Item -LiteralPath $path -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Safety stop: symbolic link / reparse point: $path"
    }
    $foundWindows += $path
    $totalBytes += [long]$item.Length
    Write-Host ("{0} {1,7:N2} GiB  {2}" -f $(if ($Execute) { 'DELETE' } else { 'PREVIEW' }), ($item.Length / 1GB), $path)
}
Write-Host ("Windows files identified: {0}; logical size: {1:N2} GiB" -f $foundWindows.Count, ($totalBytes / 1GB))

# WSL paths are all exact entries in /home/lapdq, and all are artifacts
# produced from the incomplete iPhone 8 extraction. Exclude the reusable
# tools and *all* XNU/shim workspaces. We use Python with fixed allowlists
# rather than passing paths to a shell's rm -rf.
$wslNames = @(
    'calamansi-ios16-root-diagnostic.hfs',
    'calamansi-ios16-sweet-prepared.hfs',
    'calamansi-ios16-sweet-v1.hfs',
    'calamansi-ios16-extracted',
    'calamansi-osroot-extracted',
    'calamansi-systemos-extracted',
    'calamansi-appos-extracted',
    'calamansi-dyld-verified',
    'calamansi-ipsw-temp',
    'calamansi-iphone-x-20H392/calamansi-iphone-x-root-INCOMPLETE.hfs',
    'calamansi-iphone-x-20H392/os.raw.img'
)

$wslOK = $false
if (-not $SkipWSL) {
    if (-not (Get-Command 'wsl.exe' -ErrorAction SilentlyContinue)) {
        Write-Warning "WSL not installed; skipping WSL cleanup."
    } else {
        # The program refuses to delete mounted files, external symlinks,
        # any path outside this exact allowlist, and files still in use by
        # an earlier guestmount. Each dry-run size uses allocated disk space.
        $wslHelper = '/mnt/f/ROM/patching/Project-Calamansi/tools/cleanup-iphone8-wsl.py'
        # Some iOS preferences have Apple uid 501 ownership and mode 0700.
        # Run only the fixed allowlisted helper as root in WSL to remove
        # those root-owned / foreign-uid entries without changing ownership
        # of unrelated directories or modifying the broader WSL system.
        $wslArgs = @('-d', 'Ubuntu', '-u', 'root', '--exec', '/usr/bin/python3', $wslHelper, $(if ($Execute) { 'execute' } else { 'preview' })) + $wslNames
        & wsl.exe @wslArgs
        if ($LASTEXITCODE -ne 0) {
            throw "WSL validation/cleanup failed with exit code $LASTEXITCODE; Windows files left untouched"
        }
        $wslOK = $true
    }
}

if ($Execute) {
    foreach ($path in $foundWindows) {
        # Revalidate every expected path immediately before deletion.
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Safety stop: changed to symlink: $path"
        }
        Remove-Item -LiteralPath $path -Force -ErrorAction Stop
        Write-Host "REMOVED: $path"
    }
    Write-Host 'Cleanup complete. IPSWs, iPhone X extracted services, final HFS, flashable sparse image, Stage91 boot images, patches and logs were preserved.'
    if ($wslOK) {
        Write-Host 'WSL filesystem space was freed; the Windows drive holding the WSL VHDX may need compaction separately.'
    }
} else {
    Write-Host ''
    Write-Host 'Preview finished. Run again with -Execute to delete exactly the items above.'
}
