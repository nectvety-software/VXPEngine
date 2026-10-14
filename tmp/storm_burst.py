"""Grab a timed burst of StormArena25D frames from a fresh emulator launch and
tile them into a contact sheet for visual review."""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storm_emu_test import EMU, VXP, OUT, find_window, grab  # noqa: E402
from PIL import Image


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
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
    shots = []
    for i in range(n):
        img = grab(hwnd, OUT + r"\burst%02d.png" % i)
        if img is None:
            print("FAIL: no client rect")
            return 1
        shots.append(img)
        time.sleep(gap)
    sc = 2
    cols = 5
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (240 * sc * cols, 320 * sc * rows), (18, 18, 18))
    for i, im in enumerate(shots):
        sheet.paste(im.resize((240 * sc, 320 * sc), Image.NEAREST),
                    ((i % cols) * 240 * sc, (i // cols) * 320 * sc))
    sheet.save("tmp/burst_sheet.png")
    print("wrote tmp/burst_sheet.png with", n, "frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
