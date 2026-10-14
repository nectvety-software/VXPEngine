"""TacticsVanguard2D live emulator run: launch VXPEmu screen-only, drive the
splash -> menu -> briefing -> battle -> enemy phase -> result flow with real
key messages, and grab the device screen through DPI-aware PrintWindow.

Every grab is 240x320 (the handset resolution), so the frames are comparable
with the host harness dumps. Motion is checked by sampling pixel differences
between grabs, and the HUD's own MS readout is cropped 6x so the frame time can
be read off the image instead of guessed. ASCII output only (cp1252 console).
"""
import ctypes
import os
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
if not os.path.exists(EMU):
    EMU = r"D:\MRE\VXPEmu\deploy\VXPEmu.exe"
VXP = (r"D:\MRE\VXPEngine\examples\TacticsVanguard2D"
       r"\build-arm\main\tactics_vanguard_2d.vxp")
OUT = r"D:\MRE\VXPEngine\tmp\tactics_emu"
TITLE = "VXPEmu Screen"

WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK = {"LEFT": (0x25, 0x4B, True), "RIGHT": (0x27, 0x4D, True),
      "UP": (0x26, 0x48, True), "DOWN": (0x28, 0x50, True),
      "NP2": (0x32, 0x03, False), "NP4": (0x34, 0x05, False),
      "NP5": (0x35, 0x06, False), "NP6": (0x36, 0x07, False),
      "NP7": (0x37, 0x08, False), "NP8": (0x38, 0x09, False),
      "NP9": (0x39, 0x0A, False)}


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


def hud_zoom(img, path):
    """The battle HUD prints its own last frame time at x=212,y=8 as 'MS n';
    crop the top strip 6x so the digits are legible in the contact sheet."""
    img.crop((150, 2, 240, 22)).resize((540, 120), Image.NEAREST).save(path)


def main():
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
    time.sleep(1.0)
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
    shots = {}

    def shot(name, note=""):
        img = grab(hwnd, os.path.join(OUT, name + ".png"))
        if img is None:
            print("FAIL: empty client rect at %s" % name)
            return None
        shots[name] = img
        prev = "motion %s: %d px" % (name, diff(shots.get("_prev", img), img)) \
            if "_prev" in shots else ""
        shots["_prev"] = img
        print("%-14s %s %s" % (name, note, prev))
        return img

    time.sleep(3.0)
    shot("00_splash")
    time.sleep(1.2)
    shot("01_splash_bar")
    # Any key skips the splash; the menu's row 0 is BEGIN BATTLE.
    key(hwnd, "NP5")
    time.sleep(0.5)
    shot("02_menu")
    # Down twice to BRIEFING, confirm, then back out with any key.
    key(hwnd, "NP8")
    key(hwnd, "NP8")
    time.sleep(0.3)
    shot("03_menu_briefing")
    key(hwnd, "NP5")
    time.sleep(0.5)
    shot("04_briefing")
    key(hwnd, "NP5")
    time.sleep(0.5)
    shot("05_menu_back")
    key(hwnd, "NP5")
    time.sleep(0.8)
    shot("06_battle")
    hud_zoom(shots["06_battle"], os.path.join(OUT, "06_hud.png"))
    # Select the unit under the cursor (CAEDRIC) and aim five tiles north.
    key(hwnd, "NP5")
    time.sleep(0.4)
    shot("07_range")
    for _ in range(5):
        key(hwnd, "NP2")
    time.sleep(0.4)
    shot("08_path")
    key(hwnd, "NP5")
    time.sleep(1.4)
    shot("09_card")
    hud_zoom(shots["09_card"], os.path.join(OUT, "09_hud.png"))
    key(hwnd, "NP5")
    time.sleep(0.6)
    shot("10_after_card")
    # End the player phase and watch the AI cross the bridges.
    key(hwnd, "NP9")
    time.sleep(3.0)
    shot("11_enemy_mid")
    time.sleep(4.0)
    shot("12_enemy_late")
    time.sleep(4.0)
    shot("13_round2")
    # Round 2: the vanguard holds the bridge, so its own tile can open the card
    # and one of the four neighbours is the attacker that reached it.
    key(hwnd, "NP5")
    time.sleep(0.4)
    shot("14_r2_range")
    key(hwnd, "NP5")
    time.sleep(0.4)
    shot("15_r2_card")
    key(hwnd, "NP5")
    time.sleep(0.4)
    shot("16_r2_target")
    key(hwnd, "NP2")
    key(hwnd, "NP5")
    time.sleep(0.9)
    shot("17_r2_cutin")
    time.sleep(1.2)
    shot("18_r2_hit")
    # Let the field play itself out: end each player phase and keep grabbing.
    for i in range(9):
        key(hwnd, "NP9")
        time.sleep(5.0)
        shot("19_auto%d" % i)
    time.sleep(1.0)
    print("grabs:", len([k for k in shots if k != "_prev"]))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
