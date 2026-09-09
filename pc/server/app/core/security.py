import base64
import hashlib
import hmac
import json
import secrets
import time


ITERATIONS = 240_000
TOKEN_TTL_SECONDS = 8 * 60 * 60


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(iterations))
        return hmac.compare_digest(base64.urlsafe_b64encode(digest).decode(), expected)
    except (TypeError, ValueError):
        return False


def create_token(user_id: int, role: str) -> str:
    payload = {"sub": user_id, "role": role, "exp": int(time.time()) + TOKEN_TTL_SECONDS, "nonce": secrets.token_hex(8)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def decode_token(token: str) -> dict:
    try:
        body, encoded_signature = token.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(encoded_signature, expected):
            raise ValueError("invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) <= int(time.time()):
            raise ValueError("expired")
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid token") from exc


def _secret() -> bytes:
    # Replace with a persisted installation secret before production deployment.
    return b"milk-weigh-development-secret-change-before-release"
