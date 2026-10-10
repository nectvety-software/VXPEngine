import os, subprocess, sys, time, ctypes, ctypes.wintypes as wt
from pathlib import Path
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt
sys.path.insert(0, str(Path(r'D:\MRE\VXPEngine\app')))
import native_window
exe = Path(r'D:\MRE\VXPEmu\build\Release\VXPEmu.exe')
vxp = Path(r'D:\MRE\VXPEngine\examples\FoxRiftDemo\build-arm\main\vaelora_duel.vxp')
app = QApplication([])
host = QWidget(); host.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True); host.resize(240, 320); host.show(); app.processEvents()
proc = subprocess.Popen([str(exe), str(vxp), '--autostart', '--testapi', '--screen-only'], cwd=str(exe.parent))
try:
    hwnd = None
    deadline = time.time() + 20
    while time.time() < deadline:
        app.processEvents()
        hwnd = native_window.find_main_window(proc.pid)
        if hwnd: break
        time.sleep(.1)
    if not hwnd: raise RuntimeError('No VXPEmu screen-only window')
    ok = native_window.embed(hwnd, int(host.winId()), 240, 320)
    if not ok: raise RuntimeError('Failed to embed screen window')
    native_window.fit(hwnd, 240, 320, int(host.winId()))
    time.sleep(4); app.processEvents()
    rect = wt.RECT(); ctypes.windll.user32.GetClientRect(int(host.winId()), ctypes.byref(rect))
    print(f'embedded={ok} pid={proc.pid} hwnd=0x{hwnd:X} host_client={rect.right}x{rect.bottom} title=VXPEmu Screen')
finally:
    proc.terminate()
    try: proc.wait(timeout=3)
    except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=3)
    host.close()
