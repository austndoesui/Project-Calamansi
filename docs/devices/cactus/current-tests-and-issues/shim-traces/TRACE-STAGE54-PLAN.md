# Stage54: finish native IOKit lockdown and reach BSD initialization

## Current verified boundary

Stage53's physically visible, owner-transcribed 81-line framebuffer
dump (`../../xnufboutput.txt`) shows real XNU Darwin 22.6.0 startup,
VM/pmap, scheduler, Mach IPC and IOKit initialization. Its persistent
header ends at approximate `PE_lockdown_iokit` (transcribed as
`PE_lockdown_lockit`). The implementation at this boundary is:

```
osfmk/kern/startup.c:
    kernel_bootstrap_log("PE_lockdown_iokit");
    PE_lockdown_iokit();
    vm_set_restrictions(machine_info.max_cpus);
    bsd_init();

pexpert/arm/pe_init.c:
    zalloc_iokit_lockdown();
    StartIOKitMatching();
```

The last printed status is the **before-call** marker. Stage53 does not
prove where execution stopped within that function, whether a fault
occurred, or whether framebuffer updates later became unavailable.

## Minimal Stage54 source work, compiled as one XNU build

1. Add CACTUS-only `fbcon_stage53_progress()`/`kprintf` progress
   before and after `zalloc_iokit_lockdown()` and
   `StartIOKitMatching()` in `pexpert/arm/pe_init.c`.
2. Add before and after markers around `PE_lockdown_iokit()` itself,
   `vm_set_restrictions(machine_info.max_cpus)`, and the entry to
   `bsd_init()` in `osfmk/kern/startup.c`. Retain the existing
   `bsd_init` source milestones from patch 0090.
3. If the last successful marker lands inside IOKit matching,
   instrument its *specific* callback path or panic handler in a
   follow-up patch, identifying the actual failing registration.
   Don't bypass IOKit matching or security lockdown.
4. Verify `SWEET CPU requested=1 selected=1 (limit=0)` against the
   compiled source and actual runtime data. If `machine_info.max_cpus`
   is zero, confirm why before attempting CPU/pmap changes.
5. Apply the new Stage54 patch **after** 0090 in an isolated worktree;
   build the CACTUS kernel using the existing pinned Actions workflow.
   Regenerate a stage-specific, hash-pinned payload/boot image, keep
   old Stage53 image working, and preserve live LK layer1 0x7f4db000,
   USB prehandoff and native framebuffer exceptions.

**Success gate:** Actual device framebuffer shows `PE_lockdown_iokit`
returned, `vm_set_restrictions` completed and `bsd_init` entered.
If a panic/stall occurs, the last before/after marker should name the
function; no false “full boot” PASS without hardware evidence.

## Parallel userspace preparation (before any IPSW is needed)

Audit `tools/mkpayload.py --ramdisk`, `tools/mkinit.py`, and
`tools/sweet-init.S` against Stage53's pinned Cactus payload layout.
Prepare a Cactus-specific, source-built diagnostic PID 1 and memory
root with explicit `rd=md0` boot argument, bounds, ADT RAMDisk reserve
and 16 KiB kernel VM page vs 4 KiB hardware granule checks. Use
Benesse's `a04br3-init.S`, `mkinit.py` and `mkhfsroot.py` as a reference
for user/kernel ABI and mount validation, not for physical addresses.

Only package/flash the userspace variant once Stage54 demonstrates
reliable BSD/root initialization. The later iPhone X iOS 16.7.16
(20H392) restore IPSW provides original Apple dyld and shared caches
for dynamic userland work. No IPSW is required for the kernel/diagnostic
init stages.
