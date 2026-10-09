"""Ed25519 与授权串编解码的官方向量/边界测试。

RFC 8032 §7.1 的 TEST 1-3 是权威向量：任何实现偏差都会在这里暴露。
"""

import json

import pytest

from milk_license import codec, ed25519

# RFC 8032 §7.1 测试向量：(secret_seed_hex, public_hex, message_hex, signature_hex)
RFC8032_VECTORS = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
]

# RFC 8032 §7.1 TEST SHA(abc)：用于确认 SHA-512 实现与向量一致
SHA512_ABC = (
    "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
    "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f"
)


def test_sha512_matches_rfc8032_reference():
    import hashlib

    assert hashlib.sha512(b"abc").hexdigest() == SHA512_ABC


@pytest.mark.parametrize("seed_hex,public_hex,message_hex,signature_hex", RFC8032_VECTORS)
def test_public_key_matches_rfc8032(seed_hex, public_hex, message_hex, signature_hex):
    seed = bytes.fromhex(seed_hex)
    assert ed25519.public_key(seed).hex() == public_hex


@pytest.mark.parametrize("seed_hex,public_hex,message_hex,signature_hex", RFC8032_VECTORS)
def test_sign_matches_rfc8032(seed_hex, public_hex, message_hex, signature_hex):
    seed = bytes.fromhex(seed_hex)
    message = bytes.fromhex(message_hex)
    public = bytes.fromhex(public_hex)
    assert ed25519.sign(message, seed, public).hex() == signature_hex


@pytest.mark.parametrize("seed_hex,public_hex,message_hex,signature_hex", RFC8032_VECTORS)
def test_verify_accepts_rfc8032(seed_hex, public_hex, message_hex, signature_hex):
    message = bytes.fromhex(message_hex)
    public = bytes.fromhex(public_hex)
    signature = bytes.fromhex(signature_hex)
    assert ed25519.verify(signature, message, public) is True


def test_verify_rejects_tampered_message():
    seed = bytes.fromhex(RFC8032_VECTORS[1][0])
    public = bytes.fromhex(RFC8032_VECTORS[1][1])
    signature = bytes.fromhex(RFC8032_VECTORS[1][3])
    assert ed25519.verify(signature, b"\x73", public) is False


def test_verify_rejects_tampered_signature():
    message = bytes.fromhex(RFC8032_VECTORS[1][2])
    public = bytes.fromhex(RFC8032_VECTORS[1][1])
    signature = bytearray(bytes.fromhex(RFC8032_VECTORS[1][3]))
    signature[0] ^= 0x01
    assert ed25519.verify(bytes(signature), message, public) is False


def test_verify_rejects_wrong_public_key():
    message = bytes.fromhex(RFC8032_VECTORS[1][2])
    signature = bytes.fromhex(RFC8032_VECTORS[1][3])
    other_public = bytes.fromhex(RFC8032_VECTORS[0][1])
    assert ed25519.verify(signature, message, other_public) is False


def test_verify_rejects_malformed_input_without_raising():
    assert ed25519.verify(b"", b"m", b"\x00" * 32) is False
    assert ed25519.verify(b"\x00" * 64, b"m", b"\x00" * 32) is False
    assert ed25519.verify(b"\x00" * 64, b"m", b"") is False


# ── 授权串编解码 ──────────────────────────────────────────────

SEED = bytes.fromhex(RFC8032_VECTORS[2][0])
PUBLIC = bytes.fromhex(RFC8032_VECTORS[2][1])

PAYLOAD = {
    "v": 1,
    "licensee": "乍甸乳业",
    "issued_at": "2026-10-09T00:00:00Z",
    "expires_at": "2027-10-09T00:00:00Z",
    "level": "full",
}


def test_issue_and_decode_round_trip():
    code = codec.issue_license(PAYLOAD, SEED)
    decoded = codec.decode_license(code, PUBLIC)
    assert decoded["licensee"] == "乍甸乳业"
    assert decoded["level"] == "full"
    assert codec.expires_at(decoded).year == 2027


def test_decode_rejects_tampered_payload():
    code = codec.issue_license(PAYLOAD, SEED)
    body_b64, signature_b64 = code.split(".")
    tampered = json.loads(codec._b64decode(body_b64).decode("utf-8"))
    tampered["expires_at"] = "2037-10-09T00:00:00Z"
    forged_body = codec._b64encode(json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    with pytest.raises(codec.LicenseError):
        codec.decode_license(f"{forged_body}.{signature_b64}", PUBLIC)


def test_decode_rejects_tampered_signature():
    code = codec.issue_license(PAYLOAD, SEED)
    body_b64, signature_b64 = code.split(".")
    broken = bytearray(codec._b64decode(signature_b64))
    broken[0] ^= 0x01
    with pytest.raises(codec.LicenseError):
        codec.decode_license(f"{body_b64}.{codec._b64encode(bytes(broken))}", PUBLIC)


def test_decode_rejects_other_issuer():
    code = codec.issue_license(PAYLOAD, SEED)
    other_public = bytes.fromhex(RFC8032_VECTORS[0][1])
    with pytest.raises(codec.LicenseError):
        codec.decode_license(code, other_public)


@pytest.mark.parametrize("bad", ["", "no-dot", "a.b.c", "!!!.???", "abc."])
def test_decode_rejects_malformed(bad):
    with pytest.raises(codec.LicenseError):
        codec.decode_license(bad, PUBLIC)


def test_decode_rejects_missing_field():
    payload = dict(PAYLOAD)
    payload.pop("licensee")
    code = codec.issue_license(payload, SEED)
    with pytest.raises(codec.LicenseError):
        codec.decode_license(code, PUBLIC)


def test_decode_rejects_unsupported_version():
    payload = dict(PAYLOAD, v=99)
    code = codec.issue_license(payload, SEED)
    with pytest.raises(codec.LicenseError):
        codec.decode_license(code, PUBLIC)


def test_issue_is_deterministic_for_canonical_payload():
    """键顺序不同但内容相同的 payload 必须产出同一解锁码（规范化）。"""
    reordered = {
        "level": "full",
        "expires_at": PAYLOAD["expires_at"],
        "licensee": PAYLOAD["licensee"],
        "issued_at": PAYLOAD["issued_at"],
        "v": 1,
    }
    assert codec.issue_license(PAYLOAD, SEED) == codec.issue_license(reordered, SEED)
