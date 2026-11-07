#!/usr/bin/env bash
# Build an offline-only cactus stage probe that returns to TWRP with a
# live initramfs trace file. Do not flash during the diagnostic build.
set -euo pipefail
cd "$(dirname "$0")"

STAGE="${1:-3}"
case "$STAGE" in
    3|4|5|6|7|8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|32|33|34|35|36|37|38|39|40|41|42|43|44|45|46|47|48|49|50|51|52|53|54|55|56|57|58|59|60|61|62|63|64|65|66|67|68|69|70|71|72|73|74|75|76|77|78|79|80|81|82|83|84) ;;
    *) echo "usage: $0 [3..84]" >&2; exit 2 ;;
esac

OUT="out/cactus/linux-chainload"
STOCK="$OUT/recovery-ramdisk.gz"
DTB="$OUT/recovery-dtb"
DTBO="/home/lapdq/cactus-kernel/images/cactus_dtbo.img"
MKBOOT="/home/lapdq/cactus-kernel/pack/mkbootimg.py"
for f in "$STOCK" "$DTB" "$DTBO" "$MKBOOT" "$OUT/recovery-Image"; do
    test -f "$f" || { echo "missing: $f" >&2; exit 1; }
done

PAYLOAD_DEFINE=()
if [[ "$STAGE" -ge 18 ]]; then
    PAYLOAD_SOURCE=out/cactus/payload.bin
    PREPARED_PAYLOAD="$OUT/stage18-payload.bin"
    if [[ "$STAGE" == 32 || "$STAGE" == 33 ]]; then
        # Stage27 uses the real rebuilt XNU Mach-O. Its boot_args report
        # the original 1440 framebuffer rows, and no old source image is
        # overwritten during validation or packaging.
        PAYLOAD_SOURCE=out/cactus/payload-stage27.bin
        PREPARED_PAYLOAD="$OUT/stage27-relocated-payload.bin"
    elif [[ "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage84.bin
        PREPARED_PAYLOAD="$OUT/stage84-relocated-payload.bin"
    elif [[ "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage83.bin
        PREPARED_PAYLOAD="$OUT/stage83-relocated-payload.bin"
    elif [[ "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage82.bin
        PREPARED_PAYLOAD="$OUT/stage82-relocated-payload.bin"
    elif [[ "$STAGE" == 81 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage81.bin
        PREPARED_PAYLOAD="$OUT/stage81-relocated-payload.bin"
    elif [[ "$STAGE" == 80 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage80.bin
        PREPARED_PAYLOAD="$OUT/stage80-relocated-payload.bin"
    elif [[ "$STAGE" == 79 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage79.bin
        PREPARED_PAYLOAD="$OUT/stage79-relocated-payload.bin"
    elif [[ "$STAGE" == 78 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage78.bin
        PREPARED_PAYLOAD="$OUT/stage78-relocated-payload.bin"
    elif [[ "$STAGE" == 77 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage77.bin
        PREPARED_PAYLOAD="$OUT/stage77-relocated-payload.bin"
    elif [[ "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage76.bin
        PREPARED_PAYLOAD="$OUT/stage76-relocated-payload.bin"
    elif [[ "$STAGE" == 75 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage75.bin
        PREPARED_PAYLOAD="$OUT/stage75-relocated-payload.bin"
    elif [[ "$STAGE" == 74 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage74.bin
        PREPARED_PAYLOAD="$OUT/stage74-relocated-payload.bin"
    elif [[ "$STAGE" == 73 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage73.bin
        PREPARED_PAYLOAD="$OUT/stage73-relocated-payload.bin"
    elif [[ "$STAGE" == 72 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage72.bin
        PREPARED_PAYLOAD="$OUT/stage72-relocated-payload.bin"
    elif [[ "$STAGE" == 71 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage71.bin
        PREPARED_PAYLOAD="$OUT/stage71-relocated-payload.bin"
    elif [[ "$STAGE" == 70 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage70.bin
        PREPARED_PAYLOAD="$OUT/stage70-relocated-payload.bin"
    elif [[ "$STAGE" == 69 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage69.bin
        PREPARED_PAYLOAD="$OUT/stage69-relocated-payload.bin"
    elif [[ "$STAGE" == 68 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage68.bin
        PREPARED_PAYLOAD="$OUT/stage68-relocated-payload.bin"
    elif [[ "$STAGE" == 67 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage67.bin
        PREPARED_PAYLOAD="$OUT/stage67-relocated-payload.bin"
    elif [[ "$STAGE" == 66 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage66.bin
        PREPARED_PAYLOAD="$OUT/stage66-relocated-payload.bin"
    elif [[ "$STAGE" == 65 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage65.bin
        PREPARED_PAYLOAD="$OUT/stage65-relocated-payload.bin"
    elif [[ "$STAGE" == 64 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage64.bin
        PREPARED_PAYLOAD="$OUT/stage64-relocated-payload.bin"
    elif [[ "$STAGE" == 63 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage63.bin
        PREPARED_PAYLOAD="$OUT/stage63-relocated-payload.bin"
    elif [[ "$STAGE" == 62 ]]; then
        # Same strictly pinned XNU payload as Stage61; MMIO reads happen in shim.
        PAYLOAD_SOURCE=out/cactus/payload-stage61.bin
        PREPARED_PAYLOAD="$OUT/stage62-relocated-payload.bin"
    elif [[ "$STAGE" == 61 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage61.bin
        PREPARED_PAYLOAD="$OUT/stage61-relocated-payload.bin"
    elif [[ "$STAGE" == 60 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage60.bin
        PREPARED_PAYLOAD="$OUT/stage60-relocated-payload.bin"
    elif [[ "$STAGE" == 59 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage59.bin
        PREPARED_PAYLOAD="$OUT/stage59-relocated-payload.bin"
    elif [[ "$STAGE" == 58 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage58.bin
        PREPARED_PAYLOAD="$OUT/stage58-relocated-payload.bin"
    elif [[ "$STAGE" == 57 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage57.bin
        PREPARED_PAYLOAD="$OUT/stage57-relocated-payload.bin"
    elif [[ "$STAGE" == 56 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage56.bin
        PREPARED_PAYLOAD="$OUT/stage56-relocated-payload.bin"
    elif [[ "$STAGE" == 55 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage55.bin
        PREPARED_PAYLOAD="$OUT/stage55-relocated-payload.bin"
    elif [[ "$STAGE" == 54 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage54.bin
        PREPARED_PAYLOAD="$OUT/stage54-relocated-payload.bin"
    elif [[ "$STAGE" == 53 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage53.bin
        PREPARED_PAYLOAD="$OUT/stage53-relocated-payload.bin"
    elif [[ "$STAGE" == 52 ]]; then
        PAYLOAD_SOURCE=out/cactus/payload-stage52.bin
        PREPARED_PAYLOAD="$OUT/stage52-relocated-payload.bin"
    elif [[ "$STAGE" == 51 ]]; then
        # Hard requirement: use the XNU kernel rebuilt from patch 0088 and
        # repacked with Stage51's retargeted Apple device tree.
        PAYLOAD_SOURCE=out/cactus/payload-stage51.bin
        PREPARED_PAYLOAD="$OUT/stage51-relocated-payload.bin"
    elif [[ "$STAGE" == 34 || "$STAGE" == 35 || "$STAGE" == 36 || "$STAGE" == 37 || "$STAGE" == 38 || "$STAGE" == 39 || "$STAGE" == 40 || "$STAGE" == 41 || "$STAGE" == 42 || "$STAGE" == 43 || "$STAGE" == 44 || "$STAGE" == 45 || "$STAGE" == 46 || "$STAGE" == 47 || "$STAGE" == 48 || "$STAGE" == 49 || "$STAGE" == 50 ]]; then
        # Stage28 patched XNU (0086 + 0087) from Actions run 40003701253.
        PAYLOAD_SOURCE=out/cactus/payload-stage28.bin
        PREPARED_PAYLOAD="$OUT/stage28-relocated-payload.bin"
    fi
    test -f "$PAYLOAD_SOURCE" || { echo "missing: $PAYLOAD_SOURCE" >&2; exit 1; }
    python3 prepare_stage18_payload.py "$PAYLOAD_SOURCE" "$PREPARED_PAYLOAD"
    if [[ "$STAGE" == 21 ]]; then
        python3 check_stage20b_entry.py "$OUT/stage18-payload.bin"
    elif [[ "$STAGE" == 22 ]]; then
        python3 check_stage20c_entry.py "$OUT/stage18-payload.bin"
    elif [[ "$STAGE" == 23 ]]; then
        python3 check_stage20d_entry.py "$OUT/stage18-payload.bin"
    elif [[ "$STAGE" == 24 ]]; then
        python3 check_stage21c1_entry.py "$OUT/stage18-payload.bin"
    elif [[ "$STAGE" == 25 ]]; then
        python3 check_stage21c2_entry.py "$OUT/stage18-payload.bin"
    elif [[ "$STAGE" == 26 ]]; then
        python3 check_stage21d_entry.py "$OUT/stage18-payload.bin"
    elif [[ "$STAGE" == 27 ]]; then
        python3 check_stage22_entry.py "$OUT/stage18-payload.bin"
    elif [[ "$STAGE" == 28 || "$STAGE" == 29 || "$STAGE" == 30 || "$STAGE" == 31 ]]; then
        python3 check_stage22_entry.py "$OUT/stage18-payload.bin"
        if [[ "$STAGE" == 30 ]]; then
            python3 check_stage25_pmap.py "$OUT/stage18-payload.bin"
        fi
    elif [[ "$STAGE" == 32 ]]; then
        python3 check_stage27_entry.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 33 ]]; then
        python3 check_stage28_pmap.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 84 ]]; then
        python3 check_stage84_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage83_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage82_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 81 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage81_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 80 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage80_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 79 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage79_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 78 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage78_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 77 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage77_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage76_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 75 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage75_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 74 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage74_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 73 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage73_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 72 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage72_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 71 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage71_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 70 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage70_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 69 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage69_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 68 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage68_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 67 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage67_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 66 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage66_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 65 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage65_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 64 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage64_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 63 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
        python3 check_stage63_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 62 ]]; then
        python3 check_stage61_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 61 ]]; then
        python3 check_stage61_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 60 ]]; then
        python3 check_stage60_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 59 ]]; then
        python3 check_stage59_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 58 ]]; then
        python3 check_stage58_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 57 ]]; then
        python3 check_stage57_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 56 ]]; then
        python3 check_stage56_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 55 ]]; then
        python3 check_stage55_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 54 ]]; then
        python3 check_stage54_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 53 ]]; then
        python3 check_stage53_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 52 ]]; then
        python3 check_stage52_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 51 ]]; then
        # Fresh kernel from Actions run 40099595534: third framebuffer
        # descriptor shifts native MMU instructions 12 bytes and early C
        # 32 bytes. Preserve the Stage28 guards for all older builds.
        python3 check_stage51_xnu.py "$PREPARED_PAYLOAD"
    elif [[ "$STAGE" == 34 || "$STAGE" == 35 || "$STAGE" == 36 || "$STAGE" == 37 || "$STAGE" == 38 || "$STAGE" == 39 || "$STAGE" == 40 || "$STAGE" == 41 || "$STAGE" == 42 || "$STAGE" == 43 || "$STAGE" == 44 || "$STAGE" == 45 || "$STAGE" == 46 || "$STAGE" == 47 || "$STAGE" == 48 || "$STAGE" == 49 || "$STAGE" == 50 ]]; then
        python3 check_stage27_entry.py "$PREPARED_PAYLOAD"
        python3 check_stage28_pmap.py "$PREPARED_PAYLOAD"
        if [[ "$STAGE" -ge 40 ]]; then
            CHECKPOINT_STAGE="$STAGE"
            if [[ "$STAGE" == 45 ]]; then CHECKPOINT_STAGE=43; fi
            if [[ "$STAGE" == 46 ]]; then CHECKPOINT_STAGE=44; fi
            if [[ "$STAGE" == 47 ]]; then CHECKPOINT_STAGE=44; fi
            if [[ "$STAGE" == 48 ]]; then CHECKPOINT_STAGE=44; fi
            if [[ "$STAGE" == 49 ]]; then CHECKPOINT_STAGE=44; fi
            if [[ "$STAGE" == 50 ]]; then CHECKPOINT_STAGE=44; fi
            if [[ "$STAGE" == 51 ]]; then CHECKPOINT_STAGE=44; fi
            python3 check_stage40_late_c.py "$PREPARED_PAYLOAD" --stage "$CHECKPOINT_STAGE"
        fi
    fi
    python3 trace_initramfs.py prepare "$STOCK" "$OUT/trace-ramdisk.bin" \
        "$OUT/trace-address.txt" --payload "$PREPARED_PAYLOAD" \
        --payload-address-file "$OUT/stage18-address.txt"
    read -r PAYLOAD_ADDR PAYLOAD_BYTES < "$OUT/stage18-address.txt"
    PAYLOAD_DEFINE=(-DPAYLOAD_ADDR="$PAYLOAD_ADDR" -DPAYLOAD_LENGTH="$PAYLOAD_BYTES")
else
    python3 trace_initramfs.py prepare "$STOCK" "$OUT/trace-ramdisk.bin" "$OUT/trace-address.txt"
fi
TRACE_ADDR="$(cat "$OUT/trace-address.txt")"
PREFIX="$OUT/trace-stage-$STAGE"
CFLAGS=(-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only
        -mstrict-align -fno-stack-protector -DBOARD_CACTUS)

aarch64-linux-gnu-gcc "${CFLAGS[@]}" -x assembler-with-cpp -DSTAGE="$STAGE" \
    -DTRACE_ADDR="$TRACE_ADDR" -c linux_stage_probe.S -o "$PREFIX.o"
# Stages 19+ must call the USB/XNU diagnostic probe from the live entry
# wrapper. If the preprocessor omits that branch, the image silently boots
# TWRP with no COM25 frames and an untouched CTRC header.
if [[ "$STAGE" -ge 19 ]]; then
    if ! aarch64-linux-gnu-readelf -r "$PREFIX.o" |
         grep -Eq 'R_AARCH64_CALL26[[:space:]]+[^[:space:]]+[[:space:]]+stage19_probe'; then
        echo "stage $STAGE entry does not call stage19_probe" >&2
        exit 1
    fi
fi
OBJECTS=("$PREFIX.o")
if [[ "$STAGE" == 4 ]]; then
    aarch64-linux-gnu-gcc "${CFLAGS[@]}" -c debug.c -o "$PREFIX-debug.o"
    OBJECTS+=("$PREFIX-debug.o")
fi
if [[ "$STAGE" == 6 ]]; then
    aarch64-linux-gnu-gcc "${CFLAGS[@]}" -c pmsg_trace.c -o "$PREFIX-pmsg.o"
    OBJECTS+=("$PREFIX-pmsg.o")
fi
if [[ "$STAGE" -ge 8 ]]; then
  if [[ "$STAGE" -ge 14 ]]; then
    SOURCES=(cactus_usb cactus_trace)
    EXTRA_DEFINES=()
    if [[ "$STAGE" == 15 ]]; then
      SOURCES+=(stage15_early)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=15 -DSHIM_STAGE15_EARLY=1)
    elif [[ "$STAGE" == 16 ]]; then
      # Actual cactus shim FDT and reserved-RAM debug routines, but no
      # loader or XNU branch. Dead FDT framebuffer functions are GC'd.
      SOURCES+=(stage16_probe fdt fdt_ranges debug)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=16 -ffunction-sections -fdata-sections)
    elif [[ "$STAGE" == 17 ]]; then
      SOURCES+=(stage17_probe fdt fdt_ranges)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=17 -ffunction-sections -fdata-sections)
    elif [[ "$STAGE" == 18 ]]; then
      SOURCES+=(stage18_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=18 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 19 ]]; then
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=19 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 20 ]]; then
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=20 -DCACTUS_STAGE20=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 21 ]]; then
      # Stage20-B uses its own image so the Stage20-A hardware image survives.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=21 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 22 ]]; then
      # Stage20-C runs the known early framebuffer code until XNU's VBAR write.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=22 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 23 ]]; then
      # Stage20-D runs real XNU VBAR handoff through a reversible vector stub.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=23 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 24 ]]; then
      # Stage21-C1: MMU-off EL1t trap; use HVC and EL2's physical stack.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=24 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 25 ]]; then
      # Stage21-C2: first translated instruction and virtual EL1t vector.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=25 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 26 ]]; then
      # Stage21-D: trap/fault after virtual C prologue, preserve EL2 USB return.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=26 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 27 ]]; then
      # Combined Stage22: let XNU run through early relocations and init
      # calls, capture the first real fault or the later C milestone.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=27 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 28 ]]; then
      # Stage23: retain the Stage22 hardware-proven admission and vector
      # checks, run XNU without a synthetic trap, and retain fault logs.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=28 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 29 ]]; then
      # Stage24: native Stage23 XNU continuation with original XNU
      # register snapshot on first EL1 sync HVC for panic provenance.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=29 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 30 ]]; then
      # Stage25: trap exactly where pmap_map_bd would panic for a null
      # kernel page-table entry and capture its VA/PA range and descriptors.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=30 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 31 ]]; then
      # Stage26 diagnostic: temporary reduced framebuffer height in the
      # old XNU boot_args so the initial IO mapping stays below the
      # missing L1 boundary; preserve genuine XNU fault capture.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=31 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE26=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 32 ]]; then
      # Stage27: rebuilt XNU with real early I/O L1 allocation patch;
      # keep full framebuffer geometry and genuine first-fault telemetry.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=32 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE27=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 33 ]]; then
      # Stage28: rebuilt Stage27 Mach-O with the Stage25 exact null-PTE
      # breakpoint and bounded TTBR1 descriptor walk. Still 720x1440.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=33 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 34 ]]; then
      # Stage28 FIX TEST: real rebuilt XNU, patches 0086+0087, original
      # 720x1440 boot arguments, unmodified pmap panic path.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=34 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 35 ]]; then
      # Stage35: same XNU patches 0086+0087; bounded USB handoff-marker
      # flush before ERET, preserving the genuine EL1 fault telemetry.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=35 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 36 ]]; then
      # Stage36: controlled BRK at the validated Stage22 first-C join
      # to force EL1->EL2 diagnostics with the new Stage28 XNU build.
      # Preserve Stage35 pre-handoff USB flush and full-resolution video.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=36 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE36_CHECKPOINT=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 37 ]]; then
      # Stage37: continue past the Stage36 early-C join; trap specifically
      # at the original pmap_map_bd null-PTE panic call if still reached.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=37 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE37_PMAP=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 38 ]]; then
      # Stage38: same successful Stage36 early-C BRK, plus top-RGU
      # watchdog state capture and conditional periodic restart
      # during the post-exception COM25 hold (no WDT mode writes).
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=38 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE36_CHECKPOINT=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 39 ]]; then
      # Keep MTK WDT serviced during preflight, then disable its EN bit
      # with the vendor key and verify before real XNU handoff. Leave
      # the Stage25 pmap panic-join guard active for first-fault capture.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=39 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE37_PMAP=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 40 ]]; then
      # Same rebuilt XNU and proven watchdog disable as Stage39;
      # controlled BRK at first early-C lookup BL (VA ...7ac0c20).
      # The Stage25 pmap panic sentinel remains armed independently.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=40 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE36_CHECKPOINT=1 -DCACTUS_STAGE37_PMAP=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE40_LATE_C=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 41 ]]; then
      # First instruction of the function called at the Stage40 marker.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=41 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE36_CHECKPOINT=1 -DCACTUS_STAGE37_PMAP=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE41_CALLEE_ENTRY=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 42 ]]; then
      # Check whether the boot-argument lookup function returned.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=42 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE36_CHECKPOINT=1 -DCACTUS_STAGE37_PMAP=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE42_AFTER_CALLEE=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 43 ]]; then
      # Check progress beyond second early-C lookup and its branch join.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=43 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE36_CHECKPOINT=1 -DCACTUS_STAGE37_PMAP=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE43_NEXT_INIT=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 44 ]]; then
      # Check whether next early-C initialization function returned.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=44 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE36_CHECKPOINT=1 -DCACTUS_STAGE37_PMAP=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE44_NEXT_RETURN=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 45 || "$STAGE" == 46 || "$STAGE" == 47 ]]; then
      # Combined hardware trial: native XNU C checkpoint + read-only
      # MT6765 OVL0/RDMA0 scanout address/format source snapshots.
      # Only draw the existing Stage23 RAM marker when the live OVL0
      # layer register exactly matches the known framebuffer/stride.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      CHECKPOINT_DEFINE=-DCACTUS_STAGE43_NEXT_INIT=1
      if [[ "$STAGE" == 46 || "$STAGE" == 47 ]]; then
        CHECKPOINT_DEFINE=-DCACTUS_STAGE44_NEXT_RETURN=1
      fi
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE="$STAGE" -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE25=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE36_CHECKPOINT=1 -DCACTUS_STAGE37_PMAP=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE45_COMBINED=1 "$CHECKPOINT_DEFINE" -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
      if [[ "$STAGE" == 47 ]]; then
        EXTRA_DEFINES+=(-DCACTUS_STAGE47_LAYER1=1)
      fi
    elif [[ "$STAGE" == 48 ]]; then
      # Uninterrupted native XNU boot attempt: no synthetic BRK in the
      # early-C join or the pmap panic path. Preserve EL1 exception vectors,
      # USB prehandoff flush, disabled top-RGU watchdog and read-only
      # OVL/RDMA/FDT instrumentation to locate real failures.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=48 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE45_COMBINED=1 -DCACTUS_STAGE47_LAYER1=1 -DCACTUS_STAGE48_RUN=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
    elif [[ "$STAGE" == 49 || "$STAGE" == 50 || "$STAGE" == 51 || "$STAGE" == 52 || "$STAGE" == 53 || "$STAGE" == 54 || "$STAGE" == 55 || "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
      # Stage48 uninterrupted XNU + reserved OVL layer physical-mode
      # guard. Only when SMI LARB0 MMU is off and LK's exact framebuffer
      # carveout is verified, paint a bounded test rectangle on layer1.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=49 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE45_COMBINED=1 -DCACTUS_STAGE47_LAYER1=1 -DCACTUS_STAGE48_RUN=1 -DCACTUS_STAGE49_FB=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
      if [[ "$STAGE" == 50 || "$STAGE" == 51 || "$STAGE" == 52 || "$STAGE" == 53 || "$STAGE" == 54 || "$STAGE" == 55 || "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
        # Keep the Stage49 guard, then redirect bootargs Video to the
        # proven physical scanout L1 for native XNU initialization.
        EXTRA_DEFINES+=(-UCACTUS_TRACE_STAGE -DCACTUS_TRACE_STAGE="$STAGE" -DCACTUS_STAGE50_XNU_FB=1)
        if [[ "$STAGE" == 51 || "$STAGE" == 52 || "$STAGE" == 53 || "$STAGE" == 54 || "$STAGE" == 55 || "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
          EXTRA_DEFINES+=(-DCACTUS_STAGE51_LIVE_CONSOLE=1)
          if [[ "$STAGE" == 52 || "$STAGE" == 53 || "$STAGE" == 54 || "$STAGE" == 55 || "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
            EXTRA_DEFINES+=(-DCACTUS_STAGE52_LIVE_CONSOLE=1)
            if [[ "$STAGE" == 53 || "$STAGE" == 54 || "$STAGE" == 55 || "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
              EXTRA_DEFINES+=(-DCACTUS_STAGE53_LIVE_CONSOLE=1)
              if [[ "$STAGE" == 54 || "$STAGE" == 55 || "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
                EXTRA_DEFINES+=(-DCACTUS_STAGE54_IOKIT_BSD=1)
                if [[ "$STAGE" == 55 || "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
                  EXTRA_DEFINES+=(-DCACTUS_STAGE55_BSD_GATE=1)
                  if [[ "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
                    EXTRA_DEFINES+=(-DCACTUS_STAGE56_CPU_SYNC=1)
                    if [[ "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
                      EXTRA_DEFINES+=(-DCACTUS_STAGE57_CPU0_IRQ=1)
                      if [[ "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
                        EXTRA_DEFINES+=(-DCACTUS_STAGE58_GICV3_REARM=1)
                        if [[ "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
                          EXTRA_DEFINES+=(-DCACTUS_STAGE59_IRQ_WAIT=1)
                          if [[ "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 ]]; then
                            EXTRA_DEFINES+=(-DCACTUS_STAGE60_GICR=1)
                            if [[ "$STAGE" == 61 || "$STAGE" == 62 ]]; then
                              EXTRA_DEFINES+=(-DCACTUS_STAGE61_GICR_ID=1)
                              if [[ "$STAGE" == 62 ]]; then
                                EXTRA_DEFINES+=(-DCACTUS_STAGE62_GICR_MMIO=1)
                              fi
                            fi
                          fi
                        fi
                      fi
                    fi
                  fi
                fi
              fi
            fi
          fi
        fi
      fi
    elif [[ "$STAGE" == 63 || "$STAGE" == 64 || "$STAGE" == 65 || "$STAGE" == 66 || "$STAGE" == 67 || "$STAGE" == 68 || "$STAGE" == 69 || "$STAGE" == 70 || "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
      # Exact Stage62 physical MMIO census plus newly audited Stage63 XNU.
      # Keep all native startup, live console, GIC and recovery paths enabled.
      SOURCES+=(stage19_probe fdt fdt_ranges payload_layout)
      EXTRA_DEFINES=(-DCACTUS_TRACE_STAGE=63 -DCACTUS_STAGE20=1 -DCACTUS_STAGE20B=1 -DCACTUS_STAGE20C=1 -DCACTUS_STAGE20D=1 -DCACTUS_STAGE21C1=1 -DCACTUS_STAGE21C2=1 -DCACTUS_STAGE21D=1 -DCACTUS_STAGE22=1 -DCACTUS_STAGE23=1 -DCACTUS_STAGE24=1 -DCACTUS_STAGE27=1 -DCACTUS_STAGE28_FIX=1 -DCACTUS_STAGE35=1 -DCACTUS_STAGE38_WDT=1 -DCACTUS_STAGE39_WDT_HANDOFF=1 -DCACTUS_STAGE45_COMBINED=1 -DCACTUS_STAGE47_LAYER1=1 -DCACTUS_STAGE48_RUN=1 -DCACTUS_STAGE49_FB=1 -DCACTUS_STAGE50_XNU_FB=1 -DCACTUS_STAGE51_LIVE_CONSOLE=1 -DCACTUS_STAGE52_LIVE_CONSOLE=1 -DCACTUS_STAGE53_LIVE_CONSOLE=1 -DCACTUS_STAGE54_IOKIT_BSD=1 -DCACTUS_STAGE55_BSD_GATE=1 -DCACTUS_STAGE56_CPU_SYNC=1 -DCACTUS_STAGE57_CPU0_IRQ=1 -DCACTUS_STAGE58_GICV3_REARM=1 -DCACTUS_STAGE59_IRQ_WAIT=1 -DCACTUS_STAGE60_GICR=1 -DCACTUS_STAGE61_GICR_ID=1 -DCACTUS_STAGE62_GICR_MMIO=1 -DCACTUS_STAGE63_NATIVE=1 -DCACTUS_TRACE_SLOTS=64 -ffunction-sections -fdata-sections "${PAYLOAD_DEFINE[@]}")
      if [[ "$STAGE" == 64 || "$STAGE" == 65 || "$STAGE" == 66 || "$STAGE" == 67 || "$STAGE" == 68 || "$STAGE" == 69 || "$STAGE" == 70 || "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES[0]=-DCACTUS_TRACE_STAGE=$STAGE; fi
      if [[ "$STAGE" == 65 || "$STAGE" == 66 || "$STAGE" == 67 || "$STAGE" == 68 || "$STAGE" == 69 || "$STAGE" == 70 || "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE65_NATIVE=1); fi
      if [[ "$STAGE" == 66 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE66_NATIVE=1); fi
      if [[ "$STAGE" == 67 || "$STAGE" == 68 || "$STAGE" == 69 || "$STAGE" == 70 || "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE67_NATIVE=1); fi
      if [[ "$STAGE" == 68 || "$STAGE" == 69 || "$STAGE" == 70 || "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE68_NATIVE=1); fi
      if [[ "$STAGE" == 69 || "$STAGE" == 70 || "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE69_NATIVE=1); fi
      if [[ "$STAGE" == 70 || "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE70_NATIVE=1); fi
      if [[ "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE71_NATIVE=1); fi
      if [[ "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE72_NATIVE=1); fi
      if [[ "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE73_NATIVE=1); fi
      if [[ "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE74_NATIVE=1); fi
      if [[ "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE75_NATIVE=1); fi
      if [[ "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE76_NATIVE=1); fi
      if [[ "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE77_NATIVE=1); fi
      if [[ "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE78_NATIVE=1); fi
      if [[ "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE79_NATIVE=1); fi
      if [[ "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE80_NATIVE=1); fi
      if [[ "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE81_NATIVE=1); fi
      if [[ "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE82_NATIVE=1); fi
      if [[ "$STAGE" == 83 || "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE83_NATIVE=1); fi
      if [[ "$STAGE" == 84 ]]; then EXTRA_DEFINES+=(-DCACTUS_STAGE84_NATIVE=1); fi
    else
      SOURCES+=(stage14_probe)
    fi
    for source in "${SOURCES[@]}"; do
      aarch64-linux-gnu-gcc "${CFLAGS[@]}" -Wall -Wextra -Werror \
          "${EXTRA_DEFINES[@]}" \
          -c "$source.c" -o "$PREFIX-$source.o"
      OBJECTS+=("$PREFIX-$source.o")
    done
  else
    USB_PROBE_LEVEL=2
    if [[ "$STAGE" == 9 ]]; then USB_PROBE_LEVEL=0; fi
    if [[ "$STAGE" == 10 ]]; then USB_PROBE_LEVEL=1; fi
    if [[ "$STAGE" == 11 ]]; then USB_PROBE_LEVEL=3; fi
    if [[ "$STAGE" == 12 ]]; then USB_PROBE_LEVEL=4; fi
    if [[ "$STAGE" == 13 ]]; then USB_PROBE_LEVEL=5; fi
    aarch64-linux-gnu-gcc "${CFLAGS[@]}" -Wall -Wextra -Werror \
        -DUSB_PROBE_LEVEL="$USB_PROBE_LEVEL" \
        -c musb_cdc_probe.c -o "$PREFIX-musb.o"
    OBJECTS+=("$PREFIX-musb.o")
  fi
fi
if [[ "$STAGE" -ge 16 ]]; then
  aarch64-linux-gnu-ld --build-id=none -N -e _start --gc-sections -Ttext=0 "${OBJECTS[@]}" -o "$PREFIX.elf"
else
  aarch64-linux-gnu-ld --build-id=none -N -Ttext=0 "${OBJECTS[@]}" -o "$PREFIX.elf"
fi
aarch64-linux-gnu-objcopy -O binary "$PREFIX.elf" "$PREFIX-Image"

# The C function for stage 4 is linked after the probe assembly's end label.
# Correct the Linux arm64 Image header to cover the complete emitted code.
python3 - "$PREFIX-Image" <<'PY'
import struct
import sys
from pathlib import Path
path = Path(sys.argv[1])
data = bytearray(path.read_bytes())
assert data[0x38:0x3c] == bytes((65, 82, 77, 100))
struct.pack_into('<Q', data, 0x10, len(data))
path.write_bytes(data)
print('probe Image', len(data), 'bytes')
PY

gzip -9 -c "$PREFIX-Image" > "$PREFIX.gz"
cat "$PREFIX.gz" "$DTB" > "$PREFIX.gz-dtb"
IMAGE="$PWD/out/cactus/cactus-trace-stage-$STAGE-boot.img"
if [[ "$STAGE" == 18 ]]; then
  # Keep the first hardware-tested Stage18 image intact for comparing
  # its reproducible unaligned-payload data abort with this fix.
  IMAGE="$PWD/out/cactus/cactus-trace-stage-18-aligned-boot.img"
fi
python3 "$MKBOOT" --header_version 2 \
    --kernel "$PREFIX.gz-dtb" --ramdisk "$OUT/trace-ramdisk.bin" --dtb "$DTBO" \
    --base 0x40078000 --kernel_offset 0x00008000 \
    --ramdisk_offset 0x11A88000 --second_offset 0x000E8000 \
    --tags_offset 0x07808000 --dtb_offset 0x07808000 \
    --pagesize 2048 --os_version 11.0.0 \
    --cmdline "bootopt=64S3,32N2,64N2 androidboot.selinux=permissive buildvariant=user" \
    -o "$IMAGE"
python3 check_image.py "$IMAGE"
sha256sum "$IMAGE"
if [[ "$STAGE" == 51 || "$STAGE" == 52 || "$STAGE" == 53 || "$STAGE" == 54 || "$STAGE" == 55 || "$STAGE" == 56 || "$STAGE" == 57 || "$STAGE" == 58 || "$STAGE" == 59 || "$STAGE" == 60 || "$STAGE" == 61 || "$STAGE" == 62 || "$STAGE" == 63 || "$STAGE" == 64 || "$STAGE" == 65 || "$STAGE" == 66 || "$STAGE" == 67 || "$STAGE" == 68 || "$STAGE" == 69 || "$STAGE" == 70 || "$STAGE" == 71 || "$STAGE" == 72 || "$STAGE" == 73 || "$STAGE" == 74 || "$STAGE" == 75 || "$STAGE" == 76 || "$STAGE" == 77 || "$STAGE" == 78 || "$STAGE" == 79 || "$STAGE" == 80 || "$STAGE" == 81 || "$STAGE" == 82 || "$STAGE" == 83 || "$STAGE" == 84 ]]; then
  # Pair the image with a hash the Stage51 hardware runner must check.
  sha256sum "$IMAGE" > "$IMAGE.sha256"
fi
echo "OFFLINE image: $IMAGE"
echo "After an approved test that reaches TWRP:"
echo "  adb exec-out cat /cactus-trace.bin > cactus-trace.bin"
echo "  python3 shim/trace_initramfs.py decode cactus-trace.bin"
