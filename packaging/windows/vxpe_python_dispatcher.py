"""Restricted Python host for the three bundled VXPEngine SDK scripts."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


ALLOWED_SCRIPTS = {"vxp_pack.py", "vxp_resource.py", "vxp_signer.py"}


def main() -> int:
    if len(sys.argv) < 2:
        print("VXPEngine SDK tool host: missing script", file=sys.stderr)
        return 2
    script = Path(sys.argv[1]).expanduser().resolve()
    if script.name not in ALLOWED_SCRIPTS or script.parent.name != "tools" or script.parent.parent.name != "coremre":
        print(f"VXPEngine SDK tool host: script is not allowed: {script}", file=sys.stderr)
        return 3
    if not script.is_file():
        print(f"VXPEngine SDK tool host: script does not exist: {script}", file=sys.stderr)
        return 4
    sys.argv = [str(script), *sys.argv[2:]]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
