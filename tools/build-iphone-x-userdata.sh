#!/usr/bin/env bash
# Rebuild a cactus userdata filesystem from an iPhone X iOS 16.7.16 IPSW.
# Run inside WSL Ubuntu. No flashing, no source deletions, no overwrites.
# Usage: build-iphone-x-userdata.sh prepare|pack|all IPSW WORKDIR
#   prepare: validate IPSW, extract DMGs, decode/mount and copy APFS roots
#   pack:    use the already-extracted *-copy trees to create HFS + sparse + repair
#   all:     prepare then pack
set -euo pipefail

if [[ $# != 3 || ! "$1" =~ ^(prepare|pack|all)$ ]]; then
    echo "usage: $0 prepare|pack|all IPHONE_X_20H392.ipsw WORKDIR" >&2
    exit 2
fi
mode=$1
ipsw=$(realpath "$2")
mkdir -p -- "$3"
work=$(realpath "$3")
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -f "$ipsw" && -d "$work" && "$work" != / && "$work" != /home ]] || {
    echo "invalid IPSW or work directory" >&2; exit 2;
}
for tool in python3 rsync sha256sum guestfish img2simg; do
    command -v "$tool" >/dev/null || { echo "missing $tool" >&2; exit 2; }
done

root="$work/os-root-copy"
sysroot="$work/systemos-copy"
approot="$work/appos-copy"
image="$work/calamansi-iphone-x-root-20H392.hfs"
sparse="$work/ios16-iphone-x-20H392-userdata.simg"
tail="$work/ios16-iphone-x-20H392-userdata-tail.simg"

verify_dmg() {
    local name=$1 expected=$2 actual
    [[ -f "$work/$name" && ! -L "$work/$name" ]] || {
        echo "missing $work/$name" >&2; exit 2;
    }
    actual=$(sha256sum "$work/$name")
    [[ "${actual%% *}" == "$expected" ]] || {
        echo "IPSW component SHA256 mismatch: $name" >&2; exit 2;
    }
}

mounts=()
cleanup_mounts() {
    local m
    for ((m=${#mounts[@]}-1; m>=0; m--)); do
        fusermount3 -u "${mounts[m]}" || echo "WARN: still mounted ${mounts[m]}" >&2
    done
}
trap cleanup_mounts EXIT

mount_apfs() {
    local src=$1 dst=$2 offset=${3:-}
    mkdir -p "$dst"
    if mountpoint -q "$dst"; then
        echo "refusing existing mount $dst" >&2; exit 2
    fi
    if [[ -n "$offset" ]]; then
        "$apfs" -s "$offset" "$src" "$dst"
    else
        "$apfs" "$src" "$dst"
    fi
    mountpoint -q "$dst" || { echo "APFS mount failed: $src" >&2; exit 1; }
    mounts+=("$dst")
    [[ -d "$dst/root" ]] || { echo "missing APFS root: $src" >&2; exit 1; }
}

if [[ "$mode" == prepare || "$mode" == all ]]; then
    apfs=${CALAMANSI_APFS_FUSE:-/home/lapdq/apfs-fuse-calamansi/build/apfs-fuse}
    converter=${CALAMANSI_DMG2IMG:-/home/lapdq/calamansi-iphone-x-20H392/dmg2img-lzfse/dmg2img}
    [[ -x "$apfs" && -x "$converter" ]] || {
        echo "missing APFS-FUSE or LZFSE-enabled dmg2img (configure CALAMANSI_APFS_FUSE/CALAMANSI_DMG2IMG)" >&2
        exit 2
    }
    command -v fusermount3 >/dev/null || { echo 'missing fusermount3' >&2; exit 2; }
    # Verify donor identity before reusing any extracted files.
    python3 "$script_dir/stage92_iphone_x_assets.py" "$ipsw" >/dev/null
    missing=()
    for name in os systemos appos kernelcache; do
        case "$name" in kernelcache) suffix=iphone10b ;; *) suffix=dmg ;; esac
        [[ -e "$work/$name.$suffix" ]] || missing+=("$name")
    done
    if (( ${#missing[@]} )); then
        python3 "$script_dir/stage92_iphone_x_assets.py" "$ipsw" --output "$work" --extract "${missing[@]}"
    fi
    verify_dmg os.dmg 80f426d5b8fca8552f95be427434f1911dbb4c2c6d28aad94f2426ddd0c92483
    verify_dmg systemos.dmg 9cd738f3b0169055549df84ad6d8d13e50a2da39af618ce0522ca4e06df86849
    verify_dmg appos.dmg 391f2df322c3172b021b2874f6da5c3e78b70b3df8f502e1a4af2b1d715c4608
    verify_dmg kernelcache.iphone10b 2d6a13d040aaf87cec09bb6906d43e9bd8cea951e43d1aa1cd62707dfdc5aaec

    if [[ ! -e "$work/os.raw.img" ]]; then
        "$converter" -s -i "$work/os.dmg" -o "$work/os.raw.img"
    fi
    # Verified 20H392 OS UDIF converts to GPT raw APFS; partition #1 begins at LBA 34.
    [[ $(stat -c %s "$work/os.raw.img") == 5635081728 ]] || {
        echo 'unexpected converted OS disk size' >&2; exit 2;
    }
    mount_apfs "$work/os.raw.img" "$work/os-mounted" 17408
    mount_apfs "$work/systemos.dmg" "$work/systemos-mounted"
    mount_apfs "$work/appos.dmg" "$work/appos-mounted"
    mkdir -p "$root" "$sysroot" "$approot"
    rsync -a --numeric-ids "$work/os-mounted/root/" "$root/"
    rsync -a --numeric-ids "$work/systemos-mounted/root/" "$sysroot/"
    rsync -a --numeric-ids "$work/appos-mounted/root/" "$approot/"
    cleanup_mounts
    mounts=()
fi

if [[ "$mode" == pack || "$mode" == all ]]; then
    dyld="$sysroot/System/Library/Caches/com.apple.dyld"
    for path in "$root/sbin/launchd" "$root/usr/libexec/backboardd" \
        "$root/System/Library/CoreServices/SpringBoard.app/SpringBoard" \
        "$dyld/dyld_shared_cache_arm64"; do
        [[ -s "$path" ]] || { echo "missing required iOS file: $path" >&2; exit 2; }
    done
    for artifact in "$image" "$sparse" "$tail"; do
        [[ ! -e "$artifact" && ! -L "$artifact" ]] || {
            echo "refusing to overwrite existing artifact: $artifact" >&2; exit 2;
        }
    done
    bash "$script_dir/mkiosroot_extracted.sh" "$root" "$dyld" "$image" 16G
    bash "$script_dir/finalize_iosroot_cryptex.sh" "$image" "$sysroot" "$approot" "$root"
    img2simg "$image" "$sparse"
    python3 "$script_dir/verify_ios_userdata_sparse.py" "$image" "$sparse" --partition-bytes 0x438ffbe00
    python3 "$script_dir/repair_ios_userdata_sparse_tail.py" "$sparse" "$tail"
    echo "CALAMANSI_IPHONE_X_USERDATA_READY=$sparse"
    echo "CALAMANSI_IPHONE_X_TAIL_REPAIR=$tail"
fi
