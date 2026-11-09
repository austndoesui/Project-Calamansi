# Stage 85 — PID1 stack preflight and first exception evidence

Stage84 physically reached `ST84 PID1 apple strings done`, after
`load_machfile`, zone checks, task VM-map swap, and thread setup.
The next kernel operation switches the current thread's user address
map with `vm_map_switch`, then copies argv, environment and Apple
strings to the newly created PID1 stack. These writes require valid
mapped stack pages and the ARM64 copyout fault path.

The Stage85 XNU patch `0120-cactus-pid1-stack-fault-handoff-stage85.patch`
pre-faults the actual PID1 argument stack pages in the target 4-KiB VM
map using the normal `vm_fault` API. It then retains XNU's standard
`vm_map_switch` and `copyout` operations and their error handling,
and records their results separately. An ARM64 exception hook records
the first PID1 SVC64, user instruction/data abort, and kernel data
abort with ESR/FAR/PC; the original trap handlers still run. These
observations are complementary to the existing `getpid()` hook that
turns the framebuffer's PID1 bar green on an actual syscall.

The stack pre-fault operation addresses a plausible memory initialization
blocker. The Stage 84 checkpoint alone could not establish whether the
failing operation was map switching or copyout; the Stage 85 hardware
result below now confirms successful continuation through `execve` and
the first PID1 syscall, without isolating a single earlier root cause.

## Verified offline, November 8, 2026

- Source commit `26e472d`, GitHub Actions macOS build `42403342234`:
  **SUCCESS**, 4m54s.
- Compiled XNU kernel: 17,139,088 bytes, SHA256
  `dd39a64cd43de54dd79a2eaabb23b3e689a242179baccdf6399c93aad1da13fc`.
- Relocated native payload SHA256
  `3e7d17ebde20829bba1d272a5538c30f89c7eb1c2956884f7a91e156ca591a47`.
  **41 strict layout/instruction checks passed**, including the existing
  getpid-first minimal init, native entry PA `0x8142c488`, C entry PA
  `0x81abfdfc`, and boot args PA `0x824c4000`.
- Android boot-v2 image:
  `shim/out/cactus/cactus-trace-stage-85-boot.img`, 45,522,944 bytes,
  SHA256 `5d43ed73c067ada0dbff5ec98776ddf8b7c99435386a8fddbe93552ad8efe53c`.
  Image checksum and header validation passed.

## Hardware-verified result — November 8, 2026

Fastboot saw serial `3184a8a17d2b` and identified `product: cactus`.
The guarded Stage85 flash-and-capture script subsequently completed:
fastboot reported **OKAY** sending the image, writing `boot`, and
rebooting. COM25 capture
`usb-captures/stage-cactus-20261108-004637-350/session-001-004648-009.bin`
recorded **74 valid frames**, zero corrupted frames and 16 missing
sequence numbers. The expected kernel SHA256 prefix
`0xdd39a64cd43de54d` appeared in identity event `0x2800`, followed by
native XNU handoff `0x3500` to `0x8142c488` with boot args
`0x824c4000`. Capture sequence gaps make the USB record incomplete;
this prehandoff channel does not report native PID1 progress.

**On-device native framebuffer, reported by the device owner:**

```text
ST83 PID1 executable pagein enter
ST83 PID1 executable pagein finished
ST84 PID1 prefault done
ST82 PID1 activator #0 err=0
ST75 PID1 image activated
ST84 PID1 task switch enter
ST84 PID1 task switch done
ST84 PID1 signature done
ST71 PID1 execve ok
ST71 PID1 exec accepted
ST68 PID1 exec returned
ST85 EL0 ec=15 esr=56000080 far=0 pc=100000414
ERROR none
```

The device owner also confirmed that the previously amber
**`PID1 RUNNING` indicator turned green**. ARM64 exception class `0x15`
identifies a 64-bit supervisor call from EL0; the green indicator is
raised by XNU's process-1 `getpid()` implementation. Together these
confirm successful kernel-to-userspace transition and PID1's first
native syscall. This is a **minimal static ARM64 init**, not proof of
dyld, launchd, SpringBoard or a functional iOS operating system.

**Known-good baseline:** Stage85 boot image SHA256 above; preserve it for
future userspace experiments. Next tasks include verifying sustained PID1
execution and console/syscall behavior, then progressively enabling the
runtime, filesystem and IPC requirements for dyld and launchd.
