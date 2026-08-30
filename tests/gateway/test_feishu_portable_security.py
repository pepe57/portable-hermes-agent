import asyncio
import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plugins.platforms.feishu import adapter as feishu


class _FakeResponse:
    def __init__(self, *, status: int = 200, text: str = "", payload=None):
        self.status = status
        self.text = text
        self.payload = payload


@pytest.fixture(autouse=True)
def _web_response_shim(monkeypatch):
    monkeypatch.setattr(
        feishu,
        "web",
        SimpleNamespace(
            Response=lambda *, status=200, text="": _FakeResponse(
                status=status, text=text
            ),
            json_response=lambda payload, status=200: _FakeResponse(
                status=status, payload=payload
            ),
        ),
    )


class _RequestContent:
    def __init__(self, body: bytes):
        self.body = body

    async def readexactly(self, size: int) -> bytes:
        if len(self.body) < size:
            raise asyncio.IncompleteReadError(self.body, size)
        return self.body[:size]


def _request(payload: object, *, headers: dict | None = None):
    body = json.dumps(payload).encode("utf-8")
    return SimpleNamespace(
        remote="203.0.113.10",
        content_length=len(body),
        headers={"Content-Type": "application/json", **(headers or {})},
        content=_RequestContent(body),
    )


def _adapter(*, token: str = "token", encrypt_key: str = ""):
    instance = object.__new__(feishu.FeishuAdapter)
    instance._app_id = "cli_portable"
    instance._webhook_path = "/feishu/webhook"
    instance._verification_token = token
    instance._encrypt_key = encrypt_key
    instance._record_webhook_anomaly = Mock()
    instance._clear_webhook_anomaly = Mock()
    instance._check_webhook_rate_limit = Mock(return_value=True)
    instance._on_message_event = Mock()
    instance._on_message_read_event = Mock()
    instance._on_bot_added_to_chat = Mock()
    instance._on_bot_removed_from_chat = Mock()
    instance._on_reaction_event = Mock()
    instance._on_card_action_trigger = Mock()
    instance._on_drive_comment_event = Mock()
    instance._on_meeting_invited_event = Mock()
    return instance


def test_invalid_token_does_not_consume_authenticated_delivery_quota():
    instance = _adapter()

    response = asyncio.run(
        instance._handle_webhook_request(
            _request({"header": {"token": "wrong", "event_type": "unknown"}})
        )
    )

    assert response.status == 401
    instance._check_webhook_rate_limit.assert_not_called()


def test_invalid_signature_does_not_consume_authenticated_delivery_quota():
    instance = _adapter(encrypt_key="encrypt-secret")

    response = asyncio.run(
        instance._handle_webhook_request(
            _request({"header": {"token": "token", "event_type": "unknown"}})
        )
    )

    assert response.status == 401
    instance._check_webhook_rate_limit.assert_not_called()


def test_authenticated_delivery_is_rate_limited_after_authentication():
    instance = _adapter()

    response = asyncio.run(
        instance._handle_webhook_request(
            _request({"header": {"token": "token", "event_type": "unknown"}})
        )
    )

    assert response.status == 200
    instance._check_webhook_rate_limit.assert_called_once_with(
        "cli_portable:/feishu/webhook:203.0.113.10"
    )


def test_unsigned_url_challenge_requires_configured_verification_token():
    instance = _adapter(token="", encrypt_key="encrypt-secret")

    response = asyncio.run(
        instance._handle_webhook_request(
            _request({"type": "url_verification", "challenge": "attacker-value"})
        )
    )

    assert response.status == 401
    instance._check_webhook_rate_limit.assert_not_called()


def test_signature_hashes_raw_body_bytes():
    instance = _adapter(encrypt_key="encrypt-secret")
    body = b'{"payload":"\xff"}'
    timestamp = "1700000000"
    nonce = "portable"
    digest = hashlib.sha256(
        f"{timestamp}{nonce}encrypt-secret".encode("utf-8") + body
    ).hexdigest()

    assert instance._is_webhook_signature_valid(
        {
            "x-lark-request-timestamp": timestamp,
            "x-lark-request-nonce": nonce,
            "x-lark-signature": digest,
        },
        body,
    )


def test_encrypted_event_is_decrypted_and_authenticated_before_quota():
    cryptography = pytest.importorskip("cryptography.hazmat.primitives")
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    del cryptography
    encrypt_key = "encrypt-secret"
    plaintext = json.dumps({"header": {"event_type": "unknown"}}).encode("utf-8")
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext) + padder.finalize()
    iv = b"portable-hermes!"
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encrypted = base64.b64encode(iv + encryptor.update(padded) + encryptor.finalize())

    instance = _adapter(token="", encrypt_key=encrypt_key)
    request = _request({"encrypt": encrypted.decode("ascii")})
    body = request.content.body
    timestamp = "1700000000"
    nonce = "portable"
    request.headers.update(
        {
            "x-lark-request-timestamp": timestamp,
            "x-lark-request-nonce": nonce,
            "x-lark-signature": hashlib.sha256(
                f"{timestamp}{nonce}{encrypt_key}".encode("utf-8") + body
            ).hexdigest(),
        }
    )

    response = asyncio.run(instance._handle_webhook_request(request))

    assert response.status == 200
    instance._check_webhook_rate_limit.assert_called_once()


def test_nested_json_and_anomaly_tracking_are_bounded(monkeypatch):
    nested: object = "leaf"
    for _ in range(feishu._FEISHU_WEBHOOK_MAX_JSON_DEPTH + 1):
        nested = {"child": nested}
    assert not feishu._json_containers_within_depth(
        nested, feishu._FEISHU_WEBHOOK_MAX_JSON_DEPTH
    )
    with pytest.raises(feishu._InvalidFeishuMessagePayload):
        feishu._load_feishu_payload(json.dumps(nested))

    instance = object.__new__(feishu.FeishuAdapter)
    instance._webhook_anomaly_counts = {
        f"198.51.100.{index}": (1, "401", 1.0)
        for index in range(feishu._FEISHU_WEBHOOK_ANOMALY_MAX_KEYS)
    }
    instance._webhook_anomaly_next_sweep_at = 0.0
    monkeypatch.setattr(feishu.time, "time", lambda: 2.0)

    instance._record_webhook_anomaly("203.0.113.10", "401")

    assert len(instance._webhook_anomaly_counts) == feishu._FEISHU_WEBHOOK_ANOMALY_MAX_KEYS
    assert "203.0.113.10" not in instance._webhook_anomaly_counts
