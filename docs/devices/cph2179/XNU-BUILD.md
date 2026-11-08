# CPH2179 XNU compile target

The repository now has an isolated `OPPO6765` ARM64 XNU machine configuration
for an initial **compile-only** build. It targets the Cortex-A53 instruction
baseline and does not set CPH2179 memory ranges, kernel virtual addresses,
framebuffer, GIC, timer, or peripheral values. Those need separate hardware
validation before an image can be considered bootable.

The new profile reuses the existing XNU feature list and patch series so the
first build can expose compiler and linker issues. Several inherited patches
remain Sweet/Cactus-specific; inclusion in a successful compile does not mean
their runtime behavior is suitable for OPPO. The build must not be packaged
for flashing or treated as an OPPO boot image.

After these changes are committed and pushed to the `cph2179` branch, dispatch
the `xnu` workflow with:

```sh
gh workflow run xnu.yml --ref cph2179 \
  -f macos_version=13.5 \
  -f machine_config=OPPO6765 \
  -f kernel_config=DEVELOPMENT \
  -f keep_going=true
```

The workflow uploads `xnu-kernel` and `xnu-buildtree` artifacts. First inspect
the Actions log for the final kernel output and compile failures. Keep the
kernel artifact and its SHA256 as build evidence; it is not yet a SWEETXNU
payload and is not ready to pass to the OPPO shim.

Before creating a flashable payload, implement and verify the CPH2179 XNU
handoff profile, memory map/ADT, required virtual-memory and interrupt setup,
and the kernel entry ABI. In particular, do not borrow the Cactus kernel's
link address, framebuffer, GIC, or RAM window.
