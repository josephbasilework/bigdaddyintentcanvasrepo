"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Capability = {
  id: string;
  name: string;
  type: "tool" | "resource" | "prompt";
  server_id: string;
  description?: string | null;
  category?: string | null;
  security_level: "allowed" | "requires_confirm" | "blocked";
  server_name?: string | null;
  server_enabled: boolean;
  input_schema?: Record<string, unknown> | null;
  uri?: string | null;
  mime_type?: string | null;
  arguments?: Array<Record<string, unknown>>;
  usage_count?: number;
  last_used?: string | null;
};

type CapabilityStats = {
  total_capabilities: number;
  total_tools: number;
  total_resources: number;
  total_prompts: number;
  total_servers: number;
  enabled_servers: number;
  by_security_level: Record<string, number>;
  by_category: Record<string, number>;
  by_server: Record<string, number>;
};

type UnavailableCapability = {
  capability: Capability;
  reason: string;
  can_be_enabled: boolean;
  how_to_enable?: string | null;
};

type IntegrationStatus = {
  server_id: string;
  name: string;
  description?: string | null;
  enabled: boolean;
  version?: string | null;
  capabilities: {
    tools: number;
    resources: number;
    prompts: number;
    blocked: number;
  };
  rate_limit: number;
  created_at: string;
  updated_at: string;
};

type CapabilityBrowserProps = {
  id?: string;
};

export function CapabilityBrowser({ id = "capability-browser" }: CapabilityBrowserProps) {
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [stats, setStats] = useState<CapabilityStats | null>(null);
  const [unavailable, setUnavailable] = useState<UnavailableCapability[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [securityFilter, setSecurityFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [serverFilter, setServerFilter] = useState<string>("");
  const [includeDisabled, setIncludeDisabled] = useState<boolean>(false);

  // View mode
  const [viewMode, setViewMode] = useState<"capabilities" | "integrations" | "unavailable">(
    "capabilities"
  );

  // Action check
  const [actionQuery, setActionQuery] = useState<string>("");
  const [actionResult, setActionResult] = useState<{
    possible: boolean;
    capabilities: Capability[];
    blocked_reason?: string | null;
    blocked_capabilities?: Capability[];
  } | null>(null);

  const fetchCapabilities = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.set("query", searchQuery);
      if (typeFilter) params.set("type", typeFilter);
      if (securityFilter) params.set("security_level", securityFilter);
      if (categoryFilter) params.set("category", categoryFilter);
      if (serverFilter) params.set("server_id", serverFilter);
      if (includeDisabled) params.set("include_disabled", "true");

      const response = await fetch(`${API_BASE_URL}/api/mcp/capabilities?${params.toString()}`);
      if (!response.ok) {
        throw new Error("Failed to fetch capabilities");
      }
      const data = await response.json();
      setCapabilities(data.capabilities ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch capabilities");
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, typeFilter, securityFilter, categoryFilter, serverFilter, includeDisabled]);

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/mcp/capabilities/stats`);
      if (!response.ok) return;
      const data = await response.json();
      setStats(data);
    } catch {
      // Stats are non-critical
    }
  }, []);

  const fetchUnavailable = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/mcp/capabilities/unavailable`);
      if (!response.ok) return;
      const data = await response.json();
      setUnavailable(data.unavailable ?? []);
    } catch {
      // Unavailable list is non-critical
    }
  }, []);

  const fetchIntegrations = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/mcp/integrations`);
      if (!response.ok) return;
      const data = await response.json();
      setIntegrations(data.integrations ?? []);
    } catch {
      // Integrations list is non-critical
    }
  }, []);

  const checkAction = useCallback(async () => {
    if (!actionQuery.trim()) {
      setActionResult(null);
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/mcp/capabilities/can-perform`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_description: actionQuery }),
      });
      if (!response.ok) return;
      const data = await response.json();
      setActionResult(data);
    } catch {
      // Action check is non-critical
    }
  }, [actionQuery]);

  useEffect(() => {
    fetchCapabilities();
    fetchStats();
    fetchUnavailable();
    fetchIntegrations();
  }, [fetchCapabilities, fetchStats, fetchUnavailable, fetchIntegrations]);

  const uniqueCategories = useMemo(() => {
    const categories = new Set<string>();
    capabilities.forEach((cap) => {
      if (cap.category) categories.add(cap.category);
    });
    return Array.from(categories).sort();
  }, [capabilities]);

  const uniqueServers = useMemo(() => {
    const servers = new Map<string, string>();
    capabilities.forEach((cap) => {
      if (cap.server_id && cap.server_name) {
        servers.set(cap.server_id, cap.server_name);
      }
    });
    return Array.from(servers.entries());
  }, [capabilities]);

  const getSecurityColor = (level: string): string => {
    switch (level) {
      case "allowed":
        return "#86efac";
      case "requires_confirm":
        return "#facc15";
      case "blocked":
        return "#f87171";
      default:
        return "#94a3b8";
    }
  };

  const getTypeIcon = (type: string): string => {
    switch (type) {
      case "tool":
        return "\u2699"; // gear
      case "resource":
        return "\u{1F4C1}"; // folder
      case "prompt":
        return "\u{1F4DD}"; // memo
      default:
        return "\u2022"; // bullet
    }
  };

  return (
    <section className="cap-browser" id={id} aria-live="polite">
      <header className="cap-browser-header">
        <div>
          <div className="cap-browser-title">Capability Browser</div>
          <div className="cap-browser-subtitle">Explore available integrations and tools</div>
        </div>
        <div className="cap-browser-tabs">
          <button
            type="button"
            className={`cap-tab ${viewMode === "capabilities" ? "active" : ""}`}
            onClick={() => setViewMode("capabilities")}
          >
            Capabilities
          </button>
          <button
            type="button"
            className={`cap-tab ${viewMode === "integrations" ? "active" : ""}`}
            onClick={() => setViewMode("integrations")}
          >
            Integrations
          </button>
          <button
            type="button"
            className={`cap-tab ${viewMode === "unavailable" ? "active" : ""}`}
            onClick={() => setViewMode("unavailable")}
          >
            Unavailable ({unavailable.length})
          </button>
        </div>
      </header>

      <div className="cap-browser-body">
        {isLoading && <div className="cap-state">Loading capabilities...</div>}
        {error && <div className="cap-error">{error}</div>}

        {/* Stats summary */}
        {stats && viewMode === "capabilities" && (
          <div className="cap-stats">
            <div className="cap-stat">
              <span className="cap-stat-value">{stats.total_capabilities}</span>
              <span className="cap-stat-label">Total</span>
            </div>
            <div className="cap-stat">
              <span className="cap-stat-value">{stats.total_tools}</span>
              <span className="cap-stat-label">Tools</span>
            </div>
            <div className="cap-stat">
              <span className="cap-stat-value">{stats.total_resources}</span>
              <span className="cap-stat-label">Resources</span>
            </div>
            <div className="cap-stat">
              <span className="cap-stat-value">{stats.total_prompts}</span>
              <span className="cap-stat-label">Prompts</span>
            </div>
            <div className="cap-stat">
              <span className="cap-stat-value">
                {stats.enabled_servers}/{stats.total_servers}
              </span>
              <span className="cap-stat-label">Servers</span>
            </div>
          </div>
        )}

        {/* Filters - only show for capabilities view */}
        {viewMode === "capabilities" && (
          <div className="cap-filters">
            <input
              type="text"
              className="cap-search"
              placeholder="Search capabilities..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search capabilities"
            />
            <select
              className="cap-filter-select"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter by type"
            >
              <option value="">All types</option>
              <option value="tool">Tools</option>
              <option value="resource">Resources</option>
              <option value="prompt">Prompts</option>
            </select>
            <select
              className="cap-filter-select"
              value={securityFilter}
              onChange={(e) => setSecurityFilter(e.target.value)}
              aria-label="Filter by security level"
            >
              <option value="">All security levels</option>
              <option value="allowed">Allowed</option>
              <option value="requires_confirm">Requires Confirmation</option>
              <option value="blocked">Blocked</option>
            </select>
            <select
              className="cap-filter-select"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              aria-label="Filter by category"
            >
              <option value="">All categories</option>
              {uniqueCategories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
            <select
              className="cap-filter-select"
              value={serverFilter}
              onChange={(e) => setServerFilter(e.target.value)}
              aria-label="Filter by server"
            >
              <option value="">All servers</option>
              {uniqueServers.map(([serverId, serverName]) => (
                <option key={serverId} value={serverId}>
                  {serverName}
                </option>
              ))}
            </select>
            <label className="cap-checkbox">
              <input
                type="checkbox"
                checked={includeDisabled}
                onChange={(e) => setIncludeDisabled(e.target.checked)}
              />
              Include disabled
            </label>
          </div>
        )}

        {/* Action check */}
        {viewMode === "capabilities" && (
          <div className="cap-action-check">
            <div className="cap-action-header">
              <span className="cap-action-title">Can I...?</span>
              <span className="cap-action-subtitle">
                Check if an action is possible with current capabilities
              </span>
            </div>
            <div className="cap-action-input-row">
              <input
                type="text"
                className="cap-action-input"
                placeholder="e.g., create a calendar event"
                value={actionQuery}
                onChange={(e) => setActionQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") checkAction();
                }}
                aria-label="Action description"
              />
              <button type="button" className="cap-action-button" onClick={checkAction}>
                Check
              </button>
            </div>
            {actionResult && (
              <div className={`cap-action-result ${actionResult.possible ? "possible" : "not-possible"}`}>
                {actionResult.possible ? (
                  <>
                    <div className="cap-action-result-header">Yes, possible with:</div>
                    <div className="cap-action-matches">
                      {actionResult.capabilities.map((cap) => (
                        <div key={cap.id} className="cap-action-match">
                          <span className="cap-action-match-icon">{getTypeIcon(cap.type)}</span>
                          <span className="cap-action-match-name">{cap.name}</span>
                          <span className="cap-action-match-server">({cap.server_name})</span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="cap-action-result-header">Not possible</div>
                    <div className="cap-action-reason">{actionResult.blocked_reason}</div>
                    {actionResult.blocked_capabilities && actionResult.blocked_capabilities.length > 0 && (
                      <div className="cap-action-blocked">
                        <div className="cap-action-blocked-label">Blocked capabilities that match:</div>
                        {actionResult.blocked_capabilities.map((cap) => (
                          <div key={cap.id} className="cap-action-match blocked">
                            <span className="cap-action-match-icon">{getTypeIcon(cap.type)}</span>
                            <span className="cap-action-match-name">{cap.name}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* Capabilities list */}
        {viewMode === "capabilities" && (
          <div className="cap-list">
            {capabilities.length === 0 && !isLoading && (
              <div className="cap-state">No capabilities found matching your filters.</div>
            )}
            {capabilities.map((cap) => (
              <div key={cap.id} className={`cap-card ${cap.server_enabled ? "" : "disabled"}`}>
                <div className="cap-card-header">
                  <span className="cap-card-icon">{getTypeIcon(cap.type)}</span>
                  <span className="cap-card-name">{cap.name}</span>
                  <span
                    className="cap-card-security"
                    style={{ color: getSecurityColor(cap.security_level) }}
                  >
                    {cap.security_level}
                  </span>
                </div>
                {cap.description && <div className="cap-card-description">{cap.description}</div>}
                <div className="cap-card-meta">
                  <span className="cap-card-server">{cap.server_name}</span>
                  {cap.category && <span className="cap-card-category">{cap.category}</span>}
                  {!cap.server_enabled && <span className="cap-card-disabled">Server disabled</span>}
                </div>
                {cap.input_schema && Object.keys(cap.input_schema).length > 0 && (
                  <div className="cap-card-schema">
                    <details>
                      <summary>Input schema</summary>
                      <pre>{JSON.stringify(cap.input_schema, null, 2)}</pre>
                    </details>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Integrations view */}
        {viewMode === "integrations" && (
          <div className="cap-integrations">
            {integrations.length === 0 && (
              <div className="cap-state">No integrations configured.</div>
            )}
            {integrations.map((integration) => (
              <div
                key={integration.server_id}
                className={`cap-integration ${integration.enabled ? "" : "disabled"}`}
              >
                <div className="cap-integration-header">
                  <span className="cap-integration-name">{integration.name}</span>
                  <span className={`cap-integration-status ${integration.enabled ? "enabled" : "disabled"}`}>
                    {integration.enabled ? "Enabled" : "Disabled"}
                  </span>
                </div>
                {integration.description && (
                  <div className="cap-integration-description">{integration.description}</div>
                )}
                <div className="cap-integration-caps">
                  <span>{integration.capabilities.tools} tools</span>
                  <span>{integration.capabilities.resources} resources</span>
                  <span>{integration.capabilities.prompts} prompts</span>
                  {integration.capabilities.blocked > 0 && (
                    <span className="blocked">{integration.capabilities.blocked} blocked</span>
                  )}
                </div>
                <div className="cap-integration-meta">
                  {integration.version && <span>v{integration.version}</span>}
                  <span>Rate limit: {integration.rate_limit}/min</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Unavailable view */}
        {viewMode === "unavailable" && (
          <div className="cap-unavailable-list">
            {unavailable.length === 0 && (
              <div className="cap-state">All capabilities are available.</div>
            )}
            {unavailable.map((item) => (
              <div key={item.capability.id} className="cap-unavailable-card">
                <div className="cap-unavailable-header">
                  <span className="cap-card-icon">{getTypeIcon(item.capability.type)}</span>
                  <span className="cap-card-name">{item.capability.name}</span>
                </div>
                <div className="cap-unavailable-reason">{item.reason}</div>
                {item.can_be_enabled && item.how_to_enable && (
                  <div className="cap-unavailable-howto">
                    <span className="howto-label">How to enable:</span>
                    <code>{item.how_to_enable}</code>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <style jsx>{`
        .cap-browser {
          border-radius: 0.9rem;
          border: 1px solid #1f2937;
          background: linear-gradient(180deg, #0f172a 0%, #0b1120 100%);
          color: #e2e8f0;
          box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45);
          overflow: hidden;
        }

        .cap-browser-header {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
          padding: 0.85rem 1rem 0.75rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.85);
        }

        .cap-browser-title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: #94a3b8;
        }

        .cap-browser-subtitle {
          font-size: 0.85rem;
          color: #e2e8f0;
        }

        .cap-browser-tabs {
          display: flex;
          gap: 0.5rem;
        }

        .cap-tab {
          padding: 0.4rem 0.75rem;
          border-radius: 0.4rem;
          border: 1px solid rgba(148, 163, 184, 0.3);
          background: transparent;
          color: #94a3b8;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .cap-tab:hover {
          border-color: rgba(148, 163, 184, 0.5);
          color: #e2e8f0;
        }

        .cap-tab.active {
          border-color: rgba(14, 116, 144, 0.8);
          background: rgba(14, 116, 144, 0.2);
          color: #e2e8f0;
        }

        .cap-browser-body {
          padding: 0.85rem 1rem 1rem;
          max-height: min(65vh, 600px);
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 0.85rem;
        }

        .cap-state {
          font-size: 0.85rem;
          color: #94a3b8;
          padding: 0.75rem;
          text-align: center;
        }

        .cap-error {
          font-size: 0.85rem;
          color: #fca5a5;
          background: rgba(127, 29, 29, 0.35);
          border: 1px solid rgba(239, 68, 68, 0.4);
          padding: 0.5rem 0.65rem;
          border-radius: 0.5rem;
        }

        .cap-stats {
          display: flex;
          gap: 0.75rem;
          flex-wrap: wrap;
        }

        .cap-stat {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 0.5rem 0.75rem;
          border-radius: 0.5rem;
          background: rgba(15, 23, 42, 0.6);
          border: 1px solid rgba(148, 163, 184, 0.2);
          min-width: 60px;
        }

        .cap-stat-value {
          font-size: 1.1rem;
          font-weight: 600;
          color: #e2e8f0;
        }

        .cap-stat-label {
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #94a3b8;
        }

        .cap-filters {
          display: flex;
          gap: 0.5rem;
          flex-wrap: wrap;
          align-items: center;
        }

        .cap-search {
          flex: 1;
          min-width: 150px;
          padding: 0.45rem 0.6rem;
          border-radius: 0.45rem;
          border: 1px solid rgba(148, 163, 184, 0.3);
          background: rgba(15, 23, 42, 0.6);
          color: #e2e8f0;
          font-size: 0.85rem;
        }

        .cap-filter-select {
          padding: 0.45rem 0.6rem;
          border-radius: 0.45rem;
          border: 1px solid rgba(148, 163, 184, 0.3);
          background: rgba(15, 23, 42, 0.6);
          color: #e2e8f0;
          font-size: 0.8rem;
        }

        .cap-checkbox {
          display: flex;
          align-items: center;
          gap: 0.35rem;
          font-size: 0.8rem;
          color: #cbd5f5;
          cursor: pointer;
        }

        .cap-action-check {
          padding: 0.75rem;
          border-radius: 0.6rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.5);
        }

        .cap-action-header {
          margin-bottom: 0.5rem;
        }

        .cap-action-title {
          font-size: 0.85rem;
          font-weight: 600;
          color: #e2e8f0;
        }

        .cap-action-subtitle {
          font-size: 0.75rem;
          color: #94a3b8;
          margin-left: 0.5rem;
        }

        .cap-action-input-row {
          display: flex;
          gap: 0.5rem;
        }

        .cap-action-input {
          flex: 1;
          padding: 0.45rem 0.6rem;
          border-radius: 0.45rem;
          border: 1px solid rgba(148, 163, 184, 0.3);
          background: rgba(15, 23, 42, 0.6);
          color: #e2e8f0;
          font-size: 0.85rem;
        }

        .cap-action-button {
          padding: 0.45rem 0.75rem;
          border-radius: 0.45rem;
          border: 1px solid rgba(14, 116, 144, 0.6);
          background: rgba(14, 116, 144, 0.2);
          color: #e2e8f0;
          font-size: 0.8rem;
          cursor: pointer;
        }

        .cap-action-result {
          margin-top: 0.75rem;
          padding: 0.6rem;
          border-radius: 0.5rem;
        }

        .cap-action-result.possible {
          background: rgba(22, 101, 52, 0.2);
          border: 1px solid rgba(34, 197, 94, 0.4);
        }

        .cap-action-result.not-possible {
          background: rgba(127, 29, 29, 0.2);
          border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .cap-action-result-header {
          font-size: 0.85rem;
          font-weight: 600;
          margin-bottom: 0.4rem;
        }

        .cap-action-matches {
          display: flex;
          flex-direction: column;
          gap: 0.3rem;
        }

        .cap-action-match {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          font-size: 0.8rem;
        }

        .cap-action-match.blocked {
          color: #fca5a5;
        }

        .cap-action-match-icon {
          font-size: 0.9rem;
        }

        .cap-action-match-name {
          font-weight: 500;
        }

        .cap-action-match-server {
          color: #94a3b8;
          font-size: 0.75rem;
        }

        .cap-action-reason {
          font-size: 0.8rem;
          color: #fca5a5;
        }

        .cap-action-blocked {
          margin-top: 0.5rem;
        }

        .cap-action-blocked-label {
          font-size: 0.75rem;
          color: #94a3b8;
          margin-bottom: 0.3rem;
        }

        .cap-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .cap-card {
          padding: 0.65rem 0.75rem;
          border-radius: 0.55rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.55);
          transition: border-color 0.15s ease;
        }

        .cap-card:hover {
          border-color: rgba(148, 163, 184, 0.4);
        }

        .cap-card.disabled {
          opacity: 0.6;
        }

        .cap-card-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .cap-card-icon {
          font-size: 0.9rem;
        }

        .cap-card-name {
          font-weight: 600;
          font-size: 0.9rem;
          flex: 1;
        }

        .cap-card-security {
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
        }

        .cap-card-description {
          font-size: 0.8rem;
          color: #cbd5f5;
          margin-top: 0.35rem;
        }

        .cap-card-meta {
          display: flex;
          gap: 0.5rem;
          margin-top: 0.35rem;
          font-size: 0.7rem;
        }

        .cap-card-server {
          color: #94a3b8;
        }

        .cap-card-category {
          color: #22d3ee;
          padding: 0.1rem 0.35rem;
          border-radius: 0.25rem;
          background: rgba(34, 211, 238, 0.15);
        }

        .cap-card-disabled {
          color: #facc15;
        }

        .cap-card-schema {
          margin-top: 0.5rem;
        }

        .cap-card-schema summary {
          font-size: 0.75rem;
          color: #94a3b8;
          cursor: pointer;
        }

        .cap-card-schema pre {
          font-size: 0.7rem;
          color: #cbd5f5;
          background: rgba(15, 23, 42, 0.6);
          padding: 0.5rem;
          border-radius: 0.4rem;
          overflow-x: auto;
          margin-top: 0.35rem;
        }

        .cap-integrations {
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
        }

        .cap-integration {
          padding: 0.75rem;
          border-radius: 0.6rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.55);
        }

        .cap-integration.disabled {
          opacity: 0.7;
        }

        .cap-integration-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .cap-integration-name {
          font-weight: 600;
          font-size: 0.95rem;
        }

        .cap-integration-status {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          padding: 0.15rem 0.4rem;
          border-radius: 0.3rem;
        }

        .cap-integration-status.enabled {
          color: #86efac;
          background: rgba(34, 197, 94, 0.15);
        }

        .cap-integration-status.disabled {
          color: #facc15;
          background: rgba(250, 204, 21, 0.15);
        }

        .cap-integration-description {
          font-size: 0.8rem;
          color: #cbd5f5;
          margin-top: 0.35rem;
        }

        .cap-integration-caps {
          display: flex;
          gap: 0.75rem;
          margin-top: 0.5rem;
          font-size: 0.75rem;
          color: #94a3b8;
        }

        .cap-integration-caps .blocked {
          color: #f87171;
        }

        .cap-integration-meta {
          display: flex;
          gap: 0.75rem;
          margin-top: 0.4rem;
          font-size: 0.7rem;
          color: #64748b;
        }

        .cap-unavailable-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .cap-unavailable-card {
          padding: 0.65rem 0.75rem;
          border-radius: 0.55rem;
          border: 1px solid rgba(239, 68, 68, 0.3);
          background: rgba(127, 29, 29, 0.15);
        }

        .cap-unavailable-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .cap-unavailable-reason {
          font-size: 0.8rem;
          color: #fca5a5;
          margin-top: 0.35rem;
        }

        .cap-unavailable-howto {
          margin-top: 0.5rem;
          font-size: 0.75rem;
        }

        .cap-unavailable-howto .howto-label {
          color: #86efac;
          margin-right: 0.35rem;
        }

        .cap-unavailable-howto code {
          color: #cbd5f5;
          background: rgba(15, 23, 42, 0.6);
          padding: 0.15rem 0.35rem;
          border-radius: 0.25rem;
          font-size: 0.7rem;
        }
      `}</style>
    </section>
  );
}
