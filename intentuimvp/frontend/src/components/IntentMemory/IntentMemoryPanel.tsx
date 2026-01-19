"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useCanvasStore } from "@/state/canvasStore";
import type { IntentMemoryEntry, IntentMemorySettings } from "@/types/intentMemory";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SESSION_STORAGE_KEY = "intentui_workspace_session_id";

type IntentMemoryPanelProps = {
  id?: string;
};

type EntryDraft = {
  trigger: string;
  trigger_type: string;
  responseText: string;
  confidence: number;
  enabled: boolean;
  description: string;
};

const SCOPE_LABELS: Record<IntentMemoryEntry["scope"], string> = {
  user: "User",
  workspace: "Workspace",
  session: "Session",
};

const KIND_LABELS: Record<IntentMemoryEntry["kind"], string> = {
  explicit: "Explicit",
  implicit: "Implicit",
  confirmation: "Confirmation",
};

const USAGE_LABELS: Record<IntentMemoryEntry["usage"], string> = {
  classification: "Classify",
  routing: "Route",
  auto_confirm: "Auto-confirm",
  note_suggestion: "Suggest notes",
};

const TRIGGER_TYPE_LABELS: Record<string, string> = {
  exact: "Exact",
  contains: "Contains",
  regex: "Regex",
  similarity: "Similarity",
  category: "Category",
};

const clamp = (value: number, min: number, max: number): number =>
  Math.min(Math.max(value, min), max);

const clipText = (value: string, limit = 140): string => {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (trimmed.length <= limit) return trimmed;
  return `${trimmed.slice(0, limit - 3).trimEnd()}...`;
};

const formatTimestamp = (value?: string | null): string => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const formatResponseSummary = (response: unknown): string => {
  if (response === null || response === undefined) {
    return "No response";
  }
  if (typeof response === "string") {
    return response;
  }
  if (Array.isArray(response)) {
    return response.map((item) => String(item)).join(", ");
  }
  if (typeof response === "object") {
    const record = response as Record<string, unknown>;
    if (typeof record.handler === "string") {
      return `Route to ${record.handler}`;
    }
    if (typeof record.classification === "string") {
      return `Classify as ${record.classification}`;
    }
  }
  try {
    return JSON.stringify(response);
  } catch {
    return "Response available";
  }
};

const formatResponseEditor = (response: unknown): string => {
  if (response === null || response === undefined) {
    return "";
  }
  if (typeof response === "string") {
    return response;
  }
  try {
    return JSON.stringify(response, null, 2);
  } catch {
    return String(response);
  }
};

const parseResponseEditor = (value: string): unknown => {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
};

const normalizeTrigger = (value: string): string =>
  value.toLowerCase().replace(/\s+/g, " ").trim();

const resolveSessionId = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return localStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
};

const buildQuery = (workspaceId: number | null, sessionId: string | null): string => {
  const params = new URLSearchParams();
  if (workspaceId !== null && workspaceId !== undefined) {
    params.set("workspace_id", String(workspaceId));
  }
  if (sessionId) {
    params.set("session_id", sessionId);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
};

export function IntentMemoryPanel({ id = "intent-memory-panel" }: IntentMemoryPanelProps) {
  const workspaceId = useCanvasStore((state) => state.canvasId);
  const [entries, setEntries] = useState<IntentMemoryEntry[]>([]);
  const [settingsDraft, setSettingsDraft] = useState<IntentMemorySettings | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<EntryDraft | null>(null);
  const [scopeFilter, setScopeFilter] = useState<
    "all" | IntentMemoryEntry["scope"]
  >("all");
  const [searchText, setSearchText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSavingEntry, setIsSavingEntry] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const sessionId = useMemo(() => resolveSessionId(), []);
  const query = useMemo(
    () => buildQuery(workspaceId, sessionId),
    [workspaceId, sessionId]
  );

  const fetchAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [entriesResponse, settingsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/intent-memory/entries${query}`),
        fetch(`${API_BASE_URL}/api/intent-memory/settings`),
      ]);
      if (!entriesResponse.ok) {
        throw new Error(`Failed to load entries (${entriesResponse.status})`);
      }
      if (!settingsResponse.ok) {
        throw new Error(`Failed to load settings (${settingsResponse.status})`);
      }
      const entriesPayload = await entriesResponse.json();
      const settingsPayload = (await settingsResponse.json()) as IntentMemorySettings;
      setEntries(entriesPayload.entries ?? []);
      setSettingsDraft(settingsPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load intent memory.");
    } finally {
      setIsLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  const conflicts = useMemo(() => {
    const triggerScopes = new Map<string, Set<string>>();
    entries.forEach((entry) => {
      const key = normalizeTrigger(entry.trigger);
      if (!key) return;
      if (!triggerScopes.has(key)) {
        triggerScopes.set(key, new Set());
      }
      triggerScopes.get(key)?.add(entry.scope);
    });
    const conflictKeys = new Set<string>();
    triggerScopes.forEach((scopes, key) => {
      if (scopes.size > 1) {
        conflictKeys.add(key);
      }
    });
    return conflictKeys;
  }, [entries]);

  const filteredEntries = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    return entries.filter((entry) => {
      if (scopeFilter !== "all" && entry.scope !== scopeFilter) {
        return false;
      }
      if (!term) return true;
      const responseText = formatResponseSummary(entry.response).toLowerCase();
      return (
        entry.trigger.toLowerCase().includes(term) ||
        responseText.includes(term) ||
        entry.usage.toLowerCase().includes(term) ||
        entry.kind.toLowerCase().includes(term)
      );
    });
  }, [entries, scopeFilter, searchText]);

  const totalConflicts = conflicts.size;

  const startEditing = (entry: IntentMemoryEntry) => {
    setEditingId(entry.entry_id);
    setDraft({
      trigger: entry.trigger,
      trigger_type: entry.trigger_type,
      responseText: formatResponseEditor(entry.response),
      confidence: entry.confidence,
      enabled: entry.enabled,
      description: entry.description ?? "",
    });
  };

  const cancelEditing = () => {
    setEditingId(null);
    setDraft(null);
  };

  const handleSaveEntry = async (entryId: string) => {
    if (!draft) return;
    const trimmedTrigger = draft.trigger.trim();
    if (!trimmedTrigger) {
      setError("Trigger cannot be empty.");
      return;
    }
    setIsSavingEntry(true);
    setError(null);
    try {
      const payload = {
        trigger: trimmedTrigger,
        trigger_type: draft.trigger_type,
        response: parseResponseEditor(draft.responseText),
        confidence: clamp(draft.confidence, 0, 1),
        enabled: draft.enabled,
        description: draft.description.trim() || null,
      };
      const response = await fetch(
        `${API_BASE_URL}/api/intent-memory/entries/${entryId}${query}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (!response.ok) {
        throw new Error(`Failed to update entry (${response.status})`);
      }
      await fetchAll();
      setStatusMessage("Entry updated.");
      cancelEditing();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update entry.");
    } finally {
      setIsSavingEntry(false);
    }
  };

  const handleDeleteEntry = async (entryId: string) => {
    if (typeof window !== "undefined") {
      const confirmDelete = window.confirm("Delete this intent memory pattern?");
      if (!confirmDelete) return;
    }
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/intent-memory/entries/${entryId}${query}`,
        { method: "DELETE" }
      );
      if (!response.ok) {
        throw new Error(`Failed to delete entry (${response.status})`);
      }
      await fetchAll();
      setStatusMessage("Entry deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete entry.");
    }
  };

  const handleSaveSettings = async () => {
    if (!settingsDraft) return;
    setIsSavingSettings(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/intent-memory/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settingsDraft),
      });
      if (!response.ok) {
        throw new Error(`Failed to update settings (${response.status})`);
      }
      const updated = (await response.json()) as IntentMemorySettings;
      setSettingsDraft(updated);
      setStatusMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update settings.");
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/intent-memory/export${query}`);
      if (!response.ok) {
        throw new Error(`Failed to export (${response.status})`);
      }
      const payload = await response.json();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "intent-memory.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setStatusMessage("Export ready.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleImport = async (file: File | null) => {
    if (!file) return;
    setError(null);
    try {
      const text = await file.text();
      const payload = JSON.parse(text) as { entries?: IntentMemoryEntry[]; settings?: IntentMemorySettings };
      if (!payload || !Array.isArray(payload.entries)) {
        throw new Error("Import file must include entries.");
      }
      const response = await fetch(`${API_BASE_URL}/api/intent-memory/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entries: payload.entries,
          settings: payload.settings ?? undefined,
        }),
      });
      if (!response.ok) {
        throw new Error(`Failed to import (${response.status})`);
      }
      await fetchAll();
      setStatusMessage("Import complete.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import.");
    }
  };

  return (
    <section className="intent-memory-panel" aria-live="polite" id={id}>
      <header className="intent-memory-header">
        <div>
          <h2 className="intent-memory-title">Intent Memory</h2>
          <div className="intent-memory-subtitle">
            Inspect learned patterns and tune auto-confirm behavior.
          </div>
        </div>
        <div className="intent-memory-header-actions">
          <button
            type="button"
            className="intent-memory-action"
            onClick={() => void fetchAll()}
            disabled={isLoading}
          >
            Refresh
          </button>
          <button
            type="button"
            className="intent-memory-action"
            onClick={() => void handleExport()}
            disabled={isExporting}
          >
            {isExporting ? "Exporting..." : "Export"}
          </button>
          <label className="intent-memory-import">
            Import
            <input
              type="file"
              accept="application/json"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                void handleImport(file);
                event.currentTarget.value = "";
              }}
            />
          </label>
        </div>
      </header>

      {error && <div className="intent-memory-error">{error}</div>}
      {statusMessage && !error && (
        <div className="intent-memory-status">{statusMessage}</div>
      )}

      <div className="intent-memory-grid">
        <div className="intent-memory-card">
          <div className="intent-memory-card-header">
            <span className="intent-memory-card-title">Safety and thresholds</span>
            <span className="intent-memory-card-subtitle">
              Resolution order: session &gt; workspace &gt; user
            </span>
          </div>
          {settingsDraft ? (
            <div className="intent-memory-card-body">
              <div className="intent-memory-settings">
                <label className="intent-memory-toggle">
                  <input
                    type="checkbox"
                    checked={settingsDraft.enabled}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? { ...prev, enabled: event.target.checked }
                          : prev
                      )
                    }
                  />
                  Enable intent memory
                </label>
                <label className="intent-memory-toggle">
                  <input
                    type="checkbox"
                    checked={settingsDraft.auto_classify_enabled}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? { ...prev, auto_classify_enabled: event.target.checked }
                          : prev
                      )
                    }
                  />
                  Auto-classify from memory
                </label>
                <label className="intent-memory-toggle">
                  <input
                    type="checkbox"
                    checked={settingsDraft.auto_confirm_enabled}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? { ...prev, auto_confirm_enabled: event.target.checked }
                          : prev
                      )
                    }
                  />
                  Auto-confirm trusted patterns
                </label>
                <label className="intent-memory-toggle">
                  <input
                    type="checkbox"
                    checked={settingsDraft.suggestions_enabled}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? { ...prev, suggestions_enabled: event.target.checked }
                          : prev
                      )
                    }
                  />
                  Suggest notes from memory
                </label>
              </div>
              <div className="intent-memory-note">
                Disable auto-confirm to require confirmation even for trusted patterns.
              </div>
              <div className="intent-memory-thresholds">
                <label>
                  Auto-classify threshold
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={settingsDraft.auto_classify_threshold}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? {
                              ...prev,
                              auto_classify_threshold: clamp(
                                Number(event.target.value),
                                0,
                                1
                              ),
                            }
                          : prev
                      )
                    }
                  />
                </label>
                <label>
                  Auto-confirm threshold
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={settingsDraft.auto_confirm_threshold}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? {
                              ...prev,
                              auto_confirm_threshold: clamp(
                                Number(event.target.value),
                                0,
                                1
                              ),
                            }
                          : prev
                      )
                    }
                  />
                </label>
                <label>
                  Auto-confirm min samples
                  <input
                    type="number"
                    min={1}
                    max={50}
                    step={1}
                    value={settingsDraft.auto_confirm_min_samples}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? {
                              ...prev,
                              auto_confirm_min_samples: Math.max(
                                1,
                                Math.round(Number(event.target.value))
                              ),
                            }
                          : prev
                      )
                    }
                  />
                </label>
                <label>
                  Auto-confirm similarity
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={settingsDraft.auto_confirm_similarity_threshold}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? {
                              ...prev,
                              auto_confirm_similarity_threshold: clamp(
                                Number(event.target.value),
                                0,
                                1
                              ),
                            }
                          : prev
                      )
                    }
                  />
                </label>
                <label>
                  Note suggestion threshold
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={settingsDraft.note_suggestion_threshold}
                    onChange={(event) =>
                      setSettingsDraft((prev) =>
                        prev
                          ? {
                              ...prev,
                              note_suggestion_threshold: clamp(
                                Number(event.target.value),
                                0,
                                1
                              ),
                            }
                          : prev
                      )
                    }
                  />
                </label>
              </div>
              <div className="intent-memory-card-actions">
                <button
                  type="button"
                  className="intent-memory-action"
                  onClick={() => void handleSaveSettings()}
                  disabled={isSavingSettings}
                >
                  {isSavingSettings ? "Saving..." : "Save settings"}
                </button>
              </div>
            </div>
          ) : (
            <div className="intent-memory-card-body">Loading settings...</div>
          )}
        </div>

        <div className="intent-memory-card">
          <div className="intent-memory-card-header">
            <span className="intent-memory-card-title">Patterns</span>
            <span className="intent-memory-card-subtitle">
              {filteredEntries.length} of {entries.length} patterns
            </span>
          </div>
          <div className="intent-memory-card-body">
            <div className="intent-memory-controls">
              <label>
                Scope
                <select
                  value={scopeFilter}
                  onChange={(event) =>
                    setScopeFilter(event.target.value as "all" | IntentMemoryEntry["scope"])
                  }
                >
                  <option value="all">All</option>
                  <option value="user">User</option>
                  <option value="workspace">Workspace</option>
                  <option value="session">Session</option>
                </select>
              </label>
              <label className="intent-memory-search">
                Search
                <input
                  type="text"
                  placeholder="Filter by trigger or response"
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                />
              </label>
              <div className="intent-memory-conflicts">
                Conflicts: {totalConflicts}
              </div>
            </div>

            {isLoading ? (
              <div className="intent-memory-empty">Loading patterns...</div>
            ) : filteredEntries.length === 0 ? (
              <div className="intent-memory-empty">No patterns found.</div>
            ) : (
              <ul className="intent-memory-list">
                {filteredEntries.map((entry) => {
                  const normalized = normalizeTrigger(entry.trigger);
                  const isConflicting = conflicts.has(normalized);
                  const isEditing = editingId === entry.entry_id;
                  return (
                    <li key={entry.entry_id} className="intent-memory-item">
                      <div className="intent-memory-item-header">
                        <div className="intent-memory-item-title">
                          <span>{clipText(entry.trigger, 120)}</span>
                          {!entry.enabled && (
                            <span className="intent-memory-pill muted">Disabled</span>
                          )}
                          {isConflicting && (
                            <span className="intent-memory-pill warning">Conflict</span>
                          )}
                        </div>
                        <div className="intent-memory-item-actions">
                          <button
                            type="button"
                            className="intent-memory-action-link"
                            onClick={() =>
                              isEditing ? cancelEditing() : startEditing(entry)
                            }
                          >
                            {isEditing ? "Close" : "Edit"}
                          </button>
                          <button
                            type="button"
                            className="intent-memory-action-link danger"
                            onClick={() => void handleDeleteEntry(entry.entry_id)}
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                      <div className="intent-memory-item-meta">
                        <span>{SCOPE_LABELS[entry.scope]}</span>
                        <span>{KIND_LABELS[entry.kind]}</span>
                        <span>{USAGE_LABELS[entry.usage]}</span>
                        <span>{TRIGGER_TYPE_LABELS[entry.trigger_type] ?? entry.trigger_type}</span>
                        <span>Confidence {entry.confidence.toFixed(2)}</span>
                      </div>
                      <div className="intent-memory-item-body">
                        <div className="intent-memory-response">
                          {clipText(formatResponseSummary(entry.response), 160)}
                        </div>
                        <div className="intent-memory-stats">
                          <span>Used {entry.stats.total}</span>
                          <span>Accepted {entry.stats.accepted}</span>
                          <span>Rejected {entry.stats.rejected}</span>
                          <span>Last used {formatTimestamp(entry.stats.last_used_at)}</span>
                        </div>
                      </div>
                      {isEditing && draft && (
                        <div className="intent-memory-editor">
                          <label>
                            Trigger
                            <input
                              type="text"
                              value={draft.trigger}
                              onChange={(event) =>
                                setDraft((prev) =>
                                  prev
                                    ? { ...prev, trigger: event.target.value }
                                    : prev
                                )
                              }
                            />
                          </label>
                          <label>
                            Trigger type
                            <select
                              value={draft.trigger_type}
                              onChange={(event) =>
                                setDraft((prev) =>
                                  prev
                                    ? { ...prev, trigger_type: event.target.value }
                                    : prev
                                )
                              }
                            >
                              {Object.entries(TRIGGER_TYPE_LABELS).map(([value, label]) => (
                                <option key={value} value={value}>
                                  {label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Response
                            <textarea
                              rows={4}
                              value={draft.responseText}
                              onChange={(event) =>
                                setDraft((prev) =>
                                  prev
                                    ? { ...prev, responseText: event.target.value }
                                    : prev
                                )
                              }
                            />
                          </label>
                          <div className="intent-memory-editor-row">
                            <label>
                              Confidence
                              <input
                                type="number"
                                min={0}
                                max={1}
                                step={0.01}
                                value={draft.confidence}
                                onChange={(event) =>
                                  setDraft((prev) =>
                                    prev
                                      ? {
                                          ...prev,
                                          confidence: clamp(
                                            Number(event.target.value),
                                            0,
                                            1
                                          ),
                                        }
                                      : prev
                                  )
                                }
                              />
                            </label>
                            <label className="intent-memory-toggle-inline">
                              <input
                                type="checkbox"
                                checked={draft.enabled}
                                onChange={(event) =>
                                  setDraft((prev) =>
                                    prev
                                      ? { ...prev, enabled: event.target.checked }
                                      : prev
                                  )
                                }
                              />
                              Enabled
                            </label>
                          </div>
                          <label>
                            Description
                            <input
                              type="text"
                              value={draft.description}
                              onChange={(event) =>
                                setDraft((prev) =>
                                  prev
                                    ? { ...prev, description: event.target.value }
                                    : prev
                                )
                              }
                            />
                          </label>
                          <div className="intent-memory-editor-actions">
                            <button
                              type="button"
                              className="intent-memory-action"
                              onClick={() => void handleSaveEntry(entry.entry_id)}
                              disabled={isSavingEntry}
                            >
                              {isSavingEntry ? "Saving..." : "Save"}
                            </button>
                            <button
                              type="button"
                              className="intent-memory-action ghost"
                              onClick={cancelEditing}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>

      <style jsx>{`
        .intent-memory-panel {
          background: rgba(15, 23, 42, 0.96);
          border: 1px solid rgba(51, 65, 85, 0.6);
          border-radius: 1rem;
          padding: 1rem;
          color: #e2e8f0;
          box-shadow: 0 18px 36px rgba(15, 23, 42, 0.4);
        }

        .intent-memory-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 1rem;
          margin-bottom: 0.85rem;
        }

        .intent-memory-title {
          margin: 0;
          font-size: 1.05rem;
        }

        .intent-memory-subtitle {
          font-size: 0.8rem;
          color: #94a3b8;
        }

        .intent-memory-header-actions {
          display: flex;
          gap: 0.5rem;
          flex-wrap: wrap;
          align-items: center;
        }

        .intent-memory-action,
        .intent-memory-import {
          border: 1px solid rgba(71, 85, 105, 0.8);
          background: rgba(30, 41, 59, 0.7);
          color: #e2e8f0;
          font-size: 0.75rem;
          padding: 0.35rem 0.7rem;
          border-radius: 0.5rem;
          cursor: pointer;
          transition: all 0.15s ease-in-out;
        }

        .intent-memory-import {
          position: relative;
          overflow: hidden;
        }

        .intent-memory-import input {
          position: absolute;
          inset: 0;
          opacity: 0;
          cursor: pointer;
        }

        .intent-memory-action:hover:not(:disabled),
        .intent-memory-import:hover {
          border-color: #38bdf8;
          color: #e0f2fe;
        }

        .intent-memory-action:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .intent-memory-error {
          padding: 0.5rem 0.75rem;
          background: rgba(127, 29, 29, 0.75);
          border: 1px solid rgba(239, 68, 68, 0.6);
          border-radius: 0.6rem;
          font-size: 0.75rem;
          margin-bottom: 0.75rem;
        }

        .intent-memory-status {
          padding: 0.5rem 0.75rem;
          background: rgba(15, 118, 110, 0.35);
          border: 1px solid rgba(45, 212, 191, 0.5);
          border-radius: 0.6rem;
          font-size: 0.75rem;
          margin-bottom: 0.75rem;
        }

        .intent-memory-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 0.8rem;
        }

        .intent-memory-card {
          border: 1px solid rgba(71, 85, 105, 0.6);
          border-radius: 0.85rem;
          background: rgba(15, 23, 42, 0.7);
          padding: 0.75rem;
        }

        .intent-memory-card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 0.6rem;
        }

        .intent-memory-card-title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: #94a3b8;
        }

        .intent-memory-card-subtitle {
          font-size: 0.7rem;
          color: #cbd5f5;
        }

        .intent-memory-card-body {
          display: flex;
          flex-direction: column;
          gap: 0.7rem;
        }

        .intent-memory-settings,
        .intent-memory-thresholds {
          display: grid;
          gap: 0.5rem;
        }

        .intent-memory-note {
          font-size: 0.7rem;
          color: #cbd5f5;
          padding: 0.4rem 0.6rem;
          border-left: 2px solid rgba(56, 189, 248, 0.6);
          background: rgba(15, 23, 42, 0.6);
          border-radius: 0.5rem;
        }

        .intent-memory-settings label,
        .intent-memory-thresholds label {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
          font-size: 0.75rem;
          color: #e2e8f0;
        }

        .intent-memory-thresholds input {
          padding: 0.35rem;
          border-radius: 0.4rem;
          border: 1px solid rgba(71, 85, 105, 0.7);
          background: rgba(15, 23, 42, 0.8);
          color: #e2e8f0;
        }

        .intent-memory-toggle {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.75rem;
        }

        .intent-memory-card-actions {
          display: flex;
          justify-content: flex-end;
        }

        .intent-memory-controls {
          display: flex;
          flex-wrap: wrap;
          gap: 0.6rem;
          align-items: flex-end;
        }

        .intent-memory-controls label {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
          font-size: 0.7rem;
          color: #94a3b8;
        }

        .intent-memory-controls select,
        .intent-memory-controls input {
          padding: 0.35rem 0.5rem;
          border-radius: 0.4rem;
          border: 1px solid rgba(71, 85, 105, 0.7);
          background: rgba(15, 23, 42, 0.8);
          color: #e2e8f0;
        }

        .intent-memory-search {
          min-width: 200px;
          flex: 1;
        }

        .intent-memory-conflicts {
          font-size: 0.7rem;
          color: #fbbf24;
          padding: 0.35rem 0.6rem;
          border-radius: 999px;
          border: 1px solid rgba(251, 191, 36, 0.4);
          background: rgba(120, 53, 15, 0.3);
        }

        .intent-memory-list {
          list-style: none;
          padding: 0;
          margin: 0;
          display: flex;
          flex-direction: column;
          gap: 0.7rem;
          max-height: 56vh;
          overflow-y: auto;
        }

        .intent-memory-item {
          border: 1px solid rgba(71, 85, 105, 0.6);
          border-radius: 0.8rem;
          padding: 0.65rem;
          background: rgba(2, 6, 23, 0.6);
        }

        .intent-memory-item-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 0.75rem;
        }

        .intent-memory-item-title {
          display: flex;
          flex-wrap: wrap;
          gap: 0.4rem;
          font-size: 0.85rem;
          font-weight: 600;
        }

        .intent-memory-item-actions {
          display: flex;
          gap: 0.4rem;
        }

        .intent-memory-action-link {
          background: none;
          border: none;
          color: #93c5fd;
          font-size: 0.7rem;
          cursor: pointer;
        }

        .intent-memory-action-link.danger {
          color: #fca5a5;
        }

        .intent-memory-item-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          font-size: 0.7rem;
          color: #94a3b8;
          margin-top: 0.45rem;
        }

        .intent-memory-item-body {
          margin-top: 0.5rem;
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
        }

        .intent-memory-response {
          font-size: 0.75rem;
          color: #e2e8f0;
        }

        .intent-memory-stats {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          font-size: 0.65rem;
          color: #94a3b8;
        }

        .intent-memory-pill {
          font-size: 0.65rem;
          padding: 0.15rem 0.45rem;
          border-radius: 999px;
          background: rgba(15, 23, 42, 0.8);
          border: 1px solid rgba(71, 85, 105, 0.7);
          color: #e2e8f0;
        }

        .intent-memory-pill.warning {
          background: rgba(120, 53, 15, 0.35);
          border-color: rgba(251, 191, 36, 0.5);
          color: #fde68a;
        }

        .intent-memory-pill.muted {
          color: #94a3b8;
          border-color: rgba(100, 116, 139, 0.6);
        }

        .intent-memory-editor {
          margin-top: 0.6rem;
          display: grid;
          gap: 0.5rem;
          font-size: 0.7rem;
        }

        .intent-memory-editor label {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
        }

        .intent-memory-editor input,
        .intent-memory-editor textarea,
        .intent-memory-editor select {
          padding: 0.35rem 0.5rem;
          border-radius: 0.4rem;
          border: 1px solid rgba(71, 85, 105, 0.7);
          background: rgba(15, 23, 42, 0.85);
          color: #e2e8f0;
        }

        .intent-memory-editor-row {
          display: flex;
          gap: 0.75rem;
          align-items: flex-end;
        }

        .intent-memory-toggle-inline {
          display: flex;
          align-items: center;
          gap: 0.4rem;
        }

        .intent-memory-editor-actions {
          display: flex;
          gap: 0.5rem;
          justify-content: flex-end;
        }

        .intent-memory-action.ghost {
          background: transparent;
          border-color: rgba(71, 85, 105, 0.5);
          color: #94a3b8;
        }

        .intent-memory-empty {
          font-size: 0.75rem;
          color: #94a3b8;
        }

        @media (max-width: 720px) {
          .intent-memory-header {
            flex-direction: column;
            align-items: flex-start;
          }

          .intent-memory-item-header {
            flex-direction: column;
            align-items: flex-start;
          }

          .intent-memory-item-actions {
            width: 100%;
            justify-content: flex-end;
          }
        }
      `}</style>
    </section>
  );
}
