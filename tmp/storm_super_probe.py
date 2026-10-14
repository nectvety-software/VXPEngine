"""Capture the super-move VFX (speed lines + dust cloud) from StormArena25D.
Assumes a build whose gauge fills instantly (TEMP-VFX-PROBE)."""
import subprocess
import sys
import time

sys.path.insert(0, r"D:\MRE\VXPEngine\tmp")
from storm_emu_test import EMU, OUT, VXP, diff, find_window, grab, key  # noqa


def main():
    subprocess.Popen([EMU, VXP, "--screen-only", "--autostart"])
    hwnd = 0
    for _ in range(40):
        time.sleep(0.5)
        hwnd = find_window()
        if hwnd:
            break
    if not hwnd:
        print("FAIL: window not found")
        return 1
    for i in range(60):
        time.sleep(0.5)
        img = grab(hwnd, OUT + r"\boot.png")
        if img is None:
            continue
        r, g, b = img.load()[4, 312]
        if r > 200 and g > 200 and b > 200:
            break
    print("booted")
    # close the distance, land two hits to charge, then super
    for _ in range(14):
        key(hwnd, "RIGHT")
    key(hwnd, "NP5")
    time.sleep(0.4)
    key(hwnd, "NP5")
    time.sleep(0.4)
    for n in ("u0", "u1", "u2", "u3", "u4"):
        key(hwnd, "NP8", 0.05)
        time.sleep(0.12)
        grab(hwnd, OUT + "\\" + n + ".png")
    print("captured u0..u4")
    a = grab(hwnd, OUT + r"\u0.png")
    b = grab(hwnd, OUT + r"\u3.png")
    print("changed u0->u3:", diff(a, b))
    return 0


if __name__ == "__main__":
    sys.exit(main())
