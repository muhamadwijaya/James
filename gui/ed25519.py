"""Ed25519 signatures in pure Python (only hashlib), used for offline license verification.

Based on the public-domain reference implementation from https://ed25519.cr.yp.to/python/ed25519.py
(Daniel J. Bernstein et al.). It is slow but activation happens rarely, so that is fine, and it
needs no third-party package - PyInstaller bundles it with no extra wheels.

The application embeds only the vendor PUBLIC key and calls verify(). The matching PRIVATE key
(a 32-byte seed) stays with the vendor's license tool and never ships with the app.
"""
from __future__ import annotations

import hashlib

_b = 256
_q = 2 ** 255 - 19
_l = 2 ** 252 + 27742317777372353535851937790883648493


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _expmod(base: int, e: int, m: int) -> int:
    return pow(base, e, m)


def _inv(x: int) -> int:
    return _expmod(x, _q - 2, _q)


_d = -121665 * _inv(121666) % _q
_I = _expmod(2, (_q - 1) // 4, _q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = _expmod(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = 4 * _inv(5)
_Bx = _xrecover(_By)
_B = [_Bx % _q, _By % _q]


def _edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _d * x1 * x2 * y1 * y2)
    return [x3 % _q, y3 % _q]


def _scalarmult(P, e: int):
    # double-and-add, most significant bit first (same result as the recursive reference)
    Q = [0, 1]
    for bit in bin(e)[2:] if e > 0 else "":
        Q = _edwards(Q, Q)
        if bit == "1":
            Q = _edwards(Q, P)
    return Q


def _encodeint(y: int) -> bytes:
    bits = [(y >> i) & 1 for i in range(_b)]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_b // 8))


def _encodepoint(P) -> bytes:
    x, y = P
    bits = [(y >> i) & 1 for i in range(_b - 1)] + [x & 1]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_b // 8))


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _hint(m: bytes) -> int:
    h = _H(m)
    return sum(2 ** i * _bit(h, i) for i in range(2 * _b))


def _secret_scalar(sk: bytes) -> int:
    h = _H(sk)
    return 2 ** (_b - 2) + sum(2 ** i * _bit(h, i) for i in range(3, _b - 2))


def publickey(sk: bytes) -> bytes:
    """32-byte public key for a 32-byte private seed."""
    A = _scalarmult(_B, _secret_scalar(sk))
    return _encodepoint(A)


def signature(m: bytes, sk: bytes, pk: bytes) -> bytes:
    """64-byte signature of ``m`` under private seed ``sk`` (``pk`` = publickey(sk))."""
    h = _H(sk)
    a = _secret_scalar(sk)
    r = _hint(bytes(h[j] for j in range(_b // 8, _b // 4)) + m)
    R = _scalarmult(_B, r)
    S = (r + _hint(_encodepoint(R) + pk + m) * a) % _l
    return _encodepoint(R) + _encodeint(S)


def _isoncurve(P) -> bool:
    x, y = P
    return (-x * x + y * y - 1 - _d * x * x * y * y) % _q == 0


def _decodeint(s: bytes) -> int:
    return sum(2 ** i * _bit(s, i) for i in range(_b))


def _decodepoint(s: bytes):
    y = sum(2 ** i * _bit(s, i) for i in range(_b - 1))
    x = _xrecover(y)
    if x & 1 != _bit(s, _b - 1):
        x = _q - x
    P = [x, y]
    if not _isoncurve(P):
        raise ValueError("point not on curve")
    return P


def verify(sig: bytes, m: bytes, pk: bytes) -> bool:
    """True when ``sig`` is a valid Ed25519 signature of ``m`` under public key ``pk``."""
    try:
        if len(sig) != _b // 4 or len(pk) != _b // 8:
            return False
        R = _decodepoint(sig[0:_b // 8])
        A = _decodepoint(pk)
        S = _decodeint(sig[_b // 8:_b // 4])
        h = _hint(_encodepoint(R) + pk + m)
        return _scalarmult(_B, S) == _edwards(R, _scalarmult(A, h))
    except (ValueError, IndexError):
        return False


def keypair_from_seed(seed: bytes) -> tuple[bytes, bytes]:
    """(private seed, public key). ``seed`` must be 32 bytes."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    return seed, publickey(seed)
