"""Minimal HS256 JWT implementation (stdlib only, single issuer == verifier).

RS256/JWKS are intentionally unsupported — see specs/decisions.md ADR-008.
"""

import base64
import hashlib
import hmac
import json
import time


class InvalidToken(Exception):
    pass


class ExpiredToken(InvalidToken):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64decode(segment: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(segment + '=' * (-len(segment) % 4))
    except (ValueError, TypeError) as exc:
        raise InvalidToken('Malformed base64 segment') from exc


def sign(payload: dict, secret: str) -> str:
    def segment(obj):
        return _b64encode(json.dumps(obj, separators=(',', ':'), sort_keys=True).encode())

    signing_input = f"{segment({'alg': 'HS256', 'typ': 'JWT'})}.{segment(payload)}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f'{signing_input}.{_b64encode(signature)}'


def verify(token: str, secret: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split('.')
    except ValueError as exc:
        raise InvalidToken('Token must have three segments') from exc

    signing_input = f'{header_b64}.{payload_b64}'.encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64decode(signature_b64)):
        raise InvalidToken('Signature mismatch')

    try:
        header = json.loads(_b64decode(header_b64))
        payload = json.loads(_b64decode(payload_b64))
    except ValueError as exc:
        raise InvalidToken('Malformed JSON segment') from exc

    if not isinstance(header, dict) or header.get('alg') != 'HS256':
        raise InvalidToken('Unsupported algorithm')
    if not isinstance(payload, dict):
        raise InvalidToken('Payload must be an object')

    exp = payload.get('exp')
    if exp is not None and time.time() > float(exp):
        raise ExpiredToken('Token has expired')
    return payload
