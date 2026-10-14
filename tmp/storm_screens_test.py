"""StormArena25D splash/menu emulator run: boot the ARM build in VXPEmu and walk
the whole front end - splash card, auto-advance to the menu, P1 side toggle,
help page, a real match, Clear back out, and any-key splash skip - capturing
each screen.

Navigation is state-driven rather than time-driven. VXPEmu needs ~3 s to create
its window, the splash card lives 2.6 s, and the shell hides the app until
VM_MSG_CREATE fires, so fixed sleeps mis-timed the first two runs. Every step
here polls the grabbed pixels until the screen it expects is on the device, and
the window hunt spins at 20 ms so the splash is caught before it expires.
ASCII output only (cp1252 console)."""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storm_emu_test as E

OUT = r"D:\MRE\VXPEngine\tmp\storm_screens"
E.VK["BACK"] = (0x08, 0x0E, False)      # handset Clear key
E.VK["ESC"] = (0x1B, 0x01, False)

ROW_Y0, ROW_STEP, ROW_N = 186, 22, 5


def gold(px, x, y):
    r, g, b = px[x, y]
    return r > 170 and 120 < g < 210 and b < 110


def gold_count(img, x0, y0, x1, y1):
    px = img.load()
    n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if gold(px, x, y):
                n += 1
    return n


def is_splash(img):
    """The logo block is the only large bright-gold area above the menu card.
    Keyed on a count rather than single pixels: VXPEmu's client area here is
    300x400, so the grab is downsampled 1.25:1 and a 1-px rule can vanish."""
    return gold_count(img, 60, 78, 180, 106) > 20


def cursor_row(img):
    """Row index of the gold selection bar, or -1 when no menu is on screen."""
    px = img.load()
    for i in range(ROW_N):
        if gold(px, 27, ROW_Y0 + i * ROW_STEP + 10):
            return i
    return -1


def is_fight(img):
    """The fight HUD's frame-time probe bar starts with a white tick at 4,312."""
    r, g, b = img.load()[4, 312]
    return r > 200 and g > 200 and b > 200


def bar_px(img):
    """Width of the teal loading fill on the splash. The scan starts past the
    2-px gold bar head (x 40..42) so the head is not read as fill."""
    px = img.load()
    n = 0
    for x in range(43, 199):
        r, g, b = px[x, 216]
        if g > 120 and r < 160 and b > 110:
            n += 1
        else:
            break
    return n


def hint_px(img):
    """Bright pixels in the 'PRESS ANY KEY' band (y 262..278)."""
    px = img.load()
    n = 0
    for y in range(262, 278):
        for x in range(240):
            r, g, b = px[x, y]
            if r > 170 and g > 170 and b > 170:
                n += 1
    return n


def wait_for(hwnd, pred, limit, shots=None, tag=None):
    """Poll the device until `pred` holds; returns the matching grab or None."""
    deadline = time.time() + limit
    while time.time() < deadline:
        img = E.grab(hwnd, OUT + "\\" + (tag or "_scan") + ".png")
        if img is not None and pred(img):
            if tag and shots is not None:
                shots[tag] = img
            return img
        time.sleep(0.05)
    return None


def go_row(hwnd, target):
    """Walk the cursor down (it wraps) until the wanted row is highlighted."""
    for _ in range(ROW_N + 1):
        img = E.grab(hwnd, OUT + r"\_scan.png")
        if img is not None and cursor_row(img) == target:
            return img
        E.key(hwnd, "DOWN")
        time.sleep(0.25)
    return None


def boot():
    """Kill any live emulator (it is single-instance and keeps its module),
    relaunch, and spin until the window exists. Returns (hwnd, t_open)."""
    subprocess.call(["taskkill", "/IM", "VXPEmu.exe", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.25)
        if not E.find_window():
            break
    else:
        print("FAIL: emulator window survived the kill")
        return 0, 0.0
    time.sleep(1.5)
    t0 = time.time()
    subprocess.Popen([E.EMU, E.VXP, "--screen-only", "--autostart"])
    while time.time() - t0 < 15.0:
        hwnd = E.find_window()
        if hwnd:
            return hwnd, time.time() - t0
        time.sleep(0.02)
    print("FAIL: window not found")
    return 0, 0.0


def leave_to(hwnd, pred, name_a, name_b):
    """Press a candidate key, then the fallback, until `pred` holds."""
    for name in (name_a, name_b):
        E.key(hwnd, name)
        img = wait_for(hwnd, pred, 3.0)
        if img is not None:
            print("left via:", name)
            return img
    print("FAIL: neither %s nor %s moved the screen" % (name_a, name_b))
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    print("vxp mtime:", time.strftime("%H:%M:%S",
                                      time.localtime(os.path.getmtime(E.VXP))))
    shots = {}

    hwnd, opened = boot()
    if not hwnd:
        return 1
    print("window after %.2f s" % opened)
    img = wait_for(hwnd, is_splash, 12.0, shots, "splash_1")
    if img is None:
        print("FAIL: splash card never appeared")
        return 1
    t_splash = time.time()
    print("splash caught at +%.2f s, loading fill %d px" % (opened, bar_px(img)))
    time.sleep(1.0)
    shots["splash_2"] = E.grab(hwnd, OUT + r"\splash_2.png")
    if shots["splash_2"] is None or not is_splash(shots["splash_2"]):
        print("FAIL: splash expired early")
        return 1
    print("splash fill after 1 s: %d px   bar moved, changed-samples: %d"
          % (bar_px(shots["splash_2"]),
             E.diff(shots["splash_1"], shots["splash_2"])))
    img = wait_for(hwnd, lambda i: cursor_row(i) >= 0, 8.0, shots, "menu_auto")
    if img is None:
        print("FAIL: menu did not appear after the splash")
        return 1
    print("auto-advance %.2f s after the splash was first seen, cursor row %d"
          % (time.time() - t_splash, cursor_row(img)))
    time.sleep(0.9)
    shots["menu_idle"] = E.grab(hwnd, OUT + r"\menu_idle.png")
    print("menu idle diff (fighters breathing):",
          E.diff(shots["menu_auto"], shots["menu_idle"]))

    img = go_row(hwnd, 2)
    if img is None:
        print("FAIL: cannot reach the P1 SIDE row")
        return 1
    shots["menu_side_row"] = E.grab(hwnd, OUT + r"\menu_side_row.png")
    E.key(hwnd, "RIGHT")
    time.sleep(0.5)
    shots["menu_side_kuro"] = E.grab(hwnd, OUT + r"\menu_side_kuro.png")
    print("side toggle diff:",
          E.diff(shots["menu_side_row"], shots["menu_side_kuro"]))

    go_row(hwnd, 3)
    E.key(hwnd, "NP5")
    img = wait_for(hwnd, lambda i: not is_splash(i) and cursor_row(i) < 0,
                   6.0, shots, "help")
    if img is None:
        print("FAIL: help page did not open")
        return 1
    print("menu->help diff:", E.diff(shots["menu_side_kuro"], shots["help"]))
    if leave_to(hwnd, lambda i: cursor_row(i) >= 0, "BACK", "ESC") is None:
        return 1
    shots["menu_back"] = E.grab(hwnd, OUT + r"\menu_back.png")

    img = go_row(hwnd, 0)
    if img is None:
        print("FAIL: cannot reach the FIGHT row")
        return 1
    E.key(hwnd, "NP5")
    img = wait_for(hwnd, is_fight, 8.0, shots, "fight_1s")
    if img is None:
        print("FAIL: match did not start")
        return 1
    print("menu->fight diff:", E.diff(shots["menu_back"], shots["fight_1s"]))
    for _ in range(6):
        E.key(hwnd, "NP5", 0.05)
        time.sleep(0.2)
    shots["fight_punch"] = E.grab(hwnd, OUT + r"\fight_punch.png")
    time.sleep(4.0)
    shots["fight_late"] = E.grab(hwnd, OUT + r"\fight_late.png")
    img = leave_to(hwnd, lambda i: cursor_row(i) >= 0, "BACK", "ESC")
    if img is not None:
        shots["menu_from_fight"] = E.grab(hwnd, OUT + r"\menu_from_fight.png")
        print("fight->menu diff:",
              E.diff(shots["fight_late"], shots["menu_from_fight"]))
    for tag in ("fight_1s", "fight_punch", "fight_late"):
        print("probe ms %-14s %3d" % (tag, E.probe_ms(shots[tag])))

    # Any-key skip: relaunch and tap OK while the splash card is still up.
    hwnd, opened = boot()
    if not hwnd:
        return 1
    img = wait_for(hwnd, is_splash, 12.0, shots, "splash_skip_before")
    if img is None:
        print("FAIL: second splash never appeared")
        return 1
    E.key(hwnd, "NP5")
    img = wait_for(hwnd, lambda i: cursor_row(i) >= 0, 3.0, shots, "menu_skipped")
    if img is None:
        print("FAIL: any-key did not skip the splash")
        return 1
    print("splash skipped by one key press")

    # Blink duty cycle: the hint is drawn on 16 of every 32 sim steps, so
    # sample the band it occupies across a whole splash.
    hwnd, opened = boot()
    if not hwnd:
        return 1
    img = wait_for(hwnd, is_splash, 12.0)
    if img is None:
        print("FAIL: third splash never appeared")
        return 1
    counts, t0 = [], time.time()
    while time.time() - t0 < 3.0 and is_splash(img):
        c = hint_px(img)
        counts.append(c)
        if c and not os.path.exists(OUT + r"\splash_hint_on.png"):
            img.save(OUT + r"\splash_hint_on.png")
        time.sleep(0.12)
        img = wait_for(hwnd, lambda i: True, 1.0)
    on = sum(1 for c in counts if c > 0)
    print("blink samples %d, hint visible in %d, %d bright px when on"
          % (len(counts), on, max(counts) if counts else 0))

    # VXPEmu's screen-only window has no mouse/touch->pen path (no WM_*/pen
    # handling anywhere in its src/), so the pen rows are covered by the host
    # offscreen driver instead: tmp/storm_shots.c feeds handle_penevt directly.
    print("NOTE: pen taps verified on the host harness, not on device")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
