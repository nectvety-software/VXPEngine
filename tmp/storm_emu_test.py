"""StormArena25D live emulator test: launch VXPEmu screen-only, drive keys,
grab the device screen via DPI-aware PrintWindow, and analyse motion + the
in-app frame-time probe bar. ASCII output only (cp1252 console)."""
import ctypes
import subprocess
import sys
import time

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    user32.SetProcessDPIAware()

EMU = r"D:\MRE\VXPEmu\build\Release\VXPEmu.exe"
VXP = r"D:\MRE\VXPEngine\examples\StormArena25D\build-arm\main\storm_arena_25d.vxp"
OUT = r"D:\MRE\VXPEngine\tmp\storm_emu"
TITLE = "VXPEmu Screen"

WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK = {"LEFT": (0x25, 0x4B, True), "RIGHT": (0x27, 0x4D, True),
      "UP": (0x26, 0x48, True), "DOWN": (0x28, 0x50, True),
      "NP5": (0x35, 0x06, False), "NP7": (0x37, 0x08, False),
      "NP8": (0x38, 0x09, False)}


def find_window():
    return user32.FindWindowW(None, TITLE)


def grab(hwnd, path):
    class RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                    ("r", ctypes.c_long), ("b", ctypes.c_long)]
    rc = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    w, h = rc.r - rc.l, rc.b - rc.t
    if w <= 0 or h <= 0:
        return None
    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bmp)
    user32.PrintWindow(hwnd, mem_dc, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long), ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32), ("bxpp", ctypes.c_long),
                    ("bypp", ctypes.c_long), ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32)]
    hdr = BITMAPINFOHEADER()
    hdr.biSize = ctypes.sizeof(hdr)
    hdr.biWidth, hdr.biHeight, hdr.biPlanes = w, -h, 1
    hdr.biBitCount, hdr.biCompression = 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(hdr), 0)
    img = Image.frombytes("RGBA", (w, h), buf, "raw", "BGRA")
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)
    dev = img.convert("RGB").resize((240, 320), Image.NEAREST)
    dev.save(path)
    full = img.convert("RGB")
    full.save(path.replace(".png", "_full.png"))
    return dev


def key(hwnd, name, hold=0.06):
    vk, sc, ext = VK[name]
    lp = 1 | (sc << 16) | (0x40000000 if ext else 0)
    up = lp | 0xC0000000
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, ctypes.c_uint(lp).value)
    time.sleep(hold)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, ctypes.c_uint(up & 0xFFFFFFFF).value)
    time.sleep(0.02)


def diff(a, b):
    pa, pb = a.load(), b.load()
    n = 0
    for y in range(0, 320, 2):
        for x in range(0, 240, 2):
            if pa[x, y] != pb[x, y]:
                n += 1
    return n


def probe_ms(img):
    """Frame-time bar: bg (16,18,24) at logical y 308..315, run starts x=6."""
    px = img.load()
    row = 312
    run = 0
    for x in range(6, 70):
        r, g, b = px[x, row]
        if abs(r - 16) < 12 and abs(g - 18) < 12 and abs(b - 24) < 12:
            break
        if r > 200 and g > 200 and b > 200:
            break
        run += 1
    return run


def main():
    import os
    os.makedirs(OUT, exist_ok=True)
    # VXPEmu is single-instance: a live process would keep serving its already
    # loaded module and the whole run would silently test a stale build.
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
    print("vxp mtime:", time.strftime("%H:%M:%S",
                                      time.localtime(os.path.getmtime(VXP))))
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
    print("window ready after poll")
    # The app boots into a splash card and then the menu, so the fight HUD only
    # appears once a key skips the card and OK picks row 0 (FIGHT A CPU). If the
    # card has already auto-advanced the first press simply starts the match and
    # the second lands a punch - both end in the fight screen this test needs.
    time.sleep(1.0)
    key(hwnd, "NP5")
    time.sleep(0.5)
    key(hwnd, "NP5")
    # The shell shows an "Import VXP" launcher panel until the app finishes
    # booting; wait until the in-app HUD (probe-bar white label at 4,312) shows.
    ready = None
    for i in range(60):
        time.sleep(0.5)
        img = grab(hwnd, OUT + r"\boot.png")
        if img is None:
            continue
        r, g, b = img.load()[4, 312]
        if r > 200 and g > 200 and b > 200:
            ready = i
            break
    if ready is None:
        print("FAIL: HUD probe label never appeared (app still on launcher panel?)")
    else:
        print("app booted after %.1f s" % (0.5 * (ready + 1)))
    shots = {}
    shots["t0"] = grab(hwnd, OUT + r"\t0.png")
    if shots["t0"] is None:
        print("FAIL: client rect empty (window not ready)")
        return 1
    print("probe ms t0:", probe_ms(shots["t0"]))
    time.sleep(1.0)
    shots["t1"] = grab(hwnd, OUT + r"\t1.png")
    print("motion idle t0->t1 changed-samples:", diff(shots["t0"], shots["t1"]))
    print("probe ms t1:", probe_ms(shots["t1"]))
    # accelerate: 6 UP taps
    for _ in range(6):
        key(hwnd, "UP")
    time.sleep(0.6)
    shots["fast"] = grab(hwnd, OUT + r"\fast.png")
    print("after throttle changed-samples t1->fast:", diff(shots["t1"], shots["fast"]))
    # attack: 8 punch taps + 4 kick taps
    for _ in range(8):
        key(hwnd, "NP5")
    for _ in range(4):
        key(hwnd, "NP7")
    time.sleep(0.6)
    shots["fight"] = grab(hwnd, OUT + chr(92) + "fight.png")
    print("after attacks changed-samples fast->fight:", diff(shots["fast"], shots["fight"]))
    # build the super gauge with more landed hits, then fire NP8 (super)
    for _ in range(18):
        key(hwnd, "NP5", 0.05)
        time.sleep(0.22)
    # tight burst of grabs: one lands during the punch active frames
    for nm in ("s0", "s1", "s2", "s3", "s4", "s5"):
        key(hwnd, "NP5", 0.05)
        time.sleep(0.14)
        shots[nm] = grab(hwnd, OUT + "\\" + nm + ".png")
    for _ in range(3):
        key(hwnd, "NP8", 0.05)
    time.sleep(0.15)
    shots["super"] = grab(hwnd, OUT + r"\super.png")
    print("after super changed-samples s5->super:",
          diff(shots["s5"], shots["super"]))
    # steer right 10 taps then left 10 taps
    for _ in range(10):
        key(hwnd, "RIGHT")
    time.sleep(0.6)
    shots["right"] = grab(hwnd, OUT + r"\right.png")
    print("after right changed-samples fight->right:", diff(shots["fight"], shots["right"]))
    for _ in range(10):
        key(hwnd, "LEFT")
    time.sleep(0.6)
    shots["left"] = grab(hwnd, OUT + r"\left.png")
    print("after left changed-samples right->left:", diff(shots["right"], shots["left"]))
    for name in ("t0", "t1", "fast", "fight", "s0", "s1", "s2", "s3", "s4",
                 "s5", "super", "right", "left"):
        print("probe ms %s: %d" % (name, probe_ms(shots[name])))
    time.sleep(2.0)
    shots["late"] = grab(hwnd, OUT + r"\late.png")
    print("probe ms late: %d" % probe_ms(shots["late"]))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
