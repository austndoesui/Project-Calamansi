# Project Calamansi migration plan (draft)

## Goal

Organize the existing cactus bring-up into a maintainable multi-device MT6761/MT6765 project without losing working Stage 79 build provenance or changing behavior through cosmetic patch renames.

## Recommended sequence

1. **Agree on public identity and project scope.** Replace the placeholder `README.md` with the reviewed `README.draft.md`; add a shared `AGENTS.md` based on `AGENTS.draft.md`. Keep verified cactus evidence distinct from untested `cph2179` status.
2. **Create shared and device layers.** Put MT6765 platform helpers and reusable tooling on `main`, with explicit board profiles for `cactus` and `cph2179`. Prefer a single shared integration branch; use short-lived board feature branches instead of divergent long-lived copies of the entire source.
3. **Inventory the Cactarwin patch chain.** Build an ordered manifest from the existing XNU workflow and audit each historical patch for platform-specific addresses, `CACTUS` macros, old `sweet` assumptions and upstream dependencies. Preserve exact file hashes and old names in a mapping table.
4. **Classify, then rename.** Categories: `common`, `mt6765`, `devices/cactus`, `devices/cph2179`. For example, a genuinely generic patch may become `0114-common-mockfs-bounded-read.patch`, but the current Stage79 patch has cactus-conditioned virtual RAMDisk behavior and should remain device-scoped until refactored. Change manifest references and required-patch checks atomically, retaining old ID aliases in historical docs.
5. **Port the build/flash scripts.** Add per-device configuration (board ID, image header, DTB, ADT, memory regions, watchdog, USB, framebuffer), separate build outputs, strict device-identity preflight and board-specific test guards. Preserve the known-good Stage78/79 cactus outputs as local rollback artifacts.
6. **Verify reproducibility.** On a clean checkout, apply the manifest in order, compile the same cactus kernel, validate relocated payload and boot image, and compare provenance. Only then enable the `cph2179` profile and record its own first hardware results.
7. **Publish migration with a reviewable diff.** Keep old Cactarwin repository as a historical reference/archive. Retire obsolete README claims there via a short pointer to Calamansi **after** Calamansi's main README and build workflow are verified, rather than deleting provenance or staging broken links.

## Implementation status

The README, agent guide, patch sources, manifest and Cactus shim have been migrated. Continue auditing inherited patches, verify the new CI build and separately bring up CPH2179. Preserve Cactarwin as the historical baseline.
