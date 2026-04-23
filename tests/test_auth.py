import os
from unittest.mock import MagicMock, patch

from google.auth.exceptions import DefaultCredentialsError
import pytest

from nanobanana_mcp_server.config.settings import (
    AuthMethod,
    GeminiConfig,
    ServerConfig,
    validate_gemini_base_url,
)
from nanobanana_mcp_server.core.exceptions import ADCConfigurationError, AuthenticationError
from nanobanana_mcp_server.services.gemini_client import GeminiClient


class TestAuthConfiguration:
    def test_api_key_auth_requires_api_key(self):
        """API key is required when using api_key auth method."""
        # Ensure no API key is set - also mock load_dotenv to prevent .env loading
        with (
            patch("nanobanana_mcp_server.config.settings.load_dotenv"),
            patch.dict(os.environ, {"NANOBANANA_AUTH_METHOD": "api_key"}, clear=True),
            pytest.raises(ValueError),
        ):
            ServerConfig.from_env()

    def test_vertex_ai_auth_requires_project(self):
        """GCP project ID is required when using vertex_ai auth method."""
        with (
            patch("nanobanana_mcp_server.config.settings.load_dotenv"),
            patch.dict(os.environ, {"NANOBANANA_AUTH_METHOD": "vertex_ai"}, clear=True),
            pytest.raises(ADCConfigurationError),
        ):
            ServerConfig.from_env()

    def test_auto_selects_api_key_when_available(self):
        """Auto mode selects api_key when GEMINI_API_KEY is available."""
        with patch("nanobanana_mcp_server.config.settings.load_dotenv"), patch.dict(
            os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True
        ):
            config = ServerConfig.from_env()
            assert config.auth_method == AuthMethod.API_KEY

    def test_auto_selects_vertex_ai_when_no_api_key(self):
        """Auto mode falls back to vertex_ai when no API key is set."""
        with patch("nanobanana_mcp_server.config.settings.load_dotenv"), patch.dict(
            os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=True
        ):
            config = ServerConfig.from_env()
            assert config.auth_method == AuthMethod.VERTEX_AI

    def test_auto_fails_when_no_auth_configured(self):
        """Auto mode raises error when no auth credentials are configured."""
        with (
            patch("nanobanana_mcp_server.config.settings.load_dotenv"),
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError),
        ):
            ServerConfig.from_env()

    def test_gemini_base_url_whitespace_becomes_none(self):
        """Whitespace-only GEMINI_BASE_URL should be treated as unset."""
        with patch("nanobanana_mcp_server.config.settings.load_dotenv"), patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-key",
                "GEMINI_BASE_URL": "   ",
            },
            clear=True,
        ):
            config = ServerConfig.from_env()
            assert config.gemini_base_url is None

    def test_gemini_base_url_rejects_untrusted_host(self):
        """Only Google API hosts are permitted for GEMINI_BASE_URL."""
        with patch("nanobanana_mcp_server.config.settings.load_dotenv"), patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-key",
                "GEMINI_BASE_URL": "https://evil.example.com/v1",
            },
            clear=True,
        ), pytest.raises(ValueError, match="not allowed"):
            ServerConfig.from_env()

    def test_mask_error_details_defaults_true_for_http_transport(self):
        """HTTP mode should mask internal errors for MCP clients unless overridden."""
        with patch("nanobanana_mcp_server.config.settings.load_dotenv"), patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key", "FASTMCP_TRANSPORT": "http"},
            clear=True,
        ):
            config = ServerConfig.from_env()
            assert config.mask_error_details is True

    def test_mask_error_details_defaults_false_for_stdio(self):
        """stdio (local) keeps full error details unless FASTMCP_MASK_ERRORS is set."""
        with patch("nanobanana_mcp_server.config.settings.load_dotenv"), patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key", "FASTMCP_TRANSPORT": "stdio"},
            clear=True,
        ):
            config = ServerConfig.from_env()
            assert config.mask_error_details is False

    def test_mask_error_details_explicit_false_overrides_http_default(self):
        with patch("nanobanana_mcp_server.config.settings.load_dotenv"), patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-key",
                "FASTMCP_TRANSPORT": "http",
                "FASTMCP_MASK_ERRORS": "false",
            },
            clear=True,
        ):
            config = ServerConfig.from_env()
            assert config.mask_error_details is False


class TestGeminiClientAuth:
    @patch("google.genai.Client")
    def test_api_key_client_creation(self, mock_client_cls):
        """Client is created correctly with API key authentication."""
        config = ServerConfig(gemini_api_key="test-key", auth_method=AuthMethod.API_KEY)
        gemini_config = GeminiConfig()
        client = GeminiClient(config, gemini_config)

        # Access client property to trigger initialization
        _ = client.client

        mock_client_cls.assert_called_with(api_key="test-key")

    @patch("google.genai.Client")
    def test_vertex_ai_client_creation(self, mock_client_cls):
        """Client is created correctly with Vertex AI authentication."""
        config = ServerConfig(
            gemini_api_key=None,
            auth_method=AuthMethod.VERTEX_AI,
            gcp_project_id="test-project",
            gcp_region="us-central1",
        )
        gemini_config = GeminiConfig()
        client = GeminiClient(config, gemini_config)

        # Access client property to trigger initialization
        _ = client.client

        mock_client_cls.assert_called_with(
            vertexai=True, project="test-project", location="us-central1"
        )

    @patch("google.genai.Client")
    def test_vertex_default_credentials_error_becomes_authentication_error(self, mock_client_cls):
        """DefaultCredentialsError must not leak credential material in the raised message."""
        mock_client_cls.side_effect = DefaultCredentialsError(
            'File {"type":"service_account","private_key":"-----BEGIN PRIVATE KEY-----\\nXX\\n-----END PRIVATE KEY-----\\n"} was not found.'
        )
        config = ServerConfig(
            gemini_api_key=None,
            auth_method=AuthMethod.VERTEX_AI,
            gcp_project_id="test-project",
            gcp_region="us-central1",
        )
        client = GeminiClient(config, GeminiConfig())
        with pytest.raises(AuthenticationError) as exc:
            _ = client.client
        text = str(exc.value)
        assert "BEGIN PRIVATE" not in text
        assert "XX" not in text
        assert "REDACTED" in text

    @patch("google.genai.Client")
    def test_api_key_client_creation_with_base_url_uses_http_options(self, mock_client_cls):
        """Custom base URL should be passed via http_options for API key auth."""
        base = "https://generativelanguage.googleapis.com/v1beta?token=secret"
        config = ServerConfig(
            gemini_api_key="test-key",
            auth_method=AuthMethod.API_KEY,
            gemini_base_url=validate_gemini_base_url(base),
        )
        gemini_config = GeminiConfig()
        client = GeminiClient(config, gemini_config)
        client.logger = MagicMock()

        _ = client.client

        mock_client_cls.assert_called_with(
            api_key="test-key",
            http_options={
                "base_url": "https://generativelanguage.googleapis.com/v1beta?token=secret"
            },
        )
        client.logger.info.assert_any_call(
            "Using custom base URL: https://generativelanguage.googleapis.com"
        )
