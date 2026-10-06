#!/usr/bin/env python3
"""Entry point: python main.py [--sheet tilemaps.png] [--theme light] [--selftest]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.app import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run())
