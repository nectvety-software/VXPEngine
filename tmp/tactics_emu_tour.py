"""TacticsVanguard2D device tour, pass 3.

Pass 2 froze because its menu walk used 4/6 for the army flip while the app also
treats 4/6 as row navigation off the CHANGE ARMY row: the cursor slid onto EXIT,
5 there calls vm_exit_app(), and every later PrintWindow grab returned the dead
app's last frame. This driver never presses a key blindly: it reads the menu's
3px gold highlight strip (x=25, y=150+26*row+10) out of the screenshot to
position the cursor, and the battle leg follows the deterministic spawn layout
(cursor starts on CAEDRIC at 7,14; two tiles north is open ground).

Capture path is the same DPI-aware PrintWindow helper as the earlier passes.
ASCII output only (cp1252 console).
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tactics_emu_test as T

GOLD = (228, 182, 60)
# The highlight is a 20px-tall, 3px-wide gold strip; the splash's card rules are
# 2px-tall horizontal lines that cross the same x at y=212, so a single sample
# there reads as a "selected row 2". Two samples 13px apart only fit the strip.
ROWS = [(150 + 26 * i) for i in range(4)]
PREV = [None]


def near(c, ref, tol=40):
    return all(abs(c[i] - ref[i]) <= tol for i in range(3))


def shot(hwnd, name, tag=None):
    img = T.grab(hwnd, os.path.join(T.OUT, name + ".png"))
    if img is None:
        print("FAIL: empty client rect at %s" % name)
        return None
    motion = 0 if PREV[0] is None else T.diff(PREV[0], img)
    PREV[0] = img
    print("%-20s motion %3d px  %s" % (name, motion, tag or ""))
    return img


def menu_row(img):
    px = img.load()
    for i, ry in enumerate(ROWS):
        if near(px[25, ry + 3], GOLD, 60) and near(px[25, ry + 16], GOLD, 60):
            return i
    return -1


def wait_menu(hwnd, limit=10):
    for _ in range(limit):
        img = T.grab(hwnd, os.path.join(T.OUT, "_tmp.png"))
        if img is not None:
            r = menu_row(img)
            if r >= 0:
                return r
        time.sleep(0.35)
    return -1


def goto_row(hwnd, target):
    """Move the menu cursor with 2/8 until the highlight strip reads `target`."""
    for _ in range(9):
        r = wait_menu(hwnd, 1)
        if r == target:
            return True
        if r < 0:
            print("  goto_row: not on the menu")
            return False
        d = (target - r) % 4
        for _ in range(d if d <= 2 else 4 - d):
            T.key(hwnd, "NP8" if d <= 2 else "NP2")
        time.sleep(0.3)
    print("  goto_row: stuck at row %d, wanted %d" % (wait_menu(hwnd, 1), target))
    return False


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
    PREV[0] = None
    splash = None
    for i in range(24):
        time.sleep(0.30)
        img = T.grab(hwnd, os.path.join(T.OUT, "p00_splash_%02d.png" % i))
        if img is None:
            continue
        r = menu_row(img)
        if r >= 0:
            splash = i
            break
    if splash is None:
        print("FAIL: menu never appeared")
        return 1
    print("menu reached after %.1f s of splash frames" % (0.30 * (splash + 1)))
    PREV[0] = None

    shot(hwnd, "p01_menu", "row %d" % menu_row(T.grab(hwnd, T.OUT + r"\_q.png")))
    # briefing page: row 2
    goto_row(hwnd, 2)
    shot(hwnd, "p02_menu_briefing")
    T.key(hwnd, "NP5")
    time.sleep(0.7)
    shot(hwnd, "p03_briefing")
    T.key(hwnd, "NP5")
    time.sleep(0.5)
    shot(hwnd, "p04_menu_back")
    # army flip: row 1, then 6 -> crimson, 4 -> azure
    goto_row(hwnd, 1)
    T.key(hwnd, "NP6")
    time.sleep(0.5)
    shot(hwnd, "p05_menu_crimson")
    T.key(hwnd, "NP4")
    time.sleep(0.5)
    shot(hwnd, "p06_menu_azure")
    # battle
    if not goto_row(hwnd, 0):
        return 1
    T.key(hwnd, "NP5")
    time.sleep(1.2)
    img = shot(hwnd, "p07_battle")
    if img:
        T.hud_zoom(img, os.path.join(T.OUT, "p07_hud.png"))
    T.key(hwnd, "NP5")           # select CAEDRIC, cursor starts on him
    time.sleep(0.6)
    img = shot(hwnd, "p08_range")
    if img:
        T.hud_zoom(img, os.path.join(T.OUT, "p08_hud.png"))
    T.key(hwnd, "NP2")
    T.key(hwnd, "NP2")
    time.sleep(0.5)
    shot(hwnd, "p09_path")
    T.key(hwnd, "NP5")           # commit the walk
    time.sleep(0.45)
    shot(hwnd, "p10_walking")
    time.sleep(1.4)
    img = shot(hwnd, "p11_card")
    if img:
        T.hud_zoom(img, os.path.join(T.OUT, "p11_hud.png"))
    T.key(hwnd, "NP5")           # ATTACK -> red range ring
    time.sleep(0.6)
    shot(hwnd, "p12_attack_ring")
    T.key(hwnd, "NP5")           # no target in reach: stays on the card
    time.sleep(0.6)
    shot(hwnd, "p13_no_target")
    T.key(hwnd, "NP7")
    time.sleep(0.3)
    T.key(hwnd, "NP7")
    time.sleep(0.5)
    shot(hwnd, "p14_back_to_select")
    # end the player phase, then ride the AI: one tap per round, grab as it moves
    for i in range(26):
        T.key(hwnd, "NP9")
        time.sleep(1.1 if i % 2 == 0 else 0.45)
        if shot(hwnd, "p15_ai_%02d" % i) is None:
            return 1
    print("OK")
    for junk in ("_tmp.png", "_q.png"):
        p = os.path.join(T.OUT, junk)
        if os.path.exists(p):
            os.remove(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
