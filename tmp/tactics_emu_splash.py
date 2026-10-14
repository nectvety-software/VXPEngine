"""Second TacticsVanguard2D device pass. The first run (tmp/tactics_emu_test.py)
started grabbing after the splash card had already auto-advanced, so the splash,
the briefing page and the path arrow were never seen on real hardware.

This one polls the window from the first paint and saves every frame until the
menu's gold card border shows at (14,150) -- the splash panel is inset to x=18,
so that pixel can only be the menu -- then walks menu -> briefing -> battle ->
path arrow -> action card in lock step and finally ends the player phase over
and over until the result screen appears.

Same capture path as the first run: DPI-aware PrintWindow on the 240x320 client
area. ASCII output only (cp1252 console).
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tactics_emu_test as T

PREV = [None]


def shot(hwnd, name):
    img = T.grab(hwnd, os.path.join(T.OUT, name + ".png"))
    if img is None:
        print("FAIL: empty client rect at %s" % name)
        return None
    motion = "" if PREV[0] is None else "motion %d px" % T.diff(PREV[0], img)
    PREV[0] = img
    print("%-18s %s" % (name, motion))
    return img


def main():
    os.makedirs(T.OUT, exist_ok=True)
    subprocess.call(["taskkill", "/IM", "VXPEmu.exe", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.25)
        if not T.find_window():
            break
    time.sleep(1.0)
    subprocess.Popen([T.EMU, T.VXP, "--screen-only", "--autostart"])
    hwnd = 0
    waited = 0.0
    while waited < 12.0:
        time.sleep(0.1)
        waited += 0.1
        hwnd = T.find_window()
        if hwnd:
            break
    if not hwnd:
        print("FAIL: window not found")
        return 1
    print("window after %.1f s" % waited)
    on_menu = False
    for i in range(30):
        time.sleep(0.3)
        img = T.grab(hwnd, os.path.join(T.OUT, "s00_poll_%02d.png" % i))
        if img is None:
            continue
        r, g, b = img.load()[14, 150]
        menu = r > 150 and 90 < g < 200 and b < 90
        print("poll %2d  (14,150)=(%3d,%3d,%3d) %s" %
              (i, r, g, b, "MENU" if menu else "panel"))
        if menu:
            on_menu = True
            break
    if not on_menu:
        print("FAIL: never reached the menu card")
        return 1
    PREV[0] = None
    shot(hwnd, "s01_menu")
    T.key(hwnd, "NP8")
    T.key(hwnd, "NP8")
    time.sleep(0.5)
    shot(hwnd, "s02_menu_briefing")
    T.key(hwnd, "NP5")
    time.sleep(0.6)
    shot(hwnd, "s03_briefing")
    T.key(hwnd, "NP5")
    time.sleep(0.6)
    shot(hwnd, "s04_menu")
    T.key(hwnd, "NP6")
    time.sleep(0.5)
    shot(hwnd, "s05_menu_crimson")
    T.key(hwnd, "NP4")
    time.sleep(0.5)
    shot(hwnd, "s06_menu_azure")
    T.key(hwnd, "NP2")
    T.key(hwnd, "NP2")
    T.key(hwnd, "NP2")
    time.sleep(0.4)
    shot(hwnd, "s07_menu_top")
    T.key(hwnd, "NP5")
    time.sleep(1.0)
    img = shot(hwnd, "s08_battle")
    if img:
        T.hud_zoom(img, os.path.join(T.OUT, "s08_hud.png"))
    T.key(hwnd, "NP5")
    time.sleep(0.5)
    shot(hwnd, "s09_range")
    T.key(hwnd, "NP2")
    T.key(hwnd, "NP2")
    T.key(hwnd, "NP2")
    time.sleep(0.5)
    shot(hwnd, "s10_path")
    T.key(hwnd, "NP5")
    time.sleep(0.3)
    shot(hwnd, "s11_walk")
    time.sleep(1.3)
    img = shot(hwnd, "s12_card")
    if img:
        T.hud_zoom(img, os.path.join(T.OUT, "s12_hud.png"))
    T.key(hwnd, "NP5")
    time.sleep(0.6)
    shot(hwnd, "s13_after")
    for i in range(16):
        T.key(hwnd, "NP9")
        time.sleep(6.0)
        if shot(hwnd, "s14_end%02d" % i) is None:
            return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
