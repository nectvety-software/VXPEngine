"""TacticsVanguard2D device pass 5: re-verify the rebuilt .vxp (the splash bar
clamp) end to end on a fresh boot -- 0.25 s splash polling so the t=51..54
window where the fill used to overshoot the track is actually sampled, then
menu -> battle -> one AI round. ASCII output only (cp1252 console)."""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tactics_emu_test as T
import tactics_emu_tour as U

OUT = r"tmp\tactics_emu_final"
PREV = [None]


def shot(hwnd, name):
    img = T.grab(hwnd, os.path.join(OUT, name + ".png"))
    if img is None:
        print("FAIL: empty client rect at %s" % name)
        return None
    motion = 0 if PREV[0] is None else T.diff(PREV[0], img)
    PREV[0] = img
    print("%-18s motion %5d px" % (name, motion))
    return img


def bar_px(img):
    """Width of the gold loading-bar fill on the splash (track is 100 px at x70)."""
    px = img.load()
    n = 0
    for x in range(70, 200):
        r, g, b = px[x, 196]
        if r > 170 and 130 < g < 220 and b < 120:
            n += 1
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
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
    PREV[0] = None
    on_menu = False
    for i in range(26):
        time.sleep(0.25)
        img = T.grab(hwnd, os.path.join(OUT, "f00_splash_%02d.png" % i))
        if img is None:
            continue
        row = U.menu_row(img)
        print("splash %2d  bar %3d px  %s" %
              (i, bar_px(img), "MENU row %d" % row if row >= 0 else "card"))
        if row >= 0:
            on_menu = True
            break
    if not on_menu:
        print("FAIL: menu never appeared")
        return 1
    PREV[0] = None
    shot(hwnd, "f01_menu")
    if not U.goto_row(hwnd, 0):
        print("FAIL: cannot reach BEGIN BATTLE")
        return 1
    T.key(hwnd, "NP5")
    time.sleep(1.2)
    img = shot(hwnd, "f02_battle")
    if img:
        T.hud_zoom(img, os.path.join(OUT, "f02_hud.png"))
    T.key(hwnd, "NP5")
    time.sleep(0.6)
    img = shot(hwnd, "f03_range")
    if img:
        T.hud_zoom(img, os.path.join(OUT, "f03_hud.png"))
    T.key(hwnd, "NP9")
    for i in range(8):
        time.sleep(1.1)
        T.key(hwnd, "NP9")
        if shot(hwnd, "f04_ai_%02d" % i) is None:
            return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
