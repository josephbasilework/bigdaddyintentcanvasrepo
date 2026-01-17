"""CopilotKit integration for Intent Canvas.

Provides the /copilotkit endpoint for CopilotKit frontend integration.
Actions route through the Gateway client per EI-001 (Gateway-only constraint).

Implements PRD Section 9.3 EI-004: CopilotKit Integration.
"""

import logging
import os
from typing import Any

from copilotkit import Action as CopilotAction
from copilotkit import CopilotKitRemoteEndpoint
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from fastapi import FastAPI

from app.gateway.client import get_gateway_client

logger = logging.getLogger(__name__)

# Use same model as agents, configurable via env var (model name only)
DEFAULT_GATEWAY_MODEL = os.getenv("GATEWAY_MODEL", "gemini-3-flash-preview")


async def process_intent_handler(intent: str) -> dict[str, Any]:
    """Process user intent through Intent Canvas via Gateway.

    This action receives user intent from CopilotKit and processes it
    through the Gateway client (EI-001 compliance).

    Args:
        intent: The user's intent text to process.

    Returns:
        dict containing the processed result.
    """
    logger.info(
        "Processing intent via CopilotKit",
        extra={"event": "copilotkit_process_intent", "intent_length": len(intent)},
    )

    try:
        gateway = get_gateway_client()
        response = await gateway.generate(
            model=DEFAULT_GATEWAY_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Intent Canvas, an AI assistant that helps users clarify "
                        "and refine their intentions. Analyze the user's intent and provide "
                        "a structured response with: 1) A clear understanding of the intent, "
                        "2) Any clarifying questions if needed, 3) Suggested next steps."
                    ),
                },
                {"role": "user", "content": intent},
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        # Extract the assistant's response
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        logger.info(
            "Intent processed successfully",
            extra={"event": "copilotkit_intent_processed"},
        )

        return {
            "status": "success",
            "result": content,
            "intent": intent,
        }

    except Exception as e:
        logger.error(
            "Failed to process intent",
            extra={"event": "copilotkit_intent_error", "error": str(e)},
            exc_info=True,
        )
        return {
            "status": "error",
            "error": str(e),
            "intent": intent,
        }


def create_copilotkit_sdk() -> CopilotKitRemoteEndpoint:
    """Create and configure the CopilotKit SDK instance.

    Returns:
        Configured CopilotKitRemoteEndpoint instance.
    """
    process_intent_action = CopilotAction(
        name="process_intent",
        handler=process_intent_handler,
        description="Process user intent through Intent Canvas. Use this to analyze and refine user intentions.",
        parameters=[
            {
                "name": "intent",
                "type": "string",
                "description": "The user's intent or request to process",
                "required": True,
            }
        ],
    )

    sdk = CopilotKitRemoteEndpoint(
        actions=[process_intent_action],
        agents=[],  # Agents can be added when LangGraph/PydanticAI bridge is ready
    )

    logger.info(
        "CopilotKit SDK initialized",
        extra={
            "event": "copilotkit_sdk_init",
            "actions": ["process_intent"],
            "agents": [],
        },
    )

    return sdk


def setup_copilotkit(app: FastAPI) -> None:
    """Set up CopilotKit endpoint on the FastAPI app.

    Mounts the CopilotKit remote endpoint at /copilotkit.

    Args:
        app: The FastAPI application instance.
    """
    sdk = create_copilotkit_sdk()
    add_fastapi_endpoint(app, sdk, "/copilotkit")

    logger.info(
        "CopilotKit endpoint mounted",
        extra={"event": "copilotkit_mounted", "path": "/copilotkit"},
    )
