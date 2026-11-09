# Project Calamansi — iOS 16 runtime HFS staging (November 8, 2026)

## Provenance and host artifacts

The owner-supplied iPhone 8 restore image is
`iPhone_4.7_P3_16.7.16_20H392_Restore.ipsw` (build 20H392).
`blacktop/ipsw` v3.1.743 extracted **44** actual arm64 shared-cache files
totalling **3,329,294,336 bytes** into
`/home/lapdq/calamansi-dyld-verified/20H392__iPhone10,1_4`.
The extracted main cache was independently identified in the host output
and packaged along with its subcaches, dylddata, linkedit, and symbols.

The full OS extraction encountered a Go `cannot allocate memory` failure.
A separate mounted APFS-FUSE -> ext4 `rsync` copied roughly **3.0 GB** of
OS content before APFS-FUSE failed on some `LinguisticData` and
`LocationBundles` resources with I/O errors and disconnected. That source
tree is **incomplete**; do not claim this is a restored full iOS installation.
It contains the actual
`System/Library/CoreServices/SpringBoard.app/SpringBoard` executable,
SHA256 `ea835980610a95591fb349bca077840fab7bdd663efaa11ef054d91bc2125475`.
The original Stage87 HFS root supplied known Apple launch components:

- `/sbin/launchd`: SHA256
  `12370e5ee35bf28ae479b6c4b4455f4f4693ab803e37c5eb3032537c18cac61c`.
- `/usr/lib/dyld`: SHA256
  `5806834564fe6462ae981d0915d612b1eb2f6f168822b5d278bee56254933757`.
- `/System/Library/xpc/launchd.plist`: SHA256
  `c30e4aa2fd90d81ddef173cbd357fe614411c390d62f13b8b28e061af42d104a`.

The SystemOS cryptex was copied separately with dyld-cache files excluded:
**29,674,837 bytes**, with no rsync errors. The AppOS cryptex copied
**7,936,372 bytes**, also with no rsync errors. They are available at
`/home/lapdq/calamansi-systemos-extracted` and
`/home/lapdq/calamansi-appos-extracted`.

## Validated HFSX diagnostic image

Two host-only scripts built the disk image:
`tools/mkiosroot_extracted.sh` and
`tools/finalize_iosroot_cryptex.sh`. The first uses a 16 GiB
case-sensitive HFSX journaled container and libguestfs `tar-in` to avoid
the unsupported WSL HFS kernel mount. It populates the OS root and 44
dyld-cache files. The second supplies `/private/preboot/Cryptexes/OS`,
`/private/preboot/Cryptexes/App`, points the cryptex cache directory at
the same files as the main shared-cache location, restores missing
trampoline-library paths, adds the early service keybag, and prepares logd
directory owners/markers.

The final image is
`/home/lapdq/calamansi-ios16-root-diagnostic.hfs`, **16 GiB logical**,
about **6.2 GiB allocated** on ext4. The checksum after cryptex finalization
is **SHA256**
`9f7072235cac38738b941418133218143d743934b5b4946d956d2f91d5cc84b8`.

Guestfish reopened the HFSX image in read-only mode and verified SHA256
for actual on-image `launchd`, `dyld`, `SpringBoard`, and
`launchd.plist`, matching the values above. It also verified
`/System/Cryptexes/OS -> ../../private/preboot/Cryptexes/OS`,
cryptex dyld cache path -> `/System/Library/Caches/com.apple.dyld`,
the keybag file (root-owned), and the real main shared-cache file.
These are **host filesystem checks**, not a boot result.

The Linux `fsck.hfsplus -f -y` filesystem check reported that the volume
appears OK. Its `-f -n` read-only mode continues to flag a minor primary
volume-header repair. A newly formatted, empty `mkfs.hfsplus -s -J`
case-sensitive journaled HFSX control image produced the **same** warning.
This appears to be a tool/format compatibility issue; it is not a native
XNU mount validation, so keep the warning visible when evaluating the image.

## Device integration boundary

The already flashed Stage88 boot image verified CMD13, CMD17,
CRC-checked GPT header, controller restore and native XNU handoff on cactus.
Native XNU read-only eMMC code is prepared in
`xnu/patches/devices/cactus/0121-cactus-msdc-readonly-root.patch`,
with ordered SHA-pinned manifest. It is not compiled into an XNU kernel
image yet, because the required Xcode/macOS builder is available only via
the configured GitHub Actions workflow. Per `AGENTS.md`, do not commit/push
this change without authorization for the specific branch/change set.

The native root driver currently discovers a CRC-checked GPT partition
**named `iosroot`**. No such partition has been provisioned, and the
existing Android `system` and `userdata` have not been overwritten.
A 16 GiB HFS image cannot be placed into the 64 MiB boot partition.
For a device boot test, both a compiled native XNU kernel and a reviewed
storage-staging method are still required. Reusing the Android userdata
partition directly would erase its filesystem and needs specific owner
approval. A non-destructive file/extent-backed eMMC root would require
additional kernel mapping support and enough real free space on userdata.

Finally, these assets do not prove Apple's launchd service graph,
code-signing compatibility, IOKit dependencies, or SpringBoard rendering.
The original APFS copy is incomplete. No new Stage89/kernel image was flashed
as part of this host staging record.
