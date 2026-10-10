#!/usr/bin/env python3
"""Do chi phi fill tren ARM mot cach tat dinh (khong dung dong ho host).

Tren thiet bi MRE khong co DWT/CYCCNT va `vm_get_tick_count()` trong VXPEmu tra
ve dong ho host, nen thoi gian do bang dong ho khong noi gi ve cycle cua ARM.
Thay vao do script nay:

  1. bien dich core + scene cho ARM dung co nhu ban ship
     (-march=armv5te -mthumb -O3 -ffunction-sections -fdata-sections);
  2. chay ma ARM tren Unicorn (QEMU TCG ARM) va dem *so instruction thuc thi*,
     phan loai theo nhom opcode (store / load / mul / bl);
  3. do tung cau hinh hai lan voi iters = n va 2n roi lay hieu, nen moi chi phi
     co dinh (prologue, khoi tao) tu triet tieu;

So instruction la tat dinh: chay lai cho ket qua y het, va khong phu thuoc CPU
cua may host. Day khong phai so cycle cua thiet bi - xem docs/ARM_FILL_COST.md.
"""
import argparse
import json
import os
import struct
import subprocess
import sys

import capstone
import unicorn
from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_R0, UC_ARM_REG_SP

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(DEMO, "..", ".."))
CORE = os.path.join(REPO, "packaging", "coremre", "2.0.0")
OUT = os.path.join(DEMO, "build-armbench")

GCC = os.environ.get("VXPE_ARM_GCC", "arm-none-eabi-gcc")
NM = os.environ.get("VXPE_ARM_NM", "arm-none-eabi-nm")

CFLAGS = [
    "-march=armv5te", "-mthumb", "-O3",
    "-ffunction-sections", "-fdata-sections",
    "-fno-threadsafe-statics", "-fno-exceptions", "-fno-non-call-exceptions",
    "-fno-use-cxa-atexit", "-fno-rtti", "-fno-builtin",
]
CXXFLAGS = CFLAGS + ["-std=c++17"]

LINKER_SCRIPT = """\
ENTRY(bench_halt)
SECTIONS
{
  . = 0x00008000;
  /* --gc-sections bo moi section khong duoc tham chieu, ma cac ham bench khong
     duoc ai goi trong ELF; KEEP giu chung lai de con symbol cho trinh chay. */
  .text : { KEEP(*(.text.bench*)) *(.text*) *(.rodata*) *(.init_array*) *(.data*) }
  . = ALIGN(16);
  .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) __bss_end = .; }
}
"""

ROM_BASE, ROM_SIZE = 0x00000000, 0x00100000
RAM_BASE, RAM_SIZE = 0x20000000, 0x00100000
STACK_TOP = RAM_BASE + RAM_SIZE - 0x1000

CORE_SOURCES = [
    os.path.join(CORE, "src", "graphics", "VxpRender2D.cpp"),
    os.path.join(CORE, "src", "graphics", "VxpToon3D.cpp"),
]

STORES = ("str", "stm", "push", "vst")
LOADS = ("ldr", "ldm", "pop", "vld")
MULS = ("mul", "mla", "smul", "smla", "umul", "umla")


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        sys.exit("FAIL %s\n%s\n%s" % (" ".join(cmd), p.stdout, p.stderr))
    return p.stdout


def elf_segments(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        sys.exit("khong phai ELF32 little-endian: %s" % path)
    e_phoff, = struct.unpack_from("<I", data, 0x1C)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x2A)
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from("<IIIIII", data, off)
        if p_type == 1 and p_memsz:
            segs.append((p_vaddr, p_filesz, p_memsz, data[p_offset:p_offset + p_filesz]))
    return segs


def symbols(path, wanted):
    out = run([NM, "-n", path])
    addr = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] in wanted:
            addr[parts[2]] = int(parts[0], 16)
    missing = wanted - set(addr)
    if missing:
        sys.exit("thieu symbol: %s" % ", ".join(sorted(missing)))
    return addr


class Counter:
    def __init__(self):
        self.md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
        self.cache = {}
        self.reset()

    def reset(self):
        self.insns = 0
        self.stores = 0
        self.loads = 0
        self.muls = 0
        self.branches = 0

    def classify(self, uc, addr, size):
        key = (addr, size)
        hit = self.cache.get(key)
        if hit is None:
            code = bytes(uc.mem_read(addr, size))
            n = s = l = m = b = 0
            for insn in self.md.disasm(code, addr):
                n += 1
                mn = insn.mnemonic
                if mn.startswith(STORES):
                    s += 1
                elif mn.startswith(LOADS):
                    l += 1
                elif mn.startswith(MULS):
                    m += 1
                if mn.startswith("b") and mn != "bic":
                    b += 1
            hit = (n, s, l, m, b)
            self.cache[key] = hit
        return hit

    def hook(self):
        def cb(uc, addr, size, _ud):
            n, s, l, m, b = self.classify(uc, addr, size)
            self.insns += n
            self.stores += s
            self.loads += l
            self.muls += m
            self.branches += b
            return True
        return cb


def emulate(elf, syms, func, iters):
    uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
    uc.mem_map(ROM_BASE, ROM_SIZE, unicorn.UC_PROT_ALL)
    uc.mem_map(RAM_BASE, RAM_SIZE, unicorn.UC_PROT_ALL)
    for vaddr, filesz, _memsz, blob in elf_segments(elf):
        if blob:
            uc.mem_write(vaddr, blob)
    uc.reg_write(UC_ARM_REG_SP, STACK_TOP)
    uc.reg_write(UC_ARM_REG_CPSR, 0x30)  # USR | Thumb
    uc.reg_write(UC_ARM_REG_R0, iters)

    counter = Counter()
    uc.hook_add(unicorn.UC_HOOK_BLOCK, counter.hook())

    # Diem dung: hook CODE ngay tai bench_halt va tra False de dung han, thay vi
    # phu thuoc vao cach Unicorn so sanh `until` trong Thumb.
    def stop(uc, addr, size, _ud):
        return False
    uc.hook_add(unicorn.UC_HOOK_CODE, stop, None, syms["bench_halt"], syms["bench_halt"])

    try:
        uc.emu_start(syms[func], 0)
    except unicorn.UcError as e:
        sys.exit("Unicorn loi khi chay %s: %s" % (func, e))
    return counter


def build(name, sources, cxx=True, extra=()):
    os.makedirs(OUT, exist_ok=True)
    ld = os.path.join(OUT, "bench.ld")
    with open(ld, "w", encoding="utf-8", newline="\n") as f:
        f.write(LINKER_SCRIPT)
    objs = []
    for src in sources:
        obj = os.path.join(OUT, "%s-%s.o" % (name, os.path.splitext(os.path.basename(src))[0]))
        run([GCC, "-c", src, "-o", obj, "-I", os.path.join(CORE, "include"),
             "-I", os.path.join(DEMO, "src")] + (CXXFLAGS if cxx else CFLAGS) + list(extra))
        objs.append(obj)
    elf = os.path.join(OUT, name + ".elf")
    run([GCC, "-nostdlib", "-Wl,--gc-sections", "-Wl,-T," + ld, "-o", elf] + objs + ["-lgcc"])
    return elf


def per_iter(elf, syms, func, n):
    """Do voi iters = n va 2n, tra ve chi phi moi vong lap."""
    a = emulate(elf, syms, func, n)
    ca = (a.insns, a.stores, a.loads, a.muls, a.branches)
    b = emulate(elf, syms, func, 2 * n)
    cb = (b.insns, b.stores, b.loads, b.muls, b.branches)
    return tuple((y - x) / n for x, y in zip(ca, cb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(OUT, "arm_fill_cost.json"))
    args = ap.parse_args()

    gen = os.path.join(HERE, "gen")
    run([sys.executable, os.path.join(HERE, "make_variants.py")])

    results = {}

    # --- bau troi: plain vs dither, cung hinh chu nhat va cung hai mau ---
    sky = build("sky", CORE_SOURCES + [os.path.join(HERE, "bench_sky.cpp")])
    syms = symbols(sky, {"bench_sky_plain", "bench_sky_dither", "bench_halt"})
    for func in ("bench_sky_plain", "bench_sky_dither"):
        results[func] = per_iter(sky, syms, func, 2)

    # --- thap: nay / phang (cung hinh hoc) / ban truoc (hinh hoc cu) ---
    for variant in ("scene_tower_now", "scene_tower_flat", "scene_tower_prev"):
        elf = build(variant, CORE_SOURCES + [os.path.join(gen, variant + ".cpp"),
                                             os.path.join(HERE, "bench_tower.cpp")])
        syms = symbols(elf, {"bench_run", "bench_halt"})
        results[variant] = per_iter(elf, syms, "bench_run", 1)

    keys = ("instructions", "stores", "loads", "muls", "branches")

    def show(title, base, test):
        b, t = results[base], results[test]
        print("\n%s" % title)
        print("  %-14s %12s %10s" % ("", "instructions", "stores"))
        print("  %-14s %12.0f %10.0f" % (base, b[0], b[1]))
        print("  %-14s %12.0f %10.0f" % (test, t[0], t[1]))
        print("  %-14s %12.3fx %9.3fx" % ("ty le", t[0] / b[0], t[1] / b[1]))

    print("=== chi phi fill tren ARM (so instruction thuc thi / moi lan ve) ===")
    for k, v in results.items():
        print("  %-18s insns=%8.0f stores=%7.0f loads=%7.0f muls=%6.0f branches=%7.0f"
              % (k, v[0], v[1], v[2], v[3], v[4]))

    show("BAU TROI: gradient phang -> dither (cung hinh chu nhat, cung 2 mau)",
         "bench_sky_plain", "bench_sky_dither")
    show("THAP: shading phang theo quad -> per-vertex (Y NGUYEN hinh hoc)",
         "scene_tower_flat", "scene_tower_now")
    show("THAP: ban truoc (hinh hoc + shading cu) -> hien tai",
         "scene_tower_prev", "scene_tower_now")

    payload = {k: dict(zip(keys, v)) for k, v in results.items()}
    payload["ratios"] = {
        "sky_dither_over_plain": results["bench_sky_dither"][0] / results["bench_sky_plain"][0],
        "tower_now_over_flat": results["scene_tower_now"][0] / results["scene_tower_flat"][0],
        "tower_now_over_prev": results["scene_tower_now"][0] / results["scene_tower_prev"][0],
        "tower_store_now_over_flat": results["scene_tower_now"][1] / results["scene_tower_flat"][1],
        "tower_store_now_over_prev": results["scene_tower_now"][1] / results["scene_tower_prev"][1],
    }
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print("\njson: %s" % args.json)


if __name__ == "__main__":
    main()
