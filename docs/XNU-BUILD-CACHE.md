# XNU build cache: investigation and fixes (7 November 2026)

The Calamansi macOS runner starts from a clean machine for each GitHub Actions
run. Its `build.sh` fetches the upstream XNU source, applies the ordered
patches, installs build tools and headers, and compiles XNU. `ccache` is
working: its printed counters are cumulative and get restored with the cache.

For the Stage80 and Stage81 builds, the cumulative counters changed from
2,140 cacheable calls (1,068 hits, 1,072 misses) to 3,210 calls (2,136 hits,
1,074 misses). The **Stage81 delta** was therefore **1,070 calls, 1,068 hits
and only 2 misses**. The 66.54% figure for the Stage81 run describes the
accumulated cache history, not that build's hit rate.

The Stage81 `Build` step still took 10m49s. Its timed log showed roughly
2m55s for initial setup/source fetching/patching; bootstrap_cmds (MIG)
started at 15:23:42 UTC; XNU header installation began at 15:24:28;
libsyscall headers began at 15:27:06; kernel building began at 15:27:26
and finished at 15:31:36. The workflow's existing `prebuild` cache had
been restored, but omitted `fakeroot/Applications`, where MIG was installed,
and its header-installation sentinel was never cached.

The workflow now saves that Xcode-toolchain path in its versioned prebuilt
cache. It separately saves installed XNU headers and the completion sentinel,
using `tools/xnu_header_cache_key.py` to invalidate the header cache when
any imported patch can change installed headers. A patch touching only
ordinary C or assembly implementation files leaves the header key unchanged;
shell scripts, configuration, header files and unrecognized patch formats
always invalidate it. A cache miss runs the normal builder, with the same
patch manifest and compiler.

The first CI run after this change must populate the two new caches. Compare
subsequent runs' `Restore prebuilt tools` and `Restore installed XNU
headers` steps, and check for the absence of `Building bootstrap_cmds`
and `Installing xnu headers` in the Build log. Faster builds are expected,
but a 4–7 minute target is not guaranteed; source fetching, patch application,
linking and a fresh macOS runner remain.

## Measured validation

Commit `8e82ad7` passed [cache-population run 42388776600](https://github.com/austndoesui/Project-Calamansi/actions/runs/42388776600).
Both the versioned prebuilt-tool cache and the header cache were saved.
The subsequent unchanged
[warm-cache run 42389657141](https://github.com/austndoesui/Project-Calamansi/actions/runs/42389657141)
also passed. Both caches produced **exact cache hits**. There was no
`Building bootstrap_cmds` or `Installing xnu headers` step in its build log.

| Run | XNU Build step | Total job |
| --- | --- | --- |
| Stage81 baseline 42385859444 | 10m49s | 12m12s |
| Warm cache 42389657141 | **5m27s** | **6m30s** |

The second run's cumulative ccache statistics rose from 3,210 to 4,280
cacheable calls: **1,070 additional hits, zero additional misses**.
This confirms that repeated compilation was already largely cached; the
workflow speedup comes from caching previously repeated *tool and header
installation*. A new patch that affects generated headers correctly
invalidates the header cache and will take longer.
