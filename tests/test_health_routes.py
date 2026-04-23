"""Tests for HTTP /healthz and /readyz endpoints."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient


@pytest.mark.unit
def test_healthz_and_readyz_when_initialized() -> None:
    with (
        patch("nanobanana_mcp_server.config.settings.load_dotenv"),
        patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key-for-probes", "FASTMCP_TRANSPORT": "http"},
            clear=True,
        ),
    ):
        from nanobanana_mcp_server.server import create_app

        mcp = create_app()
        with TestClient(mcp.http_app()) as client:
            r = client.get("/healthz")
            assert r.status_code == 200
            assert r.json() == {"status": "ok", "check": "liveness"}

            r2 = client.get("/readyz")
            assert r2.status_code == 200
            assert r2.json() == {"status": "ok", "check": "readiness"}


@pytest.mark.unit
def test_readiness_state_not_ready_without_init() -> None:
    import nanobanana_mcp_server.services as svc

    with (
        patch.object(svc, "_server_config", None),
        patch.object(svc, "_gemini_client", None),
        patch.object(svc, "_file_image_service", None),
        patch.object(svc, "_model_selector", None),
    ):
        ready, reasons = svc.readiness_state()
        assert ready is False
        assert "server_config_uninitialized" in reasons
