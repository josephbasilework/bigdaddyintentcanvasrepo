"""Tests for dashboard subscription model and schemas."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.dashboard_subscription import (
    DashboardSubscription,
    DashboardSubscriptionTarget,
)
from app.schemas.dashboard_subscription import (
    DashboardSubscriptionCreateRequest,
    DashboardSubscriptionResponse,
    DashboardSubscriptionUpdateRequest,
)


class DummyValue:
    """Dummy value for config sanitization tests."""

    def __str__(self) -> str:
        return "dummy"


def test_dashboard_subscription_model_config_roundtrip() -> None:
    """Ensure config round-trips and serialization stays stable."""
    subscription = DashboardSubscription(
        id=1,
        canvas_id=10,
        dashboard_node_id=20,
        subscription_target=DashboardSubscriptionTarget.NODE,
        source_id="node-123",
        subscription_config=None,
        is_active=True,
        created_at=datetime(2026, 1, 13, 9, 0, 0),
        updated_at=datetime(2026, 1, 13, 9, 0, 0),
    )

    assert subscription.get_config() == {}
    subscription.config = {"filters": {"status": "ready"}}
    assert subscription.config == {"filters": {"status": "ready"}}

    payload = subscription.to_dict()
    assert payload["subscriptionTarget"] == DashboardSubscriptionTarget.NODE
    assert payload["sourceId"] == "node-123"
    assert payload["config"] == {"filters": {"status": "ready"}}


def test_dashboard_subscription_response_accepts_serialized_payload() -> None:
    """Ensure response schema accepts serialized subscription payload."""
    subscription = DashboardSubscription(
        id=2,
        canvas_id=11,
        dashboard_node_id=21,
        subscription_target=DashboardSubscriptionTarget.WORKSPACE_STATE,
        source_id=None,
        subscription_config=json.dumps({"filters": {"status": "ready"}}),
        is_active=True,
        created_at=datetime(2026, 1, 13, 10, 0, 0),
        updated_at=datetime(2026, 1, 13, 10, 0, 0),
    )

    response = DashboardSubscriptionResponse.model_validate(subscription.to_dict())

    assert response.config == {"filters": {"status": "ready"}}


def test_dashboard_subscription_schema_sanitizes_config() -> None:
    """Ensure subscription config sanitizes unsafe values."""
    payload = DashboardSubscriptionCreateRequest(
        canvas_id=1,
        dashboard_node_id=2,
        subscription_target=DashboardSubscriptionTarget.WORKSPACE_STATE,
        config={
            "filters": {"state": "active", "extra": DummyValue()},
            "items": [1, DummyValue(), {"nested": DummyValue()}],
            7: "skip",  # type: ignore[dict-item]
        },
    )

    assert payload.config is not None
    assert payload.config["filters"]["extra"] == "dummy"
    assert payload.config["items"][1] == "dummy"
    assert payload.config["items"][2]["nested"] == "dummy"
    assert 7 not in payload.config


def test_dashboard_subscription_update_schema_sanitizes_config() -> None:
    """Ensure update schema sanitizes unsafe values."""
    payload = DashboardSubscriptionUpdateRequest(
        config={"filters": {"status": DummyValue()}, "items": [DummyValue()]},
    )

    assert payload.config is not None
    assert payload.config["filters"]["status"] == "dummy"
    assert payload.config["items"][0] == "dummy"


def test_dashboard_subscription_update_schema_rejects_non_dict_config() -> None:
    """Ensure update schema rejects non-dict config values."""
    with pytest.raises(ValidationError):
        DashboardSubscriptionUpdateRequest(config=["not-a-dict"])  # type: ignore[arg-type]
