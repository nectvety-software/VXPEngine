#!/usr/bin/env python3
"""Build an MRE ``.res`` archive without external SDK executables."""
from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path

EMPTY_APP_LOGO = (
    b"VREAPPLOGO09BVREPNG" + struct.pack("<III", 8, 256, 0)
)
MRE2_EMPTY = b"\xff\xff\xff\xff\x00\x00\x00\x00"


@dataclass
class Resource:
    name: str
    data: bytes
    offset_slot: int = 0


def build_resource(output: Path, files: list[Path], empty_logo: bool = False) -> None:
    resources: list[Resource] = []
    if empty_logo:
        resources.append(Resource("Applogo.img", EMPTY_APP_LOGO))
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
        resources.append(Resource(path.name, path.read_bytes()))
    resources.append(Resource("mre-2.0", MRE2_EMPTY))

    result = bytearray()
    for item in resources:
        result.extend(item.name.encode("utf-8") + b"\0")
        item.offset_slot = len(result)
        result.extend(struct.pack("<II", 0, len(item.data)))
    result.append(0)
    mre2_slot = len(result)
    result.extend(b"\0" * 8)

    offsets: list[int] = []
    for item in resources:
        offset = len(result)
        offsets.append(offset)
        result.extend(item.data)
        struct.pack_into("<I", result, item.offset_slot, offset)
    struct.pack_into("<I", result, mre2_slot, offsets[-1])
    # The MRE 2.0 tail stores the resource count in its last word.
    struct.pack_into("<I", result, len(result) - 4, len(resources))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    print(f"RESOURCE  : {len(resources)} entries")
    print(f"OUTPUT    : {output.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", required=True, type=Path)
    parser.add_argument("-f", "--files", nargs="*", default=[], type=Path)
    parser.add_argument("-e", "--empty-logo", action="store_true")
    args = parser.parse_args()
    build_resource(args.out, args.files, args.empty_logo)


if __name__ == "__main__":
    main()
