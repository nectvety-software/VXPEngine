"""Kiểm tra nhanh: _atomic_json_write sống sót khi file đích bị khóa tạm (WinError 5)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import scene_screen_store as store


def main() -> None:
    original_replace = Path.replace
    with tempfile.TemporaryDirectory(prefix="vxp_lock_") as tmp:
        root = Path(tmp)
        registry = root / "assets" / "scenes"

        # 1) Ghi lần đầu + gọi lại với nội dung y hệt → không ghi đè.
        store._atomic_json_write(registry / "screens.dtfe", {"screens": []})
        mtime1 = (registry / "screens.dtfe").stat().st_mtime_ns
        store._atomic_json_write(registry / "screens.dtfe", {"screens": []})
        mtime2 = (registry / "screens.dtfe").stat().st_mtime_ns
        assert mtime1 == mtime2, "nội dung không đổi vẫn ghi lại"
        print("OK  Nội dung không đổi → bỏ qua ghi")

        # 2) replace() dính WinError 5 hai lần → retry backoff thành công.
        calls = {"n": 0}

        def flaky_replace(self, target):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError(13, "Access is denied", str(target))
            return original_replace(self, target)

        Path.replace = flaky_replace
        try:
            store._atomic_json_write(registry / "screens.dtfe", {"screens": ["a"]})
        finally:
            Path.replace = original_replace
        assert calls["n"] == 3, f"phải retry đúng 3 lần, got {calls['n']}"
        assert '"a"' in (registry / "screens.dtfe").read_text(encoding="utf-8")
        assert not (registry / "screens.dtfe.tmp").exists(), "tmp còn sót sau replace thành công"
        print("OK  replace bị khóa 2 lần → retry backoff thành công, tmp sạch")

        # 3) replace() hỏng vĩnh viễn → fallback ghi trực tiếp, nội dung vẫn đúng.
        def broken_replace(self, target):
            raise PermissionError(13, "Access is denied", str(target))

        Path.replace = broken_replace
        try:
            store._atomic_json_write(registry / "screens.dtfe", {"screens": ["b"]})
        finally:
            Path.replace = original_replace
        assert '"b"' in (registry / "screens.dtfe").read_text(encoding="utf-8")
        assert not (registry / "screens.dtfe.tmp").exists(), "tmp còn sót sau fallback"
        print("OK  replace hỏng hẳn → fallback ghi trực tiếp, tmp được dọn")

        # 4) ScreenStore.ensure() qua khóa tạm → không crash, registry đọc được.
        calls2 = {"n": 0}

        def flaky_once(self, target):
            calls2["n"] += 1
            if calls2["n"] <= 1:
                raise PermissionError(13, "Access is denied", str(target))
            return original_replace(self, target)

        Path.replace = flaky_once
        try:
            payload = store.ScreenStore(root).ensure()
        finally:
            Path.replace = original_replace
        assert any(s["id"] == "main" for s in payload["screens"])
        print("OK  ScreenStore.ensure() sống sót qua khóa tạm")

    print("PASS_ALL: _atomic_json_write chống khóa file Windows")


if __name__ == "__main__":
    main()
