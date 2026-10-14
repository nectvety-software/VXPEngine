"""TacticsVanguard2D device pass 4: ride the enemy AI to a battle result.

Pass 3 proved splash, briefing, army flip, field, range hatch, path arrow and
the action card render live, but its NP7 presses fell out of the battle back to
the menu (back_out on BP_SELECT returns to the menu), so the AI phase, the
cut-in band and the result screen were never seen on hardware. This run ends
the player phase with 9 and then just keeps tapping 9: it is a no-op while the
AI moves, and it skips our own phase whenever control comes back, so the battle
plays itself to VICTORY or DEFEAT without any OK press that could restart it.

Same PrintWindow capture path as the earlier passes. ASCII output only.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tactics_emu_test as T
import tactics_emu_tour as U

PREV = [None]


def shot(hwnd, name):
    img = T.grab(hwnd, os.path.join(T.OUT, name + ".png"))
    if img is None:
        print("FAIL: empty client rect at %s" % name)
        return None
    motion = 0 if PREV[0] is None else T.diff(PREV[0], img)
    PREV[0] = img
    print("%-16s motion %5d px" % (name, motion))
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
    U.PREV[0] = None
    for i in range(40):
        time.sleep(0.30)
        img = T.grab(hwnd, os.path.join(T.OUT, "a99_tmp.png"))
        if img is not None and U.menu_row(img) >= 0:
            break
    else:
        print("FAIL: menu never appeared")
        return 1
    os.remove(os.path.join(T.OUT, "a99_tmp.png"))
    print("menu after %.1f s" % (0.30 * (i + 1)))
    PREV[0] = None
    if not U.goto_row(hwnd, 0):
        print("FAIL: cannot reach BEGIN BATTLE")
        return 1
    T.key(hwnd, "NP5")
    time.sleep(1.2)
    img = shot(hwnd, "a00_battle")
    if img is None:
        return 1
    T.hud_zoom(img, os.path.join(T.OUT, "a00_hud.png"))
    T.key(hwnd, "NP5")          # select CAEDRIC under the cursor
    time.sleep(0.6)
    shot(hwnd, "a01_range")
    T.key(hwnd, "NP9")          # end the player phase
    time.sleep(1.0)
    for i in range(90):
        T.key(hwnd, "NP9")
        time.sleep(1.05)
        img = shot(hwnd, "a02_ai_%02d" % i)
        if img is None:
            return 1
        if i in (3, 15, 30, 45, 60, 75, 89):
            T.hud_zoom(img, os.path.join(T.OUT, "a02_hud_%02d.png" % i))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
