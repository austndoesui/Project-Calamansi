#!/usr/bin/env python3
"""Generate CACTUS-only Stage60 SGI8 candidate + GIC redistributor diagnostics."""
from pathlib import Path
import importlib.util, difflib, argparse

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("stage59_gen",ROOT/"tools/stage59_generate_patch.py")
gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)

def repl(s, old, new, label):
    if s.count(old)!=1:
        raise ValueError(f"{label}: expected once, got {s.count(old)}")
    return s.replace(old,new)

def prior(rel):
    s=(ROOT/"shim/out/cactus/stage59-source"/rel).read_text()
    for bef,aft,label in gen.EDITS.get(rel,[]):
        s=repl(s,bef,aft,"Stage59 "+label)
    return s

def header():
    text=(ROOT/"xnu/patches/0082-cactus-machine-config.patch").read_text()
    start=text.index("diff --git a/pexpert/pexpert/arm64/CACTUS.h")
    end=text.index("\ndiff --git ",start+10)
    chunk=text[start:end]
    return "\n".join(line[1:] for line in chunk.splitlines() if line.startswith("+") and not line.startswith("+++"))+"\n"

def build():
    h=header()
    h2=repl(h,"#define SWEET_IPI_SGI             1       // SGI used for cross-CPU signals",
            "#define SWEET_IPI_SGI             8       // CACTUS Stage60: test NS SGI8 (SGI1 enable was RAZ/WI)", "sgid")
    rel="pexpert/arm/pe_fiq.c"; old=prior(rel);new=old
    new=repl(new,
      "    vm_offset_t gicr_pe_base = find_gicr_pe_base();\n    if (gicr_read32(GICR_WAKER) & GICR_WAKER_PROCESSORSLEEP) {",
      """    vm_offset_t gicr_pe_base = find_gicr_pe_base();
    /* Non-acknowledging GICv3 diagnostics on the actual CPU0 redistributor.
     * Read-only security group registers. Do not touch EL3-owned policy. */
    kprintf("ST60 GICR base=0x%llx pe=0x%llx mpidr=0x%llx typer=0x%llx\\n",
        (unsigned long long)gicr_base, (unsigned long long)gicr_pe_base,
        (unsigned long long)__builtin_arm_rsr64("MPIDR_EL1"),
        (unsigned long long)gicr_read64(GICR_TYPER));
    kprintf("ST60 GICR pre: ctlr=%x waker=%x group=%x mod=%x nsacr=%x enable=%x pending=%x\\n",
        gicr_read32(0), gicr_read32(GICR_WAKER),
        gicr_read32(GICR_IGROUPR0), gicr_read32(0x10D00),
        gicr_read32(0x10E00), gicr_read32(GICR_ISENABLER0),
        gicr_read32(0x10200));
    if (gicr_read32(GICR_WAKER) & GICR_WAKER_PROCESSORSLEEP) {""",
      "stage60-before")
    new=repl(new,
      '    kprintf("ST59 SGI enable readback=0x%x\\n",\n        gicr_read32(GICR_ISENABLER0));',
      '''    /* Linux waits for GICR_CTLR.RWP following SGI-frame programming. */
    uint64_t rwp_deadline;
    nanoseconds_to_deadline(10000000ULL, &rwp_deadline);
    while (gicr_read32(0) & (1U << 3)) {
        if (mach_absolute_time() > rwp_deadline) {
            kprintf("ST60 GICR RWP timeout\\n");
            break;
        }
    }
    kprintf("ST60 GICR post: ctlr=%x group=%x mod=%x enable=%x pending=%x\\n",
        gicr_read32(0), gicr_read32(GICR_IGROUPR0),
        gicr_read32(0x10D00), gicr_read32(GICR_ISENABLER0),
        gicr_read32(0x10200));''',
      "stage60-after")
    new=repl(new,
      'kprintf("ST59 GICR after pe_init enable=0x%x wake=0x%x\\n",',
      'kprintf("ST60 GICR init enable=0x%x wake=0x%x\\n",',
      "stage60-init")
    c_rel="iokit/Kernel/arm/SweetCPU.cpp"; co=prior(c_rel);cn=co
    for prev,next_,name in [
      ("ST59 GIC SGI1 rearm","ST60 rearm SGI8","rearm"),
      ("ST59 GIC SGI after rearm status=","ST60 GIC SGI8 rearm status=","status"),
      ("ST59 SGI1 enable not latched","ST60 SGI8 enable blocked","blocked"),
      ("ST59 SGI1 enabled","ST60 SGI8 enabled","enabled"),
      ("ST59 SGI1 sent","ST60 SGI8 sent","sent")
    ]:
        cn=repl(cn,prev,next_,name)
    result=[]
    for rel,a,b in [("pexpert/pexpert/arm64/CACTUS.h",h,h2),(rel,old,new),(c_rel,co,cn)]:
        result.append(f"diff --git a/{rel} b/{rel}\n")
        result.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),
                                  fromfile=f"a/{rel}",tofile=f"b/{rel}"))
    return "".join(result)

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);args=ap.parse_args()
    blob=build();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(blob.encode());print("STAGE60_PATCH",args.output,len(blob))
