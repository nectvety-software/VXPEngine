"""Small Win32 bridge used to embed and control the VXPEmu window."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

user32 = ctypes.WinDLL("user32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.GetWindowLongW.argtypes = (wt.HWND, ctypes.c_int)
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = (wt.HWND, ctypes.c_int, ctypes.c_long)
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetParent.argtypes = (wt.HWND, wt.HWND)
user32.SetParent.restype = wt.HWND
user32.MoveWindow.argtypes = (wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.BOOL)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.GetClientRect.argtypes = (wt.HWND, ctypes.POINTER(wt.RECT))
user32.GetClientRect.restype = wt.BOOL

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_EX_TOOLWINDOW = 0x00000080
WM_KEYDOWN, WM_KEYUP, WM_CLOSE = 0x0100, 0x0101, 0x0010

MRE_KEY_UP, MRE_KEY_DOWN, MRE_KEY_LEFT, MRE_KEY_RIGHT = 0x100, 0x101, 0x102, 0x103
MRE_KEY_OK, MRE_KEY_LEFT_SOFT, MRE_KEY_RIGHT_SOFT = 0x104, 0x105, 0x106
MRE_KEY_BACK, MRE_KEY_CLEAR = 0x107, 0x108

_MRE_TO_VK = {
    **{0x30 + n: 0x30 + n for n in range(10)},
    0x2A: 0x6A, 0x23: 0x33,
    MRE_KEY_UP: 0x26, MRE_KEY_DOWN: 0x28, MRE_KEY_LEFT: 0x25,
    MRE_KEY_RIGHT: 0x27, MRE_KEY_OK: 0x0D, MRE_KEY_LEFT_SOFT: 0xBF,
    MRE_KEY_RIGHT_SOFT: 0x10, MRE_KEY_BACK: 0x1B, MRE_KEY_CLEAR: 0x08,
}


def _window_long(hwnd: int, index: int) -> int:
    return user32.GetWindowLongW(hwnd, index) & 0xFFFFFFFF


def _set_window_long(hwnd: int, index: int, value: int) -> None:
    signed = value - 0x100000000 if value >= 0x80000000 else value
    user32.SetWindowLongW(hwnd, index, signed)


def find_main_window(pid: int) -> int | None:
    result: list[int] = []

    @WNDENUMPROC
    def callback(hwnd, _lparam):
        process_id = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        if _window_long(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            result.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(callback, 0)
    return result[0] if result else None


def embed(hwnd: int, host: int, width: int, height: int) -> bool:
    try:
        style = _window_long(hwnd, GWL_STYLE)
        style = (style | WS_CHILD) & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME |
                                      WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
        _set_window_long(hwnd, GWL_STYLE, style)
        user32.SetParent(hwnd, host)
        width, height = client_size(host, width, height)
        user32.MoveWindow(hwnd, 0, 0, width, height, True)
        user32.ShowWindow(hwnd, 5)
        return True
    except OSError:
        return False


def client_size(host: int, fallback_width: int, fallback_height: int) -> tuple[int, int]:
    """Return the host's real Win32 pixel size (Qt coordinates may be DPI-scaled)."""
    rect = wt.RECT()
    if host and user32.GetClientRect(host, ctypes.byref(rect)):
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width > 0 and height > 0:
            return width, height
    return int(fallback_width), int(fallback_height)


def fit(hwnd: int, width: int, height: int, host: int = 0) -> None:
    if hwnd:
        width, height = client_size(host, width, height)
        user32.MoveWindow(hwnd, 0, 0, width, height, True)


def send_key(hwnd: int, mre_code: int) -> None:
    vk = _MRE_TO_VK.get(mre_code)
    if not hwnd or vk is None:
        return
    def post(key: int, down: bool) -> None:
        scan = user32.MapVirtualKeyW(key, 0)
        flags = (scan << 16) | 1
        if not down:
            flags |= (1 << 30) | (1 << 31)
        user32.PostMessageW(hwnd, WM_KEYDOWN if down else WM_KEYUP, key, flags & 0xFFFFFFFF)

    # Qt nhận dấu # dưới dạng Shift+3 trên bàn phím Windows.
    if mre_code == 0x23:
        post(0x10, True)
    post(vk, True)
    post(vk, False)
    if mre_code == 0x23:
        post(0x10, False)


def close(hwnd: int) -> None:
    if hwnd:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
