"""Integration tests for intent memory API endpoints."""

import pytest
from fastapi import FastAPI, testclient

import app.config as config_module
import app.services.intent_memory as intent_memory_service
from app.api.intent_memory import router as intent_memory_router
from app.services.intent_memory import get_intent_memory_store


@pytest.fixture
def intent_memory_app(tmp_path, monkeypatch):
    """Create a test FastAPI app with intent memory router."""
    monkeypatch.setenv("INTENT_MEMORY_PATH", str(tmp_path))
    config_module._settings = None
    intent_memory_service._intent_memory_store = None

    app = FastAPI()
    app.include_router(intent_memory_router)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(intent_memory_app) -> testclient.TestClient:
    """Create test client for intent memory endpoints."""
    return testclient.TestClient(intent_memory_app)


def test_list_update_delete_entries(client: testclient.TestClient) -> None:
    """List, update, and delete intent memory entries."""
    store = get_intent_memory_store()
    result = store.record_explicit_rule(
        user_id="default_user",
        text="When I say weekly sync, route to /plan",
    )
    assert result is not None
    entry_id = result.entry.entry_id

    list_response = client.get("/api/intent-memory/entries")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["count"] == 1
    assert list_data["entries"][0]["entry_id"] == entry_id

    update_payload = {
        "trigger": "weekly sync check",
        "confidence": 0.9,
        "enabled": False,
        "description": "Updated rule",
    }
    update_response = client.put(
        f"/api/intent-memory/entries/{entry_id}", json=update_payload
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["trigger"] == "weekly sync check"
    assert updated["confidence"] == 0.9
    assert updated["enabled"] is False
    assert updated["description"] == "Updated rule"

    delete_response = client.delete(f"/api/intent-memory/entries/{entry_id}")
    assert delete_response.status_code == 204

    after_delete = client.get("/api/intent-memory/entries")
    assert after_delete.status_code == 200
    assert after_delete.json()["count"] == 0


def test_settings_round_trip(client: testclient.TestClient) -> None:
    """Update settings and verify they persist."""
    response = client.get("/api/intent-memory/settings")
    assert response.status_code == 200
    settings = response.json()
    assert settings["auto_confirm_enabled"] is True

    update_payload = {
        "auto_confirm_enabled": False,
        "auto_confirm_threshold": 0.9,
        "auto_confirm_min_samples": 5,
    }
    update_response = client.put("/api/intent-memory/settings", json=update_payload)
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["auto_confirm_enabled"] is False
    assert updated["auto_confirm_threshold"] == 0.9
    assert updated["auto_confirm_min_samples"] == 5

    reload_response = client.get("/api/intent-memory/settings")
    assert reload_response.status_code == 200
    reloaded = reload_response.json()
    assert reloaded["auto_confirm_enabled"] is False
    assert reloaded["auto_confirm_threshold"] == 0.9


def test_export_import_round_trip(client: testclient.TestClient) -> None:
    """Export entries and import them back."""
    store = get_intent_memory_store()
    result = store.record_explicit_rule(
        user_id="default_user",
        text="When I say status check, classify it as command",
    )
    assert result is not None
    entry_id = result.entry.entry_id

    export_response = client.get("/api/intent-memory/export")
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["count"] == 1

    delete_response = client.delete(f"/api/intent-memory/entries/{entry_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/api/intent-memory/entries")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 0

    import_response = client.post(
        "/api/intent-memory/import",
        json={"entries": export_payload["entries"]},
    )
    assert import_response.status_code == 200
    assert import_response.json()["imported"] == 1

    final_list = client.get("/api/intent-memory/entries")
    assert final_list.status_code == 200
    assert final_list.json()["count"] == 1
