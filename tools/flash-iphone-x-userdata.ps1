# Flash a verified 20H392 Android sparse iOS userdata image on cactus.
# Preview by default. -Execute performs a destructive userdata flash.
# MTK fastboot rejects the last huge sparse chunk: accept that *specific*
# failure only when all earlier chunks succeeded, then apply our verified
# DONT_CARE-preserving tail repair. Does not flash boot or reboot.
[CmdletBinding()]
param(
    [string]$WorkDir = '\\wsl.localhost\Ubuntu\home\lapdq\calamansi-iphone-x-20H392',
    [string]$Serial = '3184a8a17d2b',
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$sparse = Join-Path $WorkDir 'ios16-iphone-x-20H392-userdata.simg'
$tail = Join-Path $WorkDir 'ios16-iphone-x-20H392-userdata-tail.simg'
foreach ($path in @($sparse, $tail)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing file: $path" }
}
$fastboot = (Get-Command fastboot.exe -ErrorAction Stop).Source
Write-Host "Sparse image: $sparse"
Write-Host "Tail repair: $tail"
if (-not $Execute) {
    Write-Host 'PREVIEW ONLY. Add -Execute to check cactus and flash userdata (erases existing userdata).'
    exit 0
}
$devices = @(& $fastboot devices)
if (@($devices | Where-Object { $_ -match "^$([regex]::Escape($Serial))\s+fastboot\s*$" }).Count -ne 1) {
    throw "Expected fastboot device $Serial not connected"
}
$product = (& $fastboot -s $Serial getvar product 2>&1 | Out-String)
if ($product -notmatch 'product:\s*cactus') { throw "Unexpected device: $product" }
$size = (& $fastboot -s $Serial getvar 'partition-size:userdata' 2>&1 | Out-String)
if ($size -notmatch 'partition-size:userdata:\s*438ffbe00') {
    throw "Unexpected userdata partition size: $size"
}
Write-Host "Device $Serial verified: cactus; userdata 0x438ffbe00"

$outdir = Join-Path (Join-Path $PSScriptRoot '..\_build') 'iphone-x-flash-logs'
[void][System.IO.Directory]::CreateDirectory($outdir)
$stamp = (Get-Date).ToString('yyyyMMdd-HHmmss-fff')
function Invoke-Flash([string]$Image, [string]$Label) {
    $stdout = Join-Path $outdir "$stamp-$Label-stdout.txt"
    $stderr = Join-Path $outdir "$stamp-$Label-stderr.txt"
    # Start-Process preserves exit code and avoids PowerShell 5.1 treating
    # fastboot's normal stderr progress as terminating errors.
    $args = @('-s', $Serial, '-S', '64M', 'flash', 'userdata', ('"' + $Image + '"'))
    $process = Start-Process -FilePath $fastboot -ArgumentList $args -PassThru -Wait `
        -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $log = (Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue) + "`n" +
           (Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue)
    Write-Host "$Label exit=$($process.ExitCode) log=$stderr"
    return @{ ExitCode = $process.ExitCode; Log = $log }
}

$first = Invoke-Flash $sparse 'full'
if ($first.ExitCode -eq 0) {
    Write-Host 'Full sparse flash completed successfully; tail repair not needed.'
    exit 0
}

# Never disguise an early failure as a successful userdata flash.
$seen = [regex]::Matches($first.Log, "Sending sparse 'userdata'\s+(\d+)/(\d+)")
if ($seen.Count -eq 0) { throw 'Full flash failed before numbered chunks; refusing repair' }
$last = $seen[$seen.Count - 1]
$chunk = [int]$last.Groups[1].Value
$count = [int]$last.Groups[2].Value
$failures = [regex]::Matches($first.Log, 'FAILED\s*\(')
if ($count -le 1 -or $chunk -ne $count -or $failures.Count -ne 1 -or
    $first.Log -notmatch "FAILED\s*\(remote:\s*'sparse image write failure'\)") {
    throw "Unexpected flash failure at chunk $chunk/$count; refusing repair; inspect logs"
}
Write-Host "Known MediaTek final-chunk failure at $chunk/$count. Applying tail repair."
$repair = Invoke-Flash $tail 'tail'
if ($repair.ExitCode -ne 0) { throw 'Tail repair failed; userdata is incomplete' }
Write-Host 'Tail repair completed. Sparse segments were acknowledged by fastboot; no eMMC readback performed.'
