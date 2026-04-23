"""Tests for credential / secret redaction in log and error strings."""

from nanobanana_mcp_server.utils.logging_utils import sanitize_error_message


def test_sanitize_pem_block() -> None:
    msg = "err: -----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY----- tail"
    out = sanitize_error_message(msg)
    assert "BEGIN PRIVATE" not in out
    assert "REDACTED: PEM block" in out
    assert "tail" in out


def test_sanitize_service_account_json_file_error() -> None:
    """Mimics DefaultCredentialsError embedding full JSON as filename."""
    blob = (
        '{"type":"service_account","project_id":"x",'
        '"private_key":"-----BEGIN PRIVATE KEY-----\\nSECRET\\n-----END PRIVATE KEY-----\\n"}'
    )
    msg = f"File {blob} was not found."
    out = sanitize_error_message(msg)
    assert "PRIVATE KEY" not in out
    assert "SECRET" not in out
    assert "REDACTED" in out


def test_sanitize_long_base64_run() -> None:
    long_token = "A" * 250
    out = sanitize_error_message(f"bad: {long_token}")
    assert long_token not in out
    assert "REDACTED: long token" in out


def test_short_string_unchanged() -> None:
    assert sanitize_error_message("normal error") == "normal error"
