# CPH2179 bring-up issues

## XNU build rejects `OPPO6765`

**Status:** Open  
**Evidence:** GitHub Actions run [42507346534](https://github.com/austndoesui/Project-Calamansi/actions/runs/42507346534), saved locally as `/run/media/shark/1234-ABCD/cph2179ios/error_log.txt`.

The run selected `DEVELOPMENT_ARM64_OPPO6765`. The host-side `libfirehose_kernel`
build reached Xcode with the Cortex-A53 flags, but XNU stopped during `build_setup`
before kernel source compilation:

```text
makedefs/MakeInc.kernel:22: *** Unsupported CURRENT_MACHINE_CONFIG OPPO6765.  Stop.
```

This is a machine-config registration failure, not an XNU C compiler error.
At validation time, `OPPO6765` was missing from the effective
`SUPPORTED_ARM64_MACHINE_CONFIGS` list. The new machine-config patch either was
not applied to `makedefs/MakeInc.def`, or its supported-config hunk did not take
effect. The available excerpt does not distinguish those cases.

### Next action

Inspect the XNU build log before the `Build` step and verify that
`0115-oppo6765-machine-config.patch` is reported as applied. Then inspect the
post-patch `makedefs/MakeInc.def` from the `xnu-buildtree` artifact and confirm
that its ARM64 supported-config list includes `OPPO6765`. Correct the patch or
staging path based on that evidence, rerun the manifest verifier, and rebuild.

Do not treat this run as an XNU kernel build: it stopped before compiling the
kernel, and it produced no OPPO XNU payload or flashable image. Keep the raw
runner log outside Git; it contains long host paths and build-environment
details that do not need to be duplicated here.
