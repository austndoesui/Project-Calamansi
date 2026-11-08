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
in that run. XNU still never reached kernel source compilation. The workflow
had staged both Cactus and OPPO device patches into one XNU patch directory. It
now stages by selected machine config: OPPO gets common/legacy patches, its
own patch, and Cactus patch 0082 as the machine-config foundation expected by
0115; later Cactus bring-up patches are excluded. This fixes the cross-device
staging defect, though only another Actions run can confirm whether it was the
reason 0115 was skipped and verify it applies to the fetched XNU source. The
log confirms the Cortex-A53 flags were used for
`libfirehose_kernel`; that host tool build is not the failing part.

### Next action

On the next Actions run, confirm the staged patch list includes
`0082-cactus-machine-config.patch` and `0115-oppo6765-machine-config.patch`,
excludes Cactus patches 0084–0114, and reports 0115 as applied. Then confirm
the post-patch `makedefs/MakeInc.def` ARM64 supported-config list contains
`OPPO6765`. If 0115 is still skipped, capture the full patch warning, including
`git apply --check`'s reason, before changing the patch contents.

Do not treat this run as an XNU kernel build: it stopped before compiling the
kernel, and it produced no OPPO XNU payload or flashable image. Keep the raw
runner log outside Git; it contains long host paths and build-environment
details that do not need to be duplicated here.
