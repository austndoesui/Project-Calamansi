<h1 align="center">Project Calamansi</h1>

<p align="center">
  <strong>Bringing Apple's open-source XNU kernel to MediaTek MT6761 / MT6765 devices.</strong><br>
  An experimental, multi-device kernel and boot-chain port.
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-MT6761%20%2F%20MT6765-343434?style=flat-square">
  <img alt="Kernel" src="https://img.shields.io/badge/kernel-XNU-343434?style=flat-square">
  <img alt="Status" src="https://img.shields.io/badge/cactus-native%20XNU%20%2B%20PID1%20syscall%20verified-168c43?style=flat-square">
  <img alt="Devices" src="https://img.shields.io/badge/devices-cactus%20%7C%20CPH2179-497b70?style=flat-square">
</p>

---

**Project Calamansi** is an experimental effort to boot and adapt Apple's open-source **XNU** kernel on devices built around MediaTek's MT6761 / MT6765 family. It aims to share the kernel, boot-shim tooling, device-tree infrastructure and reproducible tests across supported boards while keeping hardware-specific configuration separate.

The first bring-up target is the **Xiaomi Redmi 6A (`cactus`)**. **`CPH2179`** is another target under development; its hardware and boot milestones must be verified independently. Calamansi is a kernel porting project, **not a working iOS port or a daily-use operating system**.

> [!WARNING]
> Experimental boot images can hang, reset or leave a device unable to boot normally until a known-good image is restored. Work only with an unlocked device and an established recovery route. Current development does not provide a usable iOS userland.

## What makes it work

| Component | Role | State |
| --- | --- | --- |
| **Boot shim** | Starts from the device's Android boot chain, prepares memory and hands control to XNU. | Hardware-proven on `cactus`; device-generalization planned. |
| **XNU kernel** | Apple's open-source kernel with MediaTek and board adaptation patches. | Native execution, BSD initialization and a minimal PID 1 userspace syscall hardware-verified on `cactus`; full iOS userspace remains unproven. |
| **Hardware description** | Apple Device Tree, memory and interrupt mappings, framebuffer and per-board parameters. | Existing cactus work; per-device profiles planned. |
| **Diagnostics** | Native framebuffer output, USB serial trace capture, and host-side validators. | Used in cactus bring-up; device-specific transport support varies. |

## Boot chain

```text
Stock bootloader / LK
  └─ Android boot image
      └─ Calamansi boot shim
          ├─ Board configuration + memory map + device tree
          ├─ USB / framebuffer diagnostics (where implemented)
          └─ Native XNU kernel
              └─ BSD, root filesystem and executable loading
                  └─ Minimal PID 1 (EL0 / getpid syscall verified on cactus)
```

This flow through the first PID 1 syscall is hardware-verified on `cactus` using a minimal custom ARM64 executable. The exact boot path and working peripherals differ by device.

## Current status

| Area | Redmi 6A (`cactus`) | `CPH2179` |
| --- | --- | --- |
| Bootloader → shim | **Verified** | Not yet documented here |
| Native XNU entry | **Verified** | Not yet documented here |
| On-device framebuffer console | **Verified** | Not yet documented here |
| USB debug capture | **Verified before XNU handoff** | Not yet documented here |
| BSD / root filesystem bring-up | **Verified through PID 1 executable loading and `execve` completion** | Not yet documented here |
| PID 1 userspace execution | **Verified: EL0 SVC64 + `getpid()`; green PID1 bar** | Not yet documented here |
| dyld / launchd / iOS userspace | **Not verified** | Not yet documented here |
| Functional iOS / SpringBoard | **Not available** | **Not available** |

**Latest verified cactus checkpoint (8 November 2026, Stage 85):** the kernel and getpid-first minimal ARM64 init were built, verified and flashed to a Redmi 6A. Native framebuffer evidence confirms executable page-in, Mach-O activation (`err=0`), task switch, signature processing, `execve` success and return, then **a real EL0 SVC64 exception**: `ST85 EL0 ec=15 esr=56000080 far=0 pc=100000414`. The device owner observed the **green `PID1 RUNNING` indicator**, which the kernel sets only when process 1 executes its `getpid()` syscall. This establishes the first confirmed native PID 1 userspace execution on `cactus`.

The Stage 85 COM25 prehandoff capture independently confirmed the expected kernel identity and XNU native entry; USB logging stops at handoff, so the **on-device framebuffer** is the evidence for userspace execution. This milestone demonstrates a minimal, static, custom PID 1 program; continued userspace services, dyld, launchd, SpringBoard and a functional iOS environment are **not yet verified**. Preserve Stage 85 as the known-good baseline. See [Stage 85 device evidence](docs/devices/cactus/STAGE85-PID1-STACK-EXEC-FAULT.md).

Device results should be recorded separately; success on one MT6765-family board does not imply that another board will boot.

## Getting started

The latest Cactus shim, tools and XNU patches are imported from [Cactarwin](https://github.com/austndoesui/Cactarwin/tree/stage61-cactus-gicr-id-guard). The [ordered manifest](xnu/patches/manifest.json) retains the original upstream names and SHA256 for every patch. The workflow fetches Apple's XNU source during build; that source is not vendored here. Packaging a boot image requires external generated or board-specific assets, explained in [the Cactus device guide](devices/cactus/README.md).

The existing cactus workflow uses Windows, WSL Ubuntu, ARM64 build tools, Python, a macOS GitHub Actions job for XNU, and an unlocked target device for hardware tests. CPH2179 prerequisites must be documented from that device's own verified setup.

## Repository layout

```text
Project-Calamansi/
├─ README.md, AGENTS.md      Project and agent documentation
├─ .github/workflows/       macOS XNU builds
├─ docs/devices/cactus/     Historical hardware evidence
├─ devices/cactus/          Redmi 6A support
├─ devices/cph2179/         Independent target (unverified)
├─ platform/mt6765/         Shared platform boundary (planned)
├─ boot/                    Boot-chain design
├─ shim/                    Existing Cactus boot shim and test tools
├─ xnu/patches/
│  ├─ manifest.json         Ordered legacy filename/hash mapping
│  ├─ common/               Generic compiler compatibility patches
│  ├─ legacy/               Inherited patches pending audit
│  └─ devices/cactus/       Cactus-conditional port patches
└─ tools/                   ADT, kernel and manifest utilities
```

The legacy patches remain unreviewed for portability. The MT6765 shared layer and CPH2179 boot support are not implemented yet.

## Development approach

1. Preserve the [ordered patch manifest](xnu/patches/manifest.json). Verify with `python3 tools/stage-patches.py --verify-only`.
2. Move reusable MT6765 code into shared components; keep panel, GPIO, memory reservations and boot peculiarities in device profiles.
3. Verify each target independently: compilation, shim handoff, native XNU execution, framebuffer, BSD and PID 1 are separate milestones.
4. Keep stage-by-stage experiments and capture logs in device-specific development records rather than the front page.

## Credits and origins

This project builds on Apple's open-source **XNU**, historical **Cactarwin** research and inherited open-source patching work. Special thanks and credit to [**dipa-studio/ios-sweet**](https://github.com/dipa-studio/ios-sweet) for earlier XNU porting and build work that informed the inherited patch stack, and [**ry-diffusion/Bergamota**](https://github.com/ry-diffusion/Bergamota) for its independently developed XNU project and this README's organization. The projects' devices, boot chains and operating-system milestones are separate. Retain applicable upstream attribution when importing code.

## License

See [LICENSE](LICENSE) for the license distributed with this repository. Imported XNU source and third-party components retain their own applicable license notices; the repository license alone does not replace those notices.
