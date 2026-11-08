#!/usr/bin/env bash
set -u

# Read-only Android evidence capture for OPPO CPH2179 memory reconciliation.
# Run from any directory on a host where adb can see the phone.

adb_bin=${ADB:-adb}
out=${1:-"cph2179-runtime-$(date +%Y%m%d-%H%M%S)"}
mkdir -p "$out" || exit 1

if ! "$adb_bin" get-state >/dev/null 2>&1; then
    echo "No ADB device is available. Connect the phone, enable USB debugging, and authorize this host." >&2
    exit 2
fi

has_remote_error() {
    rg -aq '^(cat: .*: (Permission denied|No such file or directory)|dmesg: .*Permission denied|.*su: .*not found)' "$1"
}

capture_file() {
    local remote=$1 dest=$2 tmp="$out/.$2.tmp"
    "$adb_bin" exec-out cat "$remote" >"$tmp" 2>"$out/$dest.stderr" || true
    if has_remote_error "$tmp" || [[ ! -s "$tmp" ]]; then
        echo "Retrying restricted read with su: $remote"
        "$adb_bin" exec-out su -c "cat '$remote'" >"$tmp" 2>"$out/$dest.stderr" || true
    fi
    if has_remote_error "$tmp" || [[ ! -s "$tmp" ]]; then
        mv "$tmp" "$out/$dest.stderr"
        echo "Could not read $remote; see $dest.stderr" >&2
    else
        mv "$tmp" "$out/$dest"
        if [[ ! -s "$out/$dest.stderr" ]]; then rm -f "$out/$dest.stderr"; fi
    fi
}

capture_file /proc/iomem proc-iomem.txt
capture_file /proc/meminfo proc-meminfo.txt
capture_file /sys/firmware/fdt live-fdt.dtb
capture_file /sys/fs/pstore/pmsg-ramoops-0 pmsg-ramoops-0.txt
capture_file /proc/memblock_reserved proc-memblock-reserved.txt

pstore_tmp="$out/.pstore-files.tmp"
"$adb_bin" exec-out ls -1 /sys/fs/pstore >"$pstore_tmp" 2>"$out/pstore-files.stderr" || true
if has_remote_error "$pstore_tmp" || [[ ! -s "$pstore_tmp" ]]; then
    "$adb_bin" exec-out su -c 'ls -1 /sys/fs/pstore' >"$pstore_tmp" 2>"$out/pstore-files.stderr" || true
fi
if ! has_remote_error "$pstore_tmp" && [[ -s "$pstore_tmp" ]]; then
    mv "$pstore_tmp" "$out/pstore-files.txt"
    while IFS= read -r entry; do
        [[ "$entry" =~ ^[A-Za-z0-9._-]+$ ]] || continue
        [[ "$entry" == pmsg-ramoops-0 ]] && continue
        capture_file "/sys/fs/pstore/$entry" "pstore-$entry"
    done <"$out/pstore-files.txt"
else
    mv "$pstore_tmp" "$out/pstore-files.stderr"
fi

tmp="$out/.dmesg.tmp"
"$adb_bin" exec-out dmesg >"$tmp" 2>"$out/dmesg.stderr" || true
if has_remote_error "$tmp" || [[ ! -s "$tmp" ]]; then
    echo "Retrying dmesg read with su."
    "$adb_bin" exec-out su -c dmesg >"$tmp" 2>"$out/dmesg.stderr" || true
fi
if has_remote_error "$tmp" || [[ ! -s "$tmp" ]]; then
    mv "$tmp" "$out/dmesg.stderr"
    echo "Could not read dmesg; see dmesg.stderr" >&2
else
    mv "$tmp" "$out/dmesg.txt"
    if [[ ! -s "$out/dmesg.stderr" ]]; then rm -f "$out/dmesg.stderr"; fi
fi

{
    echo "Captured: $(date -Is)"
    echo "Device properties:"
    "$adb_bin" shell getprop ro.product.model
    "$adb_bin" shell getprop ro.product.device
    "$adb_bin" shell getprop ro.build.fingerprint
    echo "Boot id (if exposed):"
    "$adb_bin" shell cat /proc/sys/kernel/random/boot_id 2>/dev/null || true
} >"$out/capture-meta.txt"

echo "Evidence saved under: $out"
echo "Review before sharing: dmesg and metadata may contain device identifiers."
echo "Allocator log hits:"
rg -in 'zone.?movable|zmc|reserved_mem|consys|wifi-reserve|sspm|scp_share|mblock|CMA:' "$out/dmesg.txt" 2>/dev/null | head -n 80 || true
