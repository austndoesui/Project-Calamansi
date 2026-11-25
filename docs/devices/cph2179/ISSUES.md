# CPH2179 bring-up issues

## XNU build rejects `OPPO6765`

**Status:** Open  
**Evidence:** GitHub Actions runs [42507346534](https://github.com/austndoesui/Project-Calamansi/actions/runs/42507346534) and [42509587086, job 128819527920](https://github.com/austndoesui/Project-Calamansi/actions/runs/42509587086/job/128819527920). Logs are saved locally as `/run/media/shark/1234-ABCD/cph2179ios/error_log.txt` and `/run/media/shark/1234-ABCD/cph2179ios/error_log2.txt`.

The run selected `DEVELOPMENT_ARM64_OPPO6765`. The host-side `libfirehose_kernel`
build reached Xcode with the Cortex-A53 flags, but XNU stopped during `build_setup`
before kernel source compilation:

```text
makedefs/MakeInc.kernel:22: *** Unsupported CURRENT_MACHINE_CONFIG OPPO6765.  Stop.
```

This is a machine-config registration failure, not an XNU C compiler error.
At validation time, `OPPO6765` was missing from the effective
`SUPPORTED_ARM64_MACHINE_CONFIGS` list. The second run's patch guard reported:

```text
0115-oppo6765-machine-config.patch: SKIPPED
```

So the immediate failure is that the OPPO machine-config patch was not applied
in that run. XNU still never reached kernel source compilation. The newer workflow stages OPPO patch 0115 and excludes Cactus-only patches. The
newest log, `7_Build (4).txt`, still skips 0115 at
`makedefs/MakeInc.def:61`; the subsequent unsupported-machine error is a result
of that skipped patch. The failing hunk tried to add the Oppo compiler flags
separately at a stale line location. The fix moves that definition into the
same supported-machine hunk, whose surrounding context is already matched by
the patch. This still needs an Actions run to confirm application against the
fetched XNU tree.

### Next action

After committing the updated 0115 patch and manifest hash, confirm the Actions
log says `REQUIRED OPPO PATCH APPLIED` and that `build_setup` passes the machine
configuration check. That only confirms machine-config registration; it does
not show that XNU source compilation succeeds or that the device can boot.

Do not treat this run as an XNU kernel build: it stopped before compiling the
kernel, and it produced no OPPO XNU payload or flashable image. Keep the raw
runner log outside Git; it contains long host paths and build-environment
details that do not need to be duplicated here.
