"""Intent memory inspection and editing endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.services.intent_memory import (
    IntentMemorySettings,
    MemoryEntry,
    MemoryKind,
    MemoryScope,
    MemoryStats,
    MemoryUsage,
    get_intent_memory_store,
)

router = APIRouter()
logger = logging.getLogger(__name__)

TriggerType = Literal["exact", "contains", "regex", "similarity", "category"]


def get_current_user() -> str:
    """Get current user from authentication (MVP default)."""
    return "default_user"


class MemoryStatsResponse(BaseModel):
    """Response model for entry stats."""

    total: int
    accepted: int
    rejected: int
    last_used_at: str | None = None


class MemoryEntryResponse(BaseModel):
    """Response model for an intent memory entry."""

    entry_id: str
    scope: str
    kind: str
    usage: str
    trigger: str
    trigger_type: str
    response: Any = None
    confidence: float
    enabled: bool
    workspace_id: str | None = None
    session_id: str | None = None
    created_at: str
    updated_at: str
    stats: MemoryStatsResponse
    description: str | None = None


class MemoryEntriesResponse(BaseModel):
    """Response model for entry lists."""

    entries: list[MemoryEntryResponse]
    count: int


class IntentMemorySettingsResponse(BaseModel):
    """Response model for intent memory settings."""

    enabled: bool
    auto_classify_enabled: bool
    auto_confirm_enabled: bool
    suggestions_enabled: bool
    auto_classify_threshold: float
    auto_confirm_threshold: float
    auto_confirm_min_samples: int
    auto_confirm_similarity_threshold: float
    note_suggestion_threshold: float


class IntentMemorySettingsUpdateRequest(BaseModel):
    """Request payload for updating intent memory settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    auto_classify_enabled: bool | None = None
    auto_confirm_enabled: bool | None = None
    suggestions_enabled: bool | None = None
    auto_classify_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    auto_confirm_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    auto_confirm_min_samples: int | None = Field(default=None, ge=1, le=50)
    auto_confirm_similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    note_suggestion_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class MemoryEntryUpdateRequest(BaseModel):
    """Request payload for updating an entry."""

    model_config = ConfigDict(extra="forbid")

    trigger: str | None = None
    trigger_type: TriggerType | None = Field(default=None, alias="trigger_type")
    response: Any | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    enabled: bool | None = None
    description: str | None = None


class IntentMemoryStatsImport(BaseModel):
    """Import stats for a memory entry."""

    total: int = 0
    accepted: int = 0
    rejected: int = 0
    last_used_at: str | None = None


class IntentMemoryEntryImport(BaseModel):
    """Import payload for memory entries."""

    entry_id: str | None = None
    scope: MemoryScope
    kind: MemoryKind
    usage: MemoryUsage
    trigger: str
    trigger_type: TriggerType = "contains"
    response: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    enabled: bool = True
    workspace_id: str | None = None
    session_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    stats: IntentMemoryStatsImport | None = None
    description: str | None = None


class IntentMemoryImportRequest(BaseModel):
    """Import payload for intent memory."""

    model_config = ConfigDict(extra="forbid")

    settings: IntentMemorySettingsUpdateRequest | None = None
    entries: list[IntentMemoryEntryImport] = Field(default_factory=list)


class IntentMemoryImportResponse(BaseModel):
    """Response after import."""

    imported: int
    settings: IntentMemorySettingsResponse | None = None


class IntentMemoryExportResponse(BaseModel):
    """Export payload for intent memory."""

    exported_at: str
    count: int
    settings: IntentMemorySettingsResponse
    entries: list[MemoryEntryResponse]


def _entry_to_response(entry: MemoryEntry) -> MemoryEntryResponse:
    return MemoryEntryResponse(
        entry_id=entry.entry_id,
        scope=entry.scope.value,
        kind=entry.kind.value,
        usage=entry.usage.value,
        trigger=entry.trigger,
        trigger_type=entry.trigger_type,
        response=entry.response,
        confidence=entry.confidence,
        enabled=entry.enabled,
        workspace_id=entry.workspace_id,
        session_id=entry.session_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        stats=MemoryStatsResponse(
            total=entry.stats.total,
            accepted=entry.stats.accepted,
            rejected=entry.stats.rejected,
            last_used_at=entry.stats.last_used_at,
        ),
        description=entry.description,
    )


def _settings_to_response(settings: IntentMemorySettings) -> IntentMemorySettingsResponse:
    return IntentMemorySettingsResponse(
        enabled=settings.enabled,
        auto_classify_enabled=settings.auto_classify_enabled,
        auto_confirm_enabled=settings.auto_confirm_enabled,
        suggestions_enabled=settings.suggestions_enabled,
        auto_classify_threshold=settings.auto_classify_threshold,
        auto_confirm_threshold=settings.auto_confirm_threshold,
        auto_confirm_min_samples=settings.auto_confirm_min_samples,
        auto_confirm_similarity_threshold=settings.auto_confirm_similarity_threshold,
        note_suggestion_threshold=settings.note_suggestion_threshold,
    )


def _generate_entry_id(trigger: str) -> str:
    return (
        f"mem-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-"
        f"{abs(hash(trigger)) % 10000}"
    )


def _validate_scope_requirements(entry: IntentMemoryEntryImport) -> None:
    if entry.scope == MemoryScope.WORKSPACE and not entry.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id is required for workspace-scoped entries",
        )
    if entry.scope == MemoryScope.SESSION and not entry.session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id is required for session-scoped entries",
        )


@router.get("/api/intent-memory/entries", response_model=MemoryEntriesResponse)
async def list_entries(
    scope: MemoryScope | None = Query(default=None),
    usage: MemoryUsage | None = Query(default=None),
    kind: MemoryKind | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    workspace_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user),
) -> MemoryEntriesResponse:
    store = get_intent_memory_store()
    entries = store.list_entries(
        user_id=user_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )
    filtered: list[MemoryEntryResponse] = []
    for entry in entries:
        if scope is not None and entry.scope != scope:
            continue
        if usage is not None and entry.usage != usage:
            continue
        if kind is not None and entry.kind != kind:
            continue
        if enabled is not None and entry.enabled != enabled:
            continue
        filtered.append(_entry_to_response(entry))
    filtered.sort(key=lambda item: item.updated_at, reverse=True)
    return MemoryEntriesResponse(entries=filtered, count=len(filtered))


@router.get("/api/intent-memory/settings", response_model=IntentMemorySettingsResponse)
async def get_settings(user_id: str = Depends(get_current_user)) -> IntentMemorySettingsResponse:
    store = get_intent_memory_store()
    settings = store.get_settings(user_id)
    return _settings_to_response(settings)


@router.put("/api/intent-memory/settings", response_model=IntentMemorySettingsResponse)
async def update_settings(
    payload: IntentMemorySettingsUpdateRequest,
    user_id: str = Depends(get_current_user),
) -> IntentMemorySettingsResponse:
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No settings provided",
        )
    store = get_intent_memory_store()
    updated = store.update_settings(user_id, updates)
    return _settings_to_response(updated)


@router.put("/api/intent-memory/entries/{entry_id}", response_model=MemoryEntryResponse)
async def update_entry(
    entry_id: str,
    payload: MemoryEntryUpdateRequest,
    workspace_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user),
) -> MemoryEntryResponse:
    store = get_intent_memory_store()
    entry = store.get_entry(
        user_id=user_id,
        entry_id=entry_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    previous = MemoryEntry(**{**entry.__dict__, "stats": entry.stats})
    updates = payload.model_dump(exclude_unset=True, by_alias=True)
    if not updates:
        return _entry_to_response(entry)
    if "trigger" in updates:
        trigger = updates["trigger"].strip()
        if not trigger:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="trigger cannot be empty",
            )
        entry.trigger = trigger
    if "trigger_type" in updates and updates["trigger_type"] is not None:
        entry.trigger_type = updates["trigger_type"]
    if "response" in updates:
        entry.response = updates["response"]
    if "confidence" in updates and updates["confidence"] is not None:
        entry.confidence = float(updates["confidence"])
    if "enabled" in updates and updates["enabled"] is not None:
        entry.enabled = bool(updates["enabled"])
    if "description" in updates:
        entry.description = updates["description"]
    entry.updated_at = datetime.now(UTC).isoformat()
    store.save_entry(user_id=user_id, entry=entry, previous=previous)
    return _entry_to_response(entry)


@router.delete(
    "/api/intent-memory/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_entry(
    entry_id: str,
    workspace_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user),
) -> None:
    store = get_intent_memory_store()
    entry = store.get_entry(
        user_id=user_id,
        entry_id=entry_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    store.delete_entry(user_id=user_id, entry=entry)


@router.get("/api/intent-memory/export", response_model=IntentMemoryExportResponse)
async def export_intent_memory(
    scope: MemoryScope | None = Query(default=None),
    usage: MemoryUsage | None = Query(default=None),
    kind: MemoryKind | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    workspace_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user),
) -> IntentMemoryExportResponse:
    store = get_intent_memory_store()
    entries = store.list_entries(
        user_id=user_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )
    filtered: list[MemoryEntryResponse] = []
    for entry in entries:
        if scope is not None and entry.scope != scope:
            continue
        if usage is not None and entry.usage != usage:
            continue
        if kind is not None and entry.kind != kind:
            continue
        if enabled is not None and entry.enabled != enabled:
            continue
        filtered.append(_entry_to_response(entry))
    filtered.sort(key=lambda item: item.updated_at, reverse=True)
    return IntentMemoryExportResponse(
        exported_at=datetime.now(UTC).isoformat(),
        count=len(filtered),
        settings=_settings_to_response(store.get_settings(user_id)),
        entries=filtered,
    )


@router.post("/api/intent-memory/import", response_model=IntentMemoryImportResponse)
async def import_intent_memory(
    payload: IntentMemoryImportRequest,
    user_id: str = Depends(get_current_user),
) -> IntentMemoryImportResponse:
    store = get_intent_memory_store()
    updated_settings: IntentMemorySettingsResponse | None = None
    if payload.settings is not None:
        updates = payload.settings.model_dump(exclude_unset=True, exclude_none=True)
        if updates:
            updated_settings = _settings_to_response(store.update_settings(user_id, updates))
    imported = 0
    for entry_payload in payload.entries:
        if not entry_payload.trigger.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="trigger cannot be empty",
            )
        _validate_scope_requirements(entry_payload)
        entry_id = entry_payload.entry_id or _generate_entry_id(entry_payload.trigger)
        created_at = entry_payload.created_at or datetime.now(UTC).isoformat()
        updated_at = entry_payload.updated_at or datetime.now(UTC).isoformat()
        stats_payload = entry_payload.stats or IntentMemoryStatsImport()
        stats = MemoryStats(
            total=stats_payload.total,
            accepted=stats_payload.accepted,
            rejected=stats_payload.rejected,
            last_used_at=stats_payload.last_used_at,
        )
        workspace_id = entry_payload.workspace_id if entry_payload.scope == MemoryScope.WORKSPACE else None
        session_id = entry_payload.session_id if entry_payload.scope == MemoryScope.SESSION else None
        entry = MemoryEntry(
            entry_id=entry_id,
            scope=entry_payload.scope,
            kind=entry_payload.kind,
            usage=entry_payload.usage,
            trigger=entry_payload.trigger.strip(),
            trigger_type=entry_payload.trigger_type,
            response=entry_payload.response,
            confidence=entry_payload.confidence,
            enabled=entry_payload.enabled,
            workspace_id=workspace_id,
            session_id=session_id,
            created_at=created_at,
            updated_at=updated_at,
            stats=stats,
            description=entry_payload.description,
        )
        store.save_entry(user_id=user_id, entry=entry, previous=None)
        imported += 1
    return IntentMemoryImportResponse(imported=imported, settings=updated_settings)
