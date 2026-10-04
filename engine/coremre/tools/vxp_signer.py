#!/usr/bin/env python3
"""Normalize and sign an MRE VXP package using the re3-compatible format."""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import secrets
import shutil
import struct
import zlib
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

TRAILER_SIZE = 86
MARKER = b"\xB4VDE10"


def _der_length(length: int) -> bytes:
    if length < 128:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def _der(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _der_length(len(value)) + value


def _der_integer(value: int) -> bytes:
    encoded = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    if encoded[0] & 0x80:
        encoded = b"\0" + encoded
    return _der(0x02, encoded)


def _probable_prime(value: int, rounds: int = 32) -> bool:
    if value < 2 or value % 2 == 0:
        return value == 2
    for prime in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47):
        if value == prime:
            return True
        if value % prime == 0:
            return False
    d, s = value - 1, 0
    while d % 2 == 0:
        s += 1
        d //= 2
    for _ in range(rounds):
        x = pow(secrets.randbelow(value - 3) + 2, d, value)
        if x in (1, value - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, value)
            if x == value - 1:
                break
        else:
            return False
    return True


def _prime(bits: int, exponent: int) -> int:
    while True:
        value = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if (value - 1) % exponent and _probable_prime(value):
            return value


def generate_rsa512_pem() -> bytes:
    """Generate legacy RSA-512 PKCS#8 material without library size restrictions."""
    exponent = 65537
    while True:
        p, q = _prime(256, exponent), _prime(256, exponent)
        if p != q and (p * q).bit_length() == 512:
            break
    private = pow(exponent, -1, (p - 1) * (q - 1))
    values = (0, p * q, exponent, private, p, q,
              private % (p - 1), private % (q - 1), pow(q, -1, p))
    pkcs1 = _der(0x30, b"".join(_der_integer(value) for value in values))
    algorithm = _der(0x30, bytes.fromhex("06092A864886F70D010101") + _der(0x05, b""))
    pkcs8 = _der(0x30, _der_integer(0) + algorithm + _der(0x04, pkcs1))
    body = base64.b64encode(pkcs8)
    lines = [body[index:index + 64] for index in range(0, len(body), 64)]
    return b"-----BEGIN PRIVATE KEY-----\n" + b"\n".join(lines) + b"\n-----END PRIVATE KEY-----\n"


def create_key(output: Path) -> str:
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing private key: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_bytes(generate_rsa512_pem())
    os.replace(temporary, output)
    key = serialization.load_pem_private_key(output.read_bytes(), password=None)
    public_der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    output.with_name(output.stem + ".pub.pem").write_bytes(public_pem)
    fingerprint = hashlib.sha256(public_der).hexdigest().upper()
    output.with_name(output.name + ".public.sha256").write_text(fingerprint + "\n", encoding="ascii")
    return fingerprint


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = path.with_name(f"{path.name}.backup-{stamp}")
    shutil.copy2(path, target)
    return target


def _decode_text(value: bytes) -> str:
    utf16 = len(value) >= 2 and len(value) % 2 == 0 and value[1::2].count(0) >= len(value[1::2]) // 2
    return value.decode("utf-16-le" if utf16 else "utf-8", errors="replace").rstrip("\0")


def _normalize(data: bytes, requested_app_id: int, cert_id: int, requested_vendor: str) -> tuple[bytes, int, str]:
    if len(data) < TRAILER_SIZE or data[-TRAILER_SIZE:-80] != MARKER:
        raise ValueError("Unsupported VXP: missing re3-compatible 86-byte trailer")
    trailer_start = len(data) - TRAILER_SIZE
    tags_pos = struct.unpack_from("<I", data, len(data) - 12)[0]
    if not 0 <= tags_pos < trailer_start:
        raise ValueError("Invalid VXP tag offset")

    pos, rebuilt = tags_pos, bytearray()
    app_id, vendor, terminated = requested_app_id, "", False
    while pos + 8 <= trailer_start:
        tag, length = struct.unpack_from("<II", data, pos)
        pos += 8
        if pos + length > trailer_start:
            raise ValueError("Invalid VXP tag length")
        value = data[pos:pos + length]
        pos += length
        if tag == 1:
            vendor = _decode_text(value)
            if requested_vendor:
                utf16 = len(value) >= 2 and len(value) % 2 == 0 and value[1::2].count(0) >= len(value[1::2]) // 2
                has_nul = value.endswith(b"\0\0") if utf16 else value.endswith(b"\0")
                value = requested_vendor.encode("utf-16-le" if utf16 else "utf-8")
                if has_nul:
                    value += b"\0\0" if utf16 else b"\0"
                vendor = requested_vendor
        elif tag == 2 and length == 4:
            current = struct.unpack("<I", value)[0]
            if app_id <= 0:
                app_id = current if 0 < current <= 0x7FFFFFFF else 0
            if app_id <= 0:
                app_id = zlib.crc32(data[:tags_pos]) & 0x7FFFFFFF
                if app_id < 10000:
                    app_id += 10000
            value = struct.pack("<I", app_id)
        elif tag == 3 and length == 4:
            value = struct.pack("<I", cert_id)
        elif tag == 0x12:
            value = b"*\0" if len(value) >= 2 and len(value) % 2 == 0 and value[1::2].count(0) else b"*"
        rebuilt.extend(struct.pack("<II", tag, len(value)))
        rebuilt.extend(value)
        if tag == 0:
            terminated = True
            break
    if not terminated or pos != trailer_start or app_id <= 0:
        raise ValueError("Unsupported or incomplete VXP tag stream")
    return data[:tags_pos] + rebuilt, app_id, vendor


def sign(source: Path, target: Path, key_path: Path, app_id: int, cert_id: int, vendor: str) -> None:
    source, target, key_path = source.resolve(), target.resolve(), key_path.resolve()
    if source == target:
        raise ValueError("Input and output must differ")
    if not source.is_file():
        raise FileNotFoundError(source)
    if not key_path.is_file():
        raise FileNotFoundError(key_path)

    original = source.read_bytes()
    payload, selected_app_id, selected_vendor = _normalize(original, app_id, cert_id, vendor)
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if key.key_size != 512:
        raise ValueError(f"VXP requires an RSA-512 key, got RSA-{key.key_size}")
    signature = key.sign(payload, padding.PKCS1v15(), hashes.SHA1())
    key.public_key().verify(signature, payload, padding.PKCS1v15(), hashes.SHA1())

    trailer = bytearray(original[-TRAILER_SIZE:])
    struct.pack_into("<I", trailer, 6, cert_id)
    trailer[10:74] = signature
    encoded = payload + trailer
    target.parent.mkdir(parents=True, exist_ok=True)
    old = _backup(target)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, target)
    digest = hashlib.sha256(encoded).hexdigest().upper()
    checksum = target.with_name(target.name + ".sha256")
    checksum.write_text(f"{digest} *{target.name}\n", encoding="ascii")

    print("SIGNATURE : RSA-SHA1 PKCS#1 v1.5")
    print(f"APP ID    : {selected_app_id}")
    print(f"VENDOR    : {selected_vendor}")
    print(f"CERT ID   : {cert_id}")
    print("IMSI      : *")
    print("VERIFY    : OK")
    print(f"OUTPUT    : {target}")
    print(f"SHA-256   : {digest}")
    if old:
        print(f"BACKUP    : {old}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("key", type=Path)
    parser.add_argument("--appid", type=int, default=0)
    parser.add_argument("--certid", type=int, default=100)
    parser.add_argument("--vendor", default="")
    args = parser.parse_args()
    sign(args.input, args.output, args.key, args.appid, args.certid, args.vendor)


if __name__ == "__main__":
    main()
