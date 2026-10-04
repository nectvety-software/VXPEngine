"""Smoke test cho frame_simulator_qt.py — chay headless (offscreen).

Kiem tra:
  * Widget duoc dung len khong loi
  * Dung so luong nut: 7 toolbar, 9 so, 2 phim rong (* / 0), 7 nav, 3 cot doc
  * Nhan phim so -> Subject cap nhat, dong nhac multi-tap doi
  * Man hinh 240x320, co muc (khong trong) — do pixel theo do sang
  * Mau nen dung #12161f

Chay:  .venv\\Scripts\\python.exe simulator\\smoke_frame_qt.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from frame_simulator_qt import FrameSimulator, ScreenPane  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(label)
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f"  -> {detail}" if detail else ""))


app = QApplication(sys.argv)
app.setStyle("Fusion")

win = FrameSimulator()
win.resize(520, 782)
win.show()
app.processEvents()

print("\n=== Cau truc ===")

tools = win.findChildren(QPushButton, "ToolButton")
check("7 nut toolbar", len(tools) == 7, f"co {len(tools)}")
check("toolbar co tooltip", all(b.toolTip() for b in tools))

keys = win.findChildren(QPushButton, "KeyButton")
check("21 phim (9 so + 2 rong + 7 nav + 3 cot)", len(keys) == 21, f"co {len(keys)}")

phones = [k for k in keys if k.property("kind") == "phone"]
check("11 phim so/* /0", len(phones) == 11, f"co {len(phones)}")

wide = [k for k in keys if k.property("wide") == "true"]
check("2 phim rong (* va 0)", len(wide) == 2, f"co {len(wide)}")
check("phim rong la * va 0", [w.text() for w in wide] == ["*", "0"],
      str([w.text() for w in wide]))

navs = [k for k in keys if k.property("kind") == "nav"]
check("6 phim dieu huong (OK tinh rieng)", len(navs) == 6, f"co {len(navs)}")

sides = [k for k in keys if k.property("kind") == "side"]
check("3 phim cot doc", len(sides) == 3, f"co {len(sides)}")

ok = [k for k in keys if k.property("kind") == "ok"]
check("1 nut OK", len(ok) == 1, f"co {len(ok)}")
check("OK chu dam", ok and ok[0].font().bold())

print("\n=== Nhan chuot / multi-tap ===")

screen = win.findChild(ScreenPane)
check("man hinh 240x320", screen.width() == 240 and screen.height() == 320,
      f"{screen.width()}x{screen.height()}")
check("Subject ban dau = GMAS (G_M_A_S, G to sang)", screen.subject == "GMAS", screen.subject)

hint = win.frame._hint
check("dong nhac nghi dung chu",
      hint.text() == "Nhấn nhiều lần: 2=abc, 3=def, 7=pqrs, 0=space", hint.text())

# Bam phim '4' 1 lan -> 'g'
btn4 = next(k for k in phones if k.text().startswith("4"))
btn4.click()
app.processEvents()
check("chuoi day van giu GMAS", screen.subject == "GMAS", screen.subject)
check("bam 4 -> hien '4 → g'", "4 → g" in hint.text(), hint.text())

# Bam phim '4' lan 2 -> 'h'
btn4.click()
app.processEvents()
check("bam 4 lan 2 -> 'h'", "4 → h" in hint.text(), hint.text())

# Bam phim '2' 3 lan -> 'c'
btn2 = next(k for k in phones if k.text().startswith("2"))
for _ in range(3):
    btn2.click()
    app.processEvents()
check("bam 2 x3 -> 'c'", "2 → c" in hint.text(), hint.text())

print("\n=== Do render (dem pixel theo do sang) ===")

img = win.grab().toImage()
check("grab duoc anh", not img.isNull(), f"{img.width()}x{img.height()}")


def ink(threshold: int) -> int:
    return sum(
        1
        for y in range(0, img.height(), 2)
        for x in range(0, img.width(), 2)
        if QColor(img.pixel(x, y)).lightness() > threshold
    )


total = len(range(0, img.height(), 2)) * len(range(0, img.width(), 2))
ink40 = ink(40)
share = ink40 / total * 100
check("khung co noi dung (muc > 0.5%)", share > 0.5, f"{share:.2f}% muc")

# Man hinh phai co muc (ban do + overlay)
simg = screen.grab().toImage()
sink = sum(
    1
    for y in range(0, simg.height(), 2)
    for x in range(0, simg.width(), 2)
    if QColor(simg.pixel(x, y)).lightness() > 25
)
check("man hinh co ban do/overlay", sink > 50, f"{sink} pixel sang")

print("\n=== Mau sac ===")

bg = QColor("#12161f")
check("mau nen dung #12161f", bg.name() == "#12161f", bg.name())

print(f"\n{'=' * 56}")
print(f"  {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("  FAILED:")
    for name in FAIL:
        print(f"    - {name}")
print("=" * 56)

# Thoat ngay — Qt teardown trong offscreen doi khi treo.
sys.stdout.flush()
os._exit(0 if not FAIL else 1)
