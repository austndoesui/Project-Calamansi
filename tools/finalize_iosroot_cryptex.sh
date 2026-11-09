#!/usr/bin/env bash
# Populate a host-only HFS+ iOS root with SystemOS/AppOS cryptexes and the
# launch-time directories required by Apple's early userspace services.
# The matching arm64 dyld subcaches must already be in /System/Library/Caches.
set -euo pipefail

if [[ $# != 4 ]]; then
    echo "usage: $0 ROOT.hfs SYSTEMOS_ROOT APPOS_ROOT EXTRACTED_OS_ROOT" >&2
    exit 2
fi
image=$(realpath "$1")
systemos=$(realpath "$2")
appos=$(realpath "$3")
osroot=$(realpath "$4")
[[ -f "$image" && -d "$systemos/usr/lib" && -d "$appos/System" && -d "$osroot/usr/lib" ]] || {
    echo "missing verified root/cryptex sources" >&2
    exit 2
}
magic=$(dd if="$image" bs=1 skip=1024 count=2 status=none)
[[ "$magic" == 'H+' || "$magic" == 'HX' ]] || {
    echo "input is neither HFS+ nor HFSX" >&2
    exit 2
}

gfish() {
    guestfish --rw -a "$image" run : mount-options force /dev/sda / : "$@"
}
gfish mkdir-p /private/preboot/Cryptexes/OS : \
    mkdir-p /private/preboot/Cryptexes/App : \
    mkdir-p /private/var/keybags : \
    mkdir-p /private/var/db/diagnostics/timesync : \
    mkdir-p /private/var/db/uuidtext

# The same 3.3GiB dyld cache has already been installed at the root cache
# path. Exclude it from SystemOS and add a single symlink below.
tar -C "$systemos" --numeric-owner --owner=0 --group=0 \
    --exclude='./System/Library/Caches/com.apple.dyld' -cf - . | \
    guestfish --rw -a "$image" run : mount-options force /dev/sda / : \
    tar-in /dev/stdin /private/preboot/Cryptexes/OS
tar -C "$appos" --numeric-owner --owner=0 --group=0 -cf - . | \
    guestfish --rw -a "$image" run : mount-options force /dev/sda / : \
    tar-in /dev/stdin /private/preboot/Cryptexes/App

# Store the 3.1GiB dyld cache only once. Apple's SystemOS cryptex path points
# to the same files as /System/Library/Caches/com.apple.dyld.
gfish mkdir-p /private/preboot/Cryptexes/OS/System/Library/Caches : \
    ln-s /System/Library/Caches/com.apple.dyld \
    /private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld

# At early ignition levels dyld may resolve these cryptex binaries at their
# non-cryptex paths. Link them through the already-existing /System/Cryptexes
# symlink rather than storing duplicate files.
for file in libffi-trampolines.dylib libobjc-trampolines.dylib libstdc++.6.0.9.dylib; do
    if [[ ! -e "$osroot/usr/lib/$file" && ! -L "$osroot/usr/lib/$file" ]]; then
        gfish ln-s "/System/Cryptexes/OS/usr/lib/$file" "/usr/lib/$file"
    fi
done

keybag=$(mktemp)
trap 'rm -f "$keybag"' EXIT
cat > "$keybag" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>KeyBagKeys</key><data>U1dFRVQ=</data></dict></plist>
EOF

gfish upload "$keybag" /private/var/keybags/systembag.kb : \
    chmod 0600 /private/var/keybags/systembag.kb : \
    chown 0 0 /private/var/keybags/systembag.kb : \
    chown 272 272 /private/var/db/diagnostics : \
    chown 272 272 /private/var/db/diagnostics/timesync : \
    chown 272 272 /private/var/db/uuidtext : \
    touch /private/var/db/diagnostics/.migrated : \
    touch /private/var/db/diagnostics/timesync/.migrated : \
    touch /private/var/db/uuidtext/.migrated : \
    chown 272 272 /private/var/db/diagnostics/.migrated : \
    chown 272 272 /private/var/db/diagnostics/timesync/.migrated : \
    chown 272 272 /private/var/db/uuidtext/.migrated

guestfish --ro -a "$image" run : mount /dev/sda / : \
    ll /private/preboot/Cryptexes/OS/usr/lib : \
    ll /private/var/keybags : \
    ll /System/Library/CoreServices/SpringBoard.app
sha256sum "$image"
echo "HOST_IOS_CRYPTEX_READY=$image"
