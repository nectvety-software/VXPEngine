"""Trace both fighters' health bars over a fresh match to measure real pacing."""
import ctypes
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storm_emu_test import EMU, VXP, OUT, find_window, grab  # noqa: E402

YELLOW = (247, 215, 90)   # rgb565 round-trip of the HUD bar colour


def hp(px, side):
    n = 0
    for x in range(2, 106):
        xx = x if side == 0 else 240 - 2 - x
        r, g, b = px[xx, 9]
        if r > 200 and 170 < g < 245 and b < 140:
            n += 1
    return n * 100 // 104


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
    t0 = time.time()
    proc = subprocess.Popen([EMU, VXP, "--screen-only", "--autostart"])
    hwnd = 0
    pid = ctypes.c_ulong()
    while time.time() - t0 < 30:
        time.sleep(0.2)
        hwnd = find_window()
        if hwnd:
            ctypes.windll.user32.GetWindowThreadProcessId(
                ctypes.c_void_p(hwnd), ctypes.byref(pid))
            break
    if not hwnd:
        print("FAIL: no window")
        return 1
    print("launched pid=%d window pid=%d match=%s"
          % (proc.pid, pid.value, proc.pid == pid.value))
    for i in range(40):
        img = grab(hwnd, OUT + r"\tr%02d.png" % i)
        if img is None:
            print("no rect")
            continue
        px = img.load()
        print("t=%5.2fs ren=%3d kuro=%3d" % (time.time() - t0, hp(px, 0),
                                             hp(px, 1)))
        time.sleep(0.35)
    return 0


if __name__ == "__main__":
    sys.exit(main())
