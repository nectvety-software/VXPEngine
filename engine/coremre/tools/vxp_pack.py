#!/usr/bin/env python3
"""Package ARM ELF32 and MRE resources as an unsigned VXP application."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

MARKER = b"\xb4VDE10"
API_NAMES = (
    "Audio", "Call", "Camera", "File", "HTTP", "Record", "Sensor",
    "SIM_card", "SMS_person", "SMS_SP", "TCP", "SysStorage", "Sec",
    "BitStream", "Contact", "LBS", "MMS", "ProMng", "SMSMng", "Video",
    "XML", "Payment", "SysFile", "BT", "UDP", "PUSH",
)


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def _fix_resource_offsets(resource: bytearray, base: int) -> None:
    pos = 0
    while True:
        end = resource.find(0, pos)
        if end < 0:
            raise ValueError("Invalid MRE resource name table")
        if end == pos:
            pos += 1
            break
        pos = end + 1
        if pos + 8 > len(resource):
            raise ValueError("Truncated MRE resource table")
        offset = struct.unpack_from("<I", resource, pos)[0]
        struct.pack_into("<I", resource, pos, offset + base)
        pos += 8
    if pos + 8 > len(resource):
        raise ValueError("Missing MRE 2.0 resource pointer")
    relative = struct.unpack_from("<I", resource, pos)[0]
    absolute = relative + base
    struct.pack_into("<I", resource, pos, absolute)
    pos = relative
    while True:
        if pos + 8 > len(resource):
            raise ValueError("Invalid MRE 2.0 resource index")
        resource_id, offset = struct.unpack_from("<II", resource, pos)
        struct.pack_into("<I", resource, pos + 4, offset + base)
        pos += 8
        if resource_id == 0xFFFFFFFF:
            break


def _embed_vm_res(elf: bytes, resource: bytes) -> bytes:
    if elf[:4] != b"\x7fELF" or elf[4] != 1 or elf[5] != 1:
        raise ValueError("Only little-endian ELF32 ARM executables are supported")
    if len(elf) < 52:
        raise ValueError("Truncated ELF header")
    shoff = struct.unpack_from("<I", elf, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", elf, 46)
    if shentsize != 40 or not shnum or shstrndx >= shnum:
        raise ValueError("Unsupported ELF32 section table")
    headers_end = shoff + shentsize * shnum
    if headers_end > len(elf):
        raise ValueError("Invalid ELF section table offset")
    headers = [bytearray(elf[shoff + i * 40:shoff + (i + 1) * 40]) for i in range(shnum)]
    str_header = headers[shstrndx]
    str_offset, str_size = struct.unpack_from("<II", str_header, 16)
    if str_offset + str_size > len(elf):
        raise ValueError("Invalid ELF section-name table")
    strings = bytearray(elf[str_offset:str_offset + str_size])
    name_offset = len(strings)
    strings.extend(b".vm_res\0")

    out = bytearray(elf)
    resource_offset = _align(len(out), 4)
    out.extend(b"\0" * (resource_offset - len(out)))
    fixed_resource = bytearray(resource)
    _fix_resource_offsets(fixed_resource, resource_offset)
    out.extend(fixed_resource)
    new_strings_offset = len(out)
    out.extend(strings)
    new_shoff = _align(len(out), 4)
    out.extend(b"\0" * (new_shoff - len(out)))

    struct.pack_into("<II", str_header, 16, new_strings_offset, len(strings))
    for header in headers:
        out.extend(header)
    # name, PROGBITS, ALLOC, addr=0, file offset, size, link/info=0,
    # alignment=1, entry size=0.
    out.extend(struct.pack("<IIIIIIIIII", name_offset, 1, 2, 0,
                           resource_offset, len(fixed_resource), 0, 0, 1, 0))
    struct.pack_into("<I", out, 32, new_shoff)
    struct.pack_into("<H", out, 48, shnum + 1)
    return bytes(out)


def _text(value: str) -> bytes:
    return value.encode("utf-8") + b"\0"


def _u32(value: int) -> bytes:
    return struct.pack("<I", value & 0xFFFFFFFF)


def _tag(tag_id: int, value: bytes) -> bytes:
    return struct.pack("<II", tag_id, len(value)) + value


def _version(value: str) -> int:
    parts = value.split(".")[:3]
    if not parts or any(not item.isdigit() for item in parts):
        raise ValueError(f"Invalid application version: {value}")
    nums = [min(int(item), 255) for item in parts] + [0, 0, 0]
    return (nums[2] << 24) | (nums[1] << 16) | (nums[0] << 8)


def _multilingual(name: str) -> bytes:
    encoded = _text(name)
    return b"".join(_u32(language) + _u32(len(encoded)) + encoded for language in (1, 2, 3))


def _apis(value: str) -> bytes:
    requested = set(value.split())
    return b"".join(_u32(5000 + index) + _u32(1)
                    for index, name in enumerate(API_NAMES) if name in requested)


def package(axf: Path, resource_path: Path, output: Path, *, developer: str,
            name: str, app_id: int, cert_id: int, imsi: str, apis: str,
            version: str, ram: int, background: bool) -> None:
    elf = _embed_vm_res(axf.read_bytes(), resource_path.read_bytes())
    tag_pos = len(elf)
    tags = b"".join((
        _tag(0x01, _text(developer)), _tag(0x02, _u32(app_id)),
        _tag(0x03, _u32(cert_id)), _tag(0x04, _text(name)),
        _tag(0x05, _u32(_version(version))), _tag(0x0F, _u32(ram)),
        _tag(0x10, _u32(0)), _tag(0x11, _u32(0x9C400000)),
        _tag(0x12, _text(imsi)), _tag(0x13, _apis(apis)),
        _tag(0x16, _u32(1)), _tag(0x18, _u32(1 if background else 0)),
        _tag(0x19, _multilingual(name)), _tag(0x1C, _u32(0)),
        _tag(0x21, _u32(6)), _tag(0x22, _u32(0)), _tag(0x23, _u32(0)),
        _tag(0x25, _u32(0)), _tag(0x29, _u32(0)), _tag(0x00, b""),
    ))
    trailer = MARKER + _u32(cert_id) + bytes(64) + _u32(tag_pos) + bytes(8)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(elf + tags + trailer)
    print("FORMAT    : MRE VXP (GCC/ARM ELF32)")
    print(f"APP ID    : {app_id}")
    print(f"VENDOR    : {developer}")
    print(f"OUTPUT    : {output.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-a", "--axf", required=True, type=Path)
    parser.add_argument("-r", "--res", required=True, type=Path)
    parser.add_argument("-o", "--out", required=True, type=Path)
    parser.add_argument("-tdn", "--tag-develop-name", required=True, dest="developer")
    parser.add_argument("-tn", "--tag-name", required=True, dest="name")
    parser.add_argument("-tai", "--tag-appid", type=int, default=0, dest="app_id")
    parser.add_argument("-tci", "--tag-certid", type=int, default=1, dest="cert_id")
    parser.add_argument("-ti", "--tag-imsi", default="", dest="imsi")
    parser.add_argument("-tapi", "--tag-api", default="File SIM_card ProMng", dest="apis")
    parser.add_argument("-tv", "--tag-version", default="1.0.0", dest="version")
    parser.add_argument("-tr", "--tag-ram", type=int, default=512, dest="ram")
    parser.add_argument("-tb", "--tag-background", type=int, default=0, dest="background")
    parser.add_argument("-crt", "--cert", default="")  # Accepted for old build files; signing is separate.
    args, _ = parser.parse_known_args()
    package(args.axf, args.res, args.out, developer=args.developer, name=args.name,
            app_id=args.app_id, cert_id=args.cert_id, imsi=args.imsi, apis=args.apis,
            version=args.version, ram=args.ram, background=bool(args.background))


if __name__ == "__main__":
    main()
