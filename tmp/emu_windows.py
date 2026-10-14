"""List every window owned by the live VXPEmu pid: a hidden second window or a
disabled screen window explains a frozen PrintWindow capture."""
import ctypes
from ctypes import wintypes
import sys

u = ctypes.windll.user32
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.GetWindowThreadProcessId.restype = wintypes.DWORD

ProcType = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def txt(h):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def info(h):
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (h, cls(h), txt(h), int(u.IsWindowVisible(h)), int(u.IsWindowEnabled(h)),
            (r.left, r.top, r.right, r.bottom))


def main(pid):
    tops = []

    def cb(h, l):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            tops.append(h)
        return True

    u.EnumWindows(ProcType(cb), 0)
    for h in tops:
        print("TOP  ", info(h))
        kids = []

        def kb(h2, l):
            kids.append(h2)
            return True

        u.EnumChildWindows(h, ProcType(kb), 0)
        for k in kids:
            print("  CHILD", info(k))
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
