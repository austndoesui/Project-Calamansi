# Run only after entering fastboot, preserving COM25 before reboot.
param(
    [int]$CaptureSeconds = 60,
    [Parameter(Mandatory=$true)][string]$Serial,
    [ValidateSet(49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84)][int]$Stage = 49
)
$ErrorActionPreference = 'Stop'
if ($CaptureSeconds -lt 30) { throw 'CaptureSeconds must be at least 30' }
$shimDir = $PSScriptRoot
$root = Split-Path $shimDir -Parent
$bootImage = Join-Path $shimDir "out\cactus\cactus-trace-stage-$Stage-boot.img"
$hash = if ($Stage -eq 49) {
    '49EA5B6C975603B9B0891180F587B53819CA7AF3C1AC6C6DEBD3DA1640D7405C'
} elseif ($Stage -eq 50) {
    '3DB03ADD61280050E03D83C9C84C1803799E06DB8428915DFDA25798C04F43B0'
} else {
    $hashFile = "$bootImage.sha256"
    if (-not (Test-Path -LiteralPath $hashFile)) {
        throw "Stage$Stage built-image checksum missing: $hashFile"
    }
    ((Get-Content -LiteralPath $hashFile -TotalCount 1) -split '\s+')[0].ToUpperInvariant()
}
if (-not (Test-Path -LiteralPath $bootImage)) { throw "Stage$Stage image missing: $bootImage" }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $bootImage).Hash -ne $hash) {
    throw "Stage$Stage image hash mismatch; refusing flash"
}
$devices = @(& fastboot devices -l)
if ($LASTEXITCODE -ne 0 -or -not ($devices -match "^$([regex]::Escape($Serial))\s+fastboot")) {
    throw "Device $Serial is not in fastboot"
}
$previousPreference = $ErrorActionPreference
try {
    # Fastboot prints getvar output on stderr, even when successful.
    $ErrorActionPreference = 'Continue'
    $product = (& fastboot -s $Serial getvar product 2>&1 | Out-String)
    $productExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($productExit -ne 0 -or $product -notmatch '(?m)product:\s*cactus') {
    throw "Unverified fastboot product: $product"
}
$startTime = Get-Date
$tag = $startTime.ToString('yyyyMMdd-HHmmss-fff')
$stdout = Join-Path $root "stage$Stage-watch-$tag-out.txt"
$stderr = Join-Path $root "stage$Stage-watch-$tag-err.txt"
$watcher = Join-Path $shimDir 'watch-cactus-usb.ps1'
$watchArgs = @('-NoProfile','-ExecutionPolicy','Bypass','-File', ('"' + $watcher + '"'), '-Seconds', $CaptureSeconds)
$watchProcess = Start-Process -FilePath powershell.exe -WorkingDirectory $shimDir -ArgumentList $watchArgs -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
Start-Sleep -Seconds 2
if ($watchProcess.HasExited) { throw "COM25 watcher exited: $(Get-Content $stderr -Raw)" }
& fastboot -s $Serial flash boot $bootImage
if ($LASTEXITCODE -ne 0) { throw 'Boot flash failed' }
& fastboot -s $Serial reboot
if ($LASTEXITCODE -ne 0) { throw 'Fastboot reboot failed' }
Write-Host "Stage$Stage booted; COM25 watcher PID $($watchProcess.Id)"
try {
    # Works even when the watcher exits between flash/reboot and the wait.
    $watchProcess.Refresh()
    # COM25's final decoder can take longer than the capture window itself,
    # especially when Windows reschedules the USB PnP watcher after close.
    if (-not $watchProcess.WaitForExit(($CaptureSeconds + 90) * 1000)) {
        Write-Warning 'Watcher exceeded wait duration; checking saved capture files directly'
    }
} catch {
    # The watcher can finish writing its CLOSED log and capture before
    # Start-Process reports an exited handle. Decode the saved bytes and
    # let missing or corrupt files, rather than a wait timeout, fail.
    Write-Warning "Watcher wait error: $($_.Exception.Message). Checking $stdout"
}
$capturesRoot = Join-Path $root 'usb-captures'
$watcherLog = Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue
$watcherPathMatch = [regex]::Match(($watcherLog -join "`n"), '(?m)^\S+ START path=(.+?) seconds=')
if ($watcherPathMatch.Success) {
    $capturePath = $watcherPathMatch.Groups[1].Value.Trim()
    $runs = @(Get-Item -LiteralPath $capturePath -ErrorAction SilentlyContinue)
} else {
    $runs = @(Get-ChildItem -LiteralPath $capturesRoot -Directory -Filter 'stage-cactus-*' |
        Where-Object { $_.CreationTime -ge $startTime.AddMinutes(-2) } |
        Sort-Object CreationTime -Descending)
}
if (-not $runs.Count) { throw "No capture directory; see $stdout" }
$sessionFiles = @(Get-ChildItem -LiteralPath $runs[0].FullName -Filter '*.bin' -File |
    Where-Object { $_.Length -gt 0 })
if (-not $sessionFiles.Count) {
    # The watcher may still be flushing a session or the START path may
    # resolve before session files have been published. Search only captures
    # created during this run; don't report 'no frames' prematurely.
    Start-Sleep -Seconds 2
    $sessionFiles = @(Get-ChildItem -LiteralPath $runs[0].FullName -Filter '*.bin' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 0 })
}
if (-not $sessionFiles.Count) {
    $recent = @(Get-ChildItem -LiteralPath $capturesRoot -Directory -Filter 'stage-cactus-*' |
        Where-Object { $_.CreationTime -ge $startTime.AddMinutes(-2) } |
        Sort-Object CreationTime -Descending)
    foreach ($candidate in $recent) {
        $found = @(Get-ChildItem -LiteralPath $candidate.FullName -Filter '*.bin' -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Length -gt 0 })
        if ($found.Count) { $runs = @($candidate); $sessionFiles = $found; break }
    }
}
if (-not $sessionFiles.Count) { throw "No completed COM25 session file found; see $stdout" }
foreach ($raw in $sessionFiles) {
    Write-Host "Checking $($raw.FullName)"
    & python (Join-Path $shimDir 'decode-cactus-usb.py') $raw.FullName "--require-stage$Stage" --show 100
    if ($LASTEXITCODE -ne 0) { Write-Warning "Stage$Stage capture incomplete; review the decoded records" }
}
Write-Host "Trace directory: $($runs[0].FullName)"
