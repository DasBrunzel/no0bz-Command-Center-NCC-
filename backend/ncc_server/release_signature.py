"""Verify signed payload manifests before the server distributes them on its own.

Core verifies every payload again before it runs one, so this check only keeps
a forged or broken manifest from ever being offered automatically. The server
has no cryptography dependency, so Ed25519 verification follows RFC 8032
section 5.1.7 directly. It is slow by library standards (a few milliseconds),
which is fine for a handful of manifests per check.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Any

# Public release keys; keep in sync with windows/installer/trusted-keys.json.
TRUSTED_RELEASE_KEYS = {"ncc-release-2026": "uf/HTI8fDX2QLbAEYQ6NA82rM7lBGW5oxeaV4vVvoag="}

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)

Point = tuple[int, int, int, int]


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _add(left: Point, right: Point) -> Point:
    a = (left[1] - left[0]) * (right[1] - right[0]) % _P
    b = (left[1] + left[0]) * (right[1] + right[0]) % _P
    c = 2 * left[3] * right[3] * _D % _P
    d = 2 * left[2] * right[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _multiply(scalar: int, point: Point) -> Point:
    result: Point = (0, 1, 1, 0)
    while scalar > 0:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _equal(left: Point, right: Point) -> bool:
    return (left[0] * right[2] - right[0] * left[2]) % _P == 0 and (
        left[1] * right[2] - right[1] * left[2]
    ) % _P == 0


def _decompress(data: bytes) -> Point | None:
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _recover_x(_GY, 0)
assert _GX is not None
_BASE: Point = (_GX, _GY, 1, _GX * _GY % _P)


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    a = _decompress(public_key)
    r = _decompress(signature[:32])
    if a is None or r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    h = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _L
    return _equal(_multiply(s, _BASE), _add(r, _multiply(h, a)))


def manifest_signature_valid(manifest: dict[str, Any]) -> bool:
    """True when a trusted release key signed this payload manifest."""
    signature = manifest.get("signature")
    artifacts = manifest.get("artifacts")
    if not isinstance(signature, dict) or not isinstance(artifacts, list) or len(artifacts) != 1:
        return False
    artifact = artifacts[0]
    key = TRUSTED_RELEASE_KEYS.get(str(signature.get("key_id")))
    if key is None or not isinstance(artifact, dict):
        return False
    try:
        public_key = base64.b64decode(key, validate=True)
        signature_bytes = base64.b64decode(str(signature.get("value")), validate=True)
    except (binascii.Error, ValueError):
        return False
    # The statement build_ncc_payload.ps1 signs and Core verifies.
    statement = (
        f"NCC-AGENT-RELEASE-V1\n{artifact.get('payload_version')}\n"
        f"{str(artifact.get('sha256')).lower()}\n{artifact.get('size_bytes')}\n"
    ).encode()
    return ed25519_verify(public_key, statement, signature_bytes)
