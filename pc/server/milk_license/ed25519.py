"""纯 Python Ed25519（签名 / 验签）。

采用 Ed25519 标准构造（RFC 8032），不依赖任何第三方库：
交付物运行在嵌入式 CPython 上，避免为签名校验引入新的二进制依赖。

安全边界：
  - 私钥（seed）只存在于开发方签发环境，永不进入交付物。
  - 交付物只内置公钥，用于验签；验签失败一律拒绝。
  - 正确性由 tests/test_license_ed25519.py 中的 RFC 8032 官方向量保证。
"""

from __future__ import annotations

import hashlib

BITS = 256
# 域参数
Q = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _expmod(base: int, exponent: int, modulus: int) -> int:
    """模幂（迭代实现，避免深递归）。"""
    result = 1
    base %= modulus
    while exponent > 0:
        if exponent & 1:
            result = (result * base) % modulus
        base = (base * base) % modulus
        exponent >>= 1
    return result


def _inv(x: int) -> int:
    return _expmod(x, Q - 2, Q)


_D = (-121665 * _inv(121666)) % Q
_I = _expmod(2, (Q - 1) // 4, Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = _expmod(xx, (Q + 3) // 8, Q)
    if (x * x - xx) % Q != 0:
        x = (x * _I) % Q
    if x % 2 != 0:
        x = Q - x
    return x


_BY = (4 * _inv(5)) % Q
_BX = _xrecover(_BY)
_B = [_BX % Q, _BY % Q]
_IDENTITY = [0, 1]


def _edwards(p: list[int], q: list[int]) -> list[int]:
    x1, y1 = p
    x2, y2 = q
    k = _D * x1 * x2 * y1 * y2
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + k)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - k)
    return [x3 % Q, y3 % Q]


def _scalarmult(point: list[int], scalar: int) -> list[int]:
    """标量乘（double-and-add 迭代实现）。"""
    result = list(_IDENTITY)
    addend = list(point)
    while scalar > 0:
        if scalar & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        scalar >>= 1
    return result


def _encode_int(value: int) -> bytes:
    return value.to_bytes(BITS // 8, "little")


def _encode_point(point: list[int]) -> bytes:
    x, y = point
    return (y | ((x & 1) << (BITS - 1))).to_bytes(BITS // 8, "little")


def _bit(data: bytes, index: int) -> int:
    return (data[index // 8] >> (index % 8)) & 1


def _decode_point(data: bytes) -> list[int]:
    if len(data) != BITS // 8:
        raise ValueError("point must be 32 bytes")
    value = int.from_bytes(data, "little")
    y = value & ((1 << (BITS - 1)) - 1)
    x = _xrecover(y)
    if (x & 1) != (value >> (BITS - 1)):
        x = Q - x
    point = [x, y]
    if not _is_on_curve(point):
        raise ValueError("decoded point is not on curve")
    return point


def _is_on_curve(point: list[int]) -> bool:
    x, y = point
    return (-x * x + y * y - 1 - _D * x * x * y * y) % Q == 0


def _secret_scalar(seed: bytes) -> int:
    digest = _sha512(seed)
    return 2 ** (BITS - 2) + sum(2**i * _bit(digest, i) for i in range(3, BITS - 2))


def _hint(*chunks: bytes) -> int:
    digest = _sha512(b"".join(chunks))
    return sum(2**i * _bit(digest, i) for i in range(2 * BITS))


def public_key(seed: bytes) -> bytes:
    """由 32 字节私钥种子推导 32 字节公钥。"""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    return _encode_point(_scalarmult(_B, _secret_scalar(seed)))


def sign(message: bytes, seed: bytes, public: bytes) -> bytes:
    """对 message 签名，返回 64 字节签名。"""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    if len(public) != 32:
        raise ValueError("public key must be 32 bytes")
    digest = _sha512(seed)
    scalar = _secret_scalar(seed)
    prefix = digest[BITS // 8 : BITS // 4]
    r = _hint(prefix, message)
    big_r = _scalarmult(_B, r)
    s = (r + _hint(_encode_point(big_r), public, message) * scalar) % L
    return _encode_point(big_r) + _encode_int(s)


def verify(signature: bytes, message: bytes, public: bytes) -> bool:
    """验签；任何格式或数值问题都返回 False（不抛异常，便于调用方统一拒绝）。"""
    try:
        if len(signature) != BITS // 4 or len(public) != BITS // 8:
            return False
        big_r = _decode_point(signature[: BITS // 8])
        point_a = _decode_point(public)
        s = int.from_bytes(signature[BITS // 8 : BITS // 4], "little")
        if s >= L:
            return False
        h = _hint(_encode_point(big_r), public, message)
        return _scalarmult(_B, s) == _edwards(big_r, _scalarmult(point_a, h))
    except (ValueError, TypeError):
        return False
