from pathlib import Path
import hashlib
import stage27_pack_kernel as pack
root=Path(__file__).resolve().parents[1]
kernel=root.parent/'stage78-kernel-run42278107872/kernel.development.cactus'
expected='1779340d044523ad05d8b2006710d13ca93d6f979d5815b6d5307c0b6dca8bcf'
data=kernel.read_bytes()
assert hashlib.sha256(data).hexdigest()==expected, 'Stage78 Actions kernel hash changed'
for marker in (b'ST78 hdr err=',b'ST78 mockfs cluster enter',b'ST78 MachO activator enter'):
    assert data.count(marker)==1, f'Stage78 trace provenance missing: {marker!r}'
pack.STAGE77_VERIFIED_KERNEL_SHA256=expected
pack.prepare(kernel,root/'shim/out/cactus/payload.bin',root/'shim/out/cactus/payload-stage78.bin',stage61_live_fb=True,stage64_cactus_gic=True,stage65_cactus_pid1=True,stage66_topbar=True,stage67_vfs_probe=True,stage68_root_pid1=True,stage69_root_pid1=True,stage70_minimal_pid1=True,stage71_direct_pid1=True,stage72_mockfs_pid1=True,stage73_pid1_vm=True,stage74_physmap_pid1=True,stage75_exec_read=True,stage76_pid1_shadow=True,stage77_pid1_wired=True,ramdisk=root/'shim/out/cactus/stage65-init/cactus-init.macho')
print('STAGE78 PACK PASS')
