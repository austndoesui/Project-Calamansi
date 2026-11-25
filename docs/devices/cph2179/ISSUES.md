# CPH2179 bring-up issues

## XNU compile reaches ARM64 cache geometry error for `OPPO6765`

**Status:** Open  
**Evidence:** GitHub Actions runs [42507346534](https://github.com/austndoesui/Project-Calamansi/actions/runs/42507346534) and [42509587086, job 128819527920](https://github.com/austndoesui/Project-Calamansi/actions/runs/42509587086/job/128819527920). Logs are saved locally as `/run/media/shark/1234-ABCD/cph2179ios/error_log.txt` and `/run/media/shark/1234-ABCD/cph2179ios/error_log2.txt`.

The run selected `DEVELOPMENT_ARM64_OPPO6765`. The host-side `libfirehose_kernel`
build reached Xcode with the Cortex-A53 flags, but XNU stopped during `build_setup`
before kernel source compilation:

```text
makedefs/MakeInc.kernel:22: *** Unsupported CURRENT_MACHINE_CONFIG OPPO6765.  Stop.
```

This is a machine-config registration failure, not an XNU C compiler error.
The earlier runs failed before compilation because `OPPO6765` was missing from
the effective `SUPPORTED_ARM64_MACHINE_CONFIGS` list. That registration is now
working: the latest log reports `REQUIRED OPPO PATCH APPLIED` and compilation
starts. The first compiler errors are now:

```text
osfmk/arm64/proc_reg.h:233:2: error: processor not supported
```

So the immediate failure is that the OPPO machine-config patch was not applied
in `0_build (2).txt`. XNU's ARM64 cache-line selection has a Cactus/SWEET and
Apple/BCM case, but no OPPO6765 case, so it reaches the `#error`. The Oppo
compile profile uses Cortex-A53, whose instruction and data cache lines are
64 bytes; patch 0115 now adds that compile-time case using
`ARM64_BOARD_CONFIG_OPPO6765`.

### Next action

After committing the cache-line change and manifest hash, check the next
workflow's first compiler error. The current run used `MAKEFLAGS=-k`, so it
continued after the same header error was reported by many translation units.
The 48 MB `0_build (2).txt` is the complete verbose Actions log; the build tree
is separately uploaded as `xnu-buildtree.zip` (about 22 MB) so individual
compile commands can be reproduced. Neither artifact is a kernel image.

This run reached XNU source compilation but did not produce an OPPO kernel
payload or flashable image. Keep the raw runner log outside Git; it contains
long host paths and build-environment details.
