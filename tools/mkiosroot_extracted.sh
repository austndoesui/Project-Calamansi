#!/usr/bin/env bash
# Assemble an iOS 16 HFS+ root offline from files extracted by ipsw.
# Uses libguestfs, so WSL does not need a writable HFS+ kernel module.
# Input: an extracted OS root directory, matching SystemOS arm64 caches,
#        and an output path. Does not touch the phone or source files.
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
    echo "usage: $0 EXTRACTED_ROOT DYLD_CACHE_DIR OUT.hfs [16G]" >&2
    exit 2
fi
root=$(realpath "$1")
dsc=$(realpath "$2")
output=$3
size=${4:-16G}
[[ -d "$root" && -d "$dsc" ]] || { echo "missing source tree" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "refusing to overwrite $output" >&2; exit 2; }
for file in sbin/launchd usr/lib/dyld usr/libexec/backboardd usr/libexec/mobileactivationd System/Library/CoreServices/SpringBoard.app/SpringBoard System/Library/xpc/launchd.plist; do
    [[ -s "$root/$file" ]] || { echo "missing iOS executable: $file" >&2; exit 2; }
done
[[ -s "$dsc/dyld_shared_cache_arm64" ]] || { echo "missing dyld main cache" >&2; exit 2; }
[[ $(find "$dsc" -maxdepth 1 -type f -name 'dyld_shared_cache_arm64*' | wc -l) -eq 44 ]] || {
    echo "incomplete dyld arm64 subcache set" >&2
    exit 2
}
dyld_bytes=$(find "$dsc" -maxdepth 1 -type f -name 'dyld_shared_cache_arm64*' -printf '%s\n' |
    awk '{total += $1} END {printf "%.0f", total}')
[[ "$dyld_bytes" == 3330359296 ]] || {
    echo "iPhone X 20H392 arm64 dyld cache total byte count mismatch: $dyld_bytes" >&2
    exit 2
}
for cmd in guestfish mkfs.hfsplus truncate tar; do
    command -v "$cmd" >/dev/null || { echo "missing $cmd" >&2; exit 2; }
done

mkdir -p "$(dirname "$output")"
trap '[[ -f "$output" ]] && rm -f -- "$output"' ERR
truncate -s "$size" "$output"
mkfs.hfsplus -s -J -v iOSRoot "$output"

# Force the root disk's ownership to root; the ipsw extractor runs as the
# extracting user and loses original APFS owner metadata. Specific iOS
# service directories are prepared below with their required owners.
tar --numeric-owner --owner=0 --group=0 \
    --exclude='./System/Library/Caches/com.apple.dyld' \
    --exclude='./.file' \
    -C "$root" -cf - . | \
    guestfish --rw -a "$output" run : mount-options force /dev/sda / : \
    tar-in /dev/stdin /

guestfish --rw -a "$output" run : mount-options force /dev/sda / : \
    mkdir-p /System/Library/Caches/com.apple.dyld : \
    mkdir-p /private/var/db : mkdir-p /private/var/tmp : \
    mkdir-p /private/etc : mkdir-p /dev

# The extractor's ordinary files are assigned root (APFS ownership was lost
# during extraction), but mobile's private preferences must retain uid 501.
# The upstream ios-sweet root tweaks set 0600 on these; iOS would otherwise
# deny SpringBoard and Setup access after packaging.
if [[ -d "$root/private/var/mobile/Library/Preferences" ]]; then
    guestfish --rw -a "$output" run : mount-options force /dev/sda / : \
        chown 501 501 /private/var/mobile : \
        chown 501 501 /private/var/mobile/Library : \
        chown 501 501 /private/var/mobile/Library/Preferences
    for source_plist in "$root"/private/var/mobile/Library/Preferences/*.plist; do
        [[ -f "$source_plist" ]] || continue
        plist_name=${source_plist##*/}
        guestfish --rw -a "$output" run : mount-options force /dev/sda / : \
            chown 501 501 "/private/var/mobile/Library/Preferences/$plist_name"
    done
fi
if [[ -d "$root/private/var/containers/Bundle" ]]; then
    guestfish --rw -a "$output" run : mount-options force /dev/sda / : \
        chown 33 33 /private/var/containers/Bundle
fi

tar --numeric-owner --owner=0 --group=0 -C "$dsc" -cf - . | \
    guestfish --rw -a "$output" run : mount-options force /dev/sda / : \
    tar-in /dev/stdin /System/Library/Caches/com.apple.dyld

guestfish --ro -a "$output" run : mount /dev/sda / : \
    ll /sbin : ll /usr/lib : \
    ll /System/Library/Caches/com.apple.dyld

sha256sum "$output"
echo "OFFLINE_HFS_ROOT_READY=$output"
