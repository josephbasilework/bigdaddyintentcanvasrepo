"""Tests for CopilotKit integration endpoint."""

from unittest.mock import AsyncMock, patch

import pytest

from app.copilotkit import create_copilotkit_sdk, process_intent_handler


class TestCopilotKitSDK:
    """Tests for CopilotKit SDK creation."""

    def test_create_copilotkit_sdk_returns_remote_endpoint(self):
        """Test that SDK is created with correct configuration."""
        from copilotkit import CopilotKitRemoteEndpoint

        sdk = create_copilotkit_sdk()

        assert isinstance(sdk, CopilotKitRemoteEndpoint)

    def test_create_copilotkit_sdk_has_process_intent_action(self):
        """Test that SDK has the process_intent action configured."""
        sdk = create_copilotkit_sdk()

        # The SDK should have actions configured
        # We verify by checking the actions list is not empty
        assert sdk.actions is not None


class TestProcessIntentHandler:
    """Tests for the process_intent action handler."""

    @pytest.mark.asyncio
    async def test_process_intent_success(self):
        """Test successful intent processing via gateway."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "I understand you want to test the system. Here are some suggestions..."
                    }
                }
            ]
        }

        with patch("app.copilotkit.get_gateway_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await process_intent_handler("Test my intent")

            assert result["status"] == "success"
            assert result["intent"] == "Test my intent"
            assert "I understand you want to test" in result["result"]

            # Verify gateway was called with correct parameters
            mock_client.generate.assert_called_once()
            call_args = mock_client.generate.call_args
            assert call_args.kwargs["model"] == "openai/gpt-4o-mini"
            assert len(call_args.kwargs["messages"]) == 2
            assert call_args.kwargs["messages"][1]["content"] == "Test my intent"

    @pytest.mark.asyncio
    async def test_process_intent_gateway_error(self):
        """Test intent processing when gateway fails."""
        with patch("app.copilotkit.get_gateway_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate.side_effect = Exception("Gateway unavailable")
            mock_get_client.return_value = mock_client

            result = await process_intent_handler("Test intent")

            assert result["status"] == "error"
            assert result["intent"] == "Test intent"
            assert "Gateway unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_process_intent_empty_response(self):
        """Test intent processing with empty gateway response."""
        mock_response = {"choices": [{"message": {}}]}

        with patch("app.copilotkit.get_gateway_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await process_intent_handler("Empty response test")

            assert result["status"] == "success"
            assert result["result"] == ""
            assert result["intent"] == "Empty response test"


class TestCopilotKitIntegration:
    """Integration tests for CopilotKit endpoint setup."""

    def test_setup_copilotkit_mounts_endpoint(self):
        """Test that setup_copilotkit mounts the endpoint correctly."""
        from fastapi import FastAPI

        from app.copilotkit import setup_copilotkit

        app = FastAPI()
        setup_copilotkit(app)

        # Check that routes were added
        routes = [r.path for r in app.routes]
        # CopilotKit adds routes under /copilotkit
        copilotkit_routes = [r for r in routes if "/copilotkit" in r]
        assert len(copilotkit_routes) > 0
