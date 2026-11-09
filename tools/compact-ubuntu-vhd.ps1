# Compacts the existing Ubuntu WSL2 ext4.vhdx without deleting Linux files.
# Run: powershell -NoProfile -ExecutionPolicy Bypass -File "F:\ROM\patching\Project-Calamansi\tools\compact-ubuntu-vhd.ps1"
[CmdletBinding()]
param([switch]$Elevated)

$ErrorActionPreference = 'Stop'
trap {
    Write-Host ("Compaction stopped: " + $_.Exception.Message) -ForegroundColor Red
    if ($Elevated) { [void](Read-Host 'Press Enter to close this window') }
    break
}

$vhd = 'C:\Users\lapdq\AppData\Local\wsl\{16e0ee70-da34-4bcc-a42e-b64d530a7bf2}\ext4.vhdx'
$expected = 'C:\Users\lapdq\AppData\Local\wsl\{16e0ee70-da34-4bcc-a42e-b64d530a7bf2}'
if (-not [string]::Equals((Split-Path -Parent $vhd), $expected, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Safety stop: unexpected Ubuntu VHD location'
}
if (-not (Test-Path -LiteralPath $vhd -PathType Leaf)) {
    throw "Ubuntu virtual disk not found: $vhd"
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$admin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    if ($Elevated) { throw 'Administrator access was not granted.' }
    Write-Host 'Requesting Administrator permission to compact the Ubuntu VHDX...'
    $thisScript = $MyInvocation.MyCommand.Path
    if (-not $thisScript) { throw 'Script path could not be resolved' }
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $thisScript + '" -Elevated'
    Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -Wait
    exit
}

$beforeBytes = (Get-Item -LiteralPath $vhd).Length
$cBefore = (Get-PSDrive -Name C).Free
Write-Host ('Ubuntu VHD before: {0:N2} GiB' -f ($beforeBytes / 1GB))
Write-Host 'Shutting down Ubuntu and other WSL distributions...'
& wsl.exe --shutdown
if ($LASTEXITCODE -ne 0) {
    throw "wsl --shutdown failed (exit code $LASTEXITCODE)"
}

# Hyper-V's Optimize-VHD is available on this Windows installation.
# The script intentionally stops if Windows denies VHD permission.
if (-not (Get-Command Optimize-VHD -ErrorAction SilentlyContinue)) {
    Import-Module Hyper-V -ErrorAction Stop
}
if (-not (Get-Command Optimize-VHD -ErrorAction SilentlyContinue)) {
    throw 'Optimize-VHD is unavailable. Enable Hyper-V PowerShell management tools.'
}

Write-Host 'Compacting Ubuntu virtual disk...'
Optimize-VHD -Path $vhd -Mode Full -ErrorAction Stop

$afterBytes = (Get-Item -LiteralPath $vhd).Length
$cAfter = (Get-PSDrive -Name C).Free
Write-Host ('Ubuntu VHD after:  {0:N2} GiB' -f ($afterBytes / 1GB))
Write-Host ('Disk file reduction: {0:N2} GiB' -f (($beforeBytes - $afterBytes) / 1GB))
Write-Host ('Free space on C:   {0:N2} GiB (was {1:N2} GiB)' -f ($cAfter / 1GB), ($cBefore / 1GB))
Write-Host 'Complete. Ubuntu data and the XNU workspace were preserved.'
if ($Elevated) { [void](Read-Host 'Press Enter to close this window') }
