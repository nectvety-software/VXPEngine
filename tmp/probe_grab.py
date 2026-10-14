"""Fresh-launch grab + colour forensics for the StormArena25D billboard probe.
ASCII output only (cp1252 console)."""
import collections
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storm_emu_test import EMU, VXP, OUT, find_window, grab, probe_ms  # noqa: E402


def analyze(path):
    from PIL import Image
    img = Image.open(path)
    px = img.load()
    counts = collections.Counter()
    boxes = {}
    for y in range(320):
        for x in range(240):
            c = px[x, y]
            counts[c] += 1
            b = boxes.get(c)
            if b is None:
                boxes[c] = [x, y, x, y]
            else:
                b[0] = min(b[0], x); b[1] = min(b[1], y)
                b[2] = max(b[2], x); b[3] = max(b[3], y)
    print("probe ms:", probe_ms(img))
    for c, n in counts.most_common(14):
        b = boxes[c]
        print("  rgb%s n=%d bbox=(%d,%d,%d,%d)" % (c, n, b[0], b[1], b[2], b[3]))


def main():
    os.makedirs(OUT, exist_ok=True)
    subprocess.call(["taskkill", "/IM", "VXPEmu.exe", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.25)
        if not find_window():
            break
    else:
        print("FAIL: emulator window survived the kill")
        return 1
    time.sleep(1.5)
    print("vxp mtime:", time.strftime("%H:%M:%S", time.localtime(
        os.path.getmtime(VXP))), "size:", os.path.getsize(VXP))
    t_launch = time.time()
    subprocess.Popen([EMU, VXP, "--screen-only", "--autostart"])
    hwnd = 0
    for _ in range(60):
        time.sleep(0.5)
        hwnd = find_window()
        if hwnd:
            break
    if not hwnd:
        print("FAIL: no window")
        return 1
    print("window after %.1fs" % (time.time() - t_launch))
    for i in range(80):
        time.sleep(0.5)
        img = grab(hwnd, OUT + r"\probe.png")
        if img is None:
            continue
        r, g, b = img.load()[4, 312]
        if r > 200 and g > 200 and b > 200:
            print("booted after %.1fs" % (time.time() - t_launch))
            break
    else:
        print("WARN: HUD label never appeared")
    for name in ("probe", "probe2"):
        grab(hwnd, OUT + "\\" + name + ".png")
        print("== %s ==" % name)
        analyze(OUT + "\\" + name + ".png")
        time.sleep(1.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
