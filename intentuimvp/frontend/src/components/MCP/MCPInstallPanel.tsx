"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type MCPCredentialField = {
  key: string;
  label: string;
  type: "text" | "json" | "secret";
  description?: string | null;
  env_key: string;
  required: boolean;
};

type MCPOAuthSpec = {
  provider: string;
  scopes: string[];
  documentation_url?: string | null;
};

type MCPCatalogEntry = {
  catalog_id: string;
  server_id: string;
  name: string;
  description?: string | null;
  credential_fields: MCPCredentialField[];
  oauth?: MCPOAuthSpec | null;
  manifest?: Record<string, unknown>;
};

type MCPInstallToolPreview = {
  name: string;
  description?: string | null;
  security_level?: string | null;
  inputSchema?: Record<string, unknown>;
};

type MCPResourcePreview = {
  uri: string;
  name: string;
  description?: string | null;
  mime_type?: string | null;
};

type MCPPromptPreview = {
  name: string;
  description?: string | null;
  arguments?: Array<Record<string, unknown>>;
};

type MCPSecurityCheck = {
  id: string;
  label: string;
  status: "passed" | "pending" | "failed";
  details?: string | null;
  issues?: string[];
  blocking?: boolean;
};

type MCPInstallPreview = {
  server_id: string;
  name: string;
  description?: string | null;
  transport_type: string;
  transport_config: Record<string, unknown>;
  resources: MCPResourcePreview[];
  prompts: MCPPromptPreview[];
  tools: MCPInstallToolPreview[];
  security_rules: Record<string, string>;
  credential_fields: MCPCredentialField[];
  missing_credentials: string[];
  sandbox_issues: string[];
  blocked_tools: string[];
  permission_scopes: string[];
  required_env: string[];
  security_checks: MCPSecurityCheck[];
  oauth?: MCPOAuthSpec | null;
};

type MCPServerSummary = {
  server_id: string;
  name: string;
  enabled: boolean;
};

type MCPInstallResponse = {
  success: boolean;
  requires_confirmation?: boolean;
  review_required?: boolean;
  preview?: MCPInstallPreview;
  error?: string | null;
};

type MCPInstallPanelProps = {
  id?: string;
};

export function MCPInstallPanel({ id = "mcp-install-panel" }: MCPInstallPanelProps) {
  const [catalog, setCatalog] = useState<MCPCatalogEntry[]>([]);
  const [servers, setServers] = useState<MCPServerSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [credentialValues, setCredentialValues] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<MCPInstallPreview | null>(null);
  const [approvedTools, setApprovedTools] = useState<Record<string, boolean>>({});
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const hasBlockingChecks = useMemo(
    () =>
      preview?.security_checks?.some(
        (check) => check.status === "failed" && check.blocking
      ) ?? false,
    [preview]
  );

  const selectedEntry = useMemo(
    () => catalog.find((entry) => entry.catalog_id === selectedId) ?? null,
    [catalog, selectedId]
  );

  const refreshServers = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/mcp/servers?enabled_only=false`);
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as { servers?: MCPServerSummary[] };
      setServers(data.servers ?? []);
    } catch {
      // Ignore server list errors to keep the panel usable.
    }
  }, []);

  const refreshCatalog = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/mcp/catalog`);
      if (!response.ok) {
        throw new Error("Failed to load MCP catalog");
      }
      const data = (await response.json()) as { entries?: MCPCatalogEntry[] };
      setCatalog(data.entries ?? []);
      if (!selectedId && data.entries && data.entries.length > 0) {
        setSelectedId(data.entries[0].catalog_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load MCP catalog");
    } finally {
      setIsLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    refreshCatalog();
    refreshServers();
  }, [refreshCatalog, refreshServers]);

  useEffect(() => {
    setCredentialValues({});
    setPreview(null);
    setApprovedTools({});
    setStatusMessage(null);
    setError(null);
  }, [selectedId]);

  const updateCredential = (envKey: string, value: string) => {
    setCredentialValues((prev) => ({ ...prev, [envKey]: value }));
  };

  const initializeApprovedTools = (tools: MCPInstallToolPreview[]) => {
    const initial: Record<string, boolean> = {};
    tools.forEach((tool) => {
      if (!tool.name) return;
      const isBlocked = tool.security_level === "blocked";
      initial[tool.name] = !isBlocked;
    });
    setApprovedTools(initial);
  };

  const handlePreview = async () => {
    if (!selectedEntry) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/mcp/install`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          catalog_id: selectedEntry.catalog_id,
          credentials: credentialValues,
        }),
      });
      const data = (await response.json()) as MCPInstallResponse;
      if (!response.ok || data.error) {
        throw new Error(data.error || "Failed to preview MCP install");
      }
      if (data.preview) {
        setPreview(data.preview);
        initializeApprovedTools(data.preview.tools ?? []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to preview MCP install");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirm = async () => {
    if (!selectedEntry || !preview) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const approved = Object.entries(approvedTools)
        .filter(([, value]) => value)
        .map(([tool]) => tool);

      const response = await fetch(`${API_BASE_URL}/api/mcp/install`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          catalog_id: selectedEntry.catalog_id,
          credentials: credentialValues,
          approved_tools: approved,
          confirmed: true,
        }),
      });

      const data = (await response.json()) as MCPInstallResponse;
      if (!response.ok || data.error) {
        throw new Error(data.error || "Failed to install MCP");
      }

      if (data.success) {
        const suffix = data.review_required
          ? "Installed in review mode. Enable after approving tools."
          : "Installed and enabled.";
        setStatusMessage(`${selectedEntry.name} MCP ${suffix}`);
        setPreview(null);
        await refreshServers();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to install MCP");
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleApproveAll = (checked: boolean) => {
    if (!preview) return;
    const next: Record<string, boolean> = {};
    preview.tools.forEach((tool) => {
      if (!tool.name) return;
      const isBlocked = tool.security_level === "blocked";
      next[tool.name] = isBlocked ? false : checked;
    });
    setApprovedTools(next);
  };

  return (
    <section className="mcp-panel" id={id} aria-live="polite">
      <header className="mcp-panel-header">
        <div>
          <div className="mcp-panel-title">MCP Setup</div>
          <div className="mcp-panel-subtitle">Install integrations at runtime</div>
        </div>
      </header>
      <div className="mcp-panel-body">
        {isLoading && <div className="mcp-panel-state">Loading catalog...</div>}
        {error && <div className="mcp-panel-error">{error}</div>}
        {statusMessage && <div className="mcp-panel-success">{statusMessage}</div>}

        <div className="mcp-section">
          <div className="mcp-section-title">Available MCPs</div>
          <select
            className="mcp-select"
            value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}
            aria-label="Select an MCP integration"
          >
            {catalog.map((entry) => (
              <option key={entry.catalog_id} value={entry.catalog_id}>
                {entry.name}
              </option>
            ))}
          </select>
          {selectedEntry && (
            <div className="mcp-description">{selectedEntry.description}</div>
          )}
        </div>

        {selectedEntry && (
          <div className="mcp-section">
            <div className="mcp-section-title">Credentials</div>
            {selectedEntry.credential_fields.length === 0 && (
              <div className="mcp-panel-state">No credentials required.</div>
            )}
            {selectedEntry.credential_fields.map((field) => {
              const value = credentialValues[field.env_key] ?? "";
              const inputId = `mcp-credential-${field.env_key}`;
              return (
                <div key={field.env_key} className="mcp-field">
                  <label htmlFor={inputId}>
                    {field.label}
                    {field.required && <span className="mcp-required">Required</span>}
                  </label>
                  {field.type === "json" ? (
                    <textarea
                      id={inputId}
                      value={value}
                      onChange={(event) => updateCredential(field.env_key, event.target.value)}
                      rows={4}
                      placeholder={field.description ?? ""}
                    />
                  ) : (
                    <input
                      id={inputId}
                      type={field.type === "secret" ? "password" : "text"}
                      value={value}
                      onChange={(event) => updateCredential(field.env_key, event.target.value)}
                      placeholder={field.description ?? ""}
                    />
                  )}
                </div>
              );
            })}

            {selectedEntry.oauth && selectedEntry.oauth.scopes.length > 0 && (
              <div className="mcp-oauth">
                <div className="mcp-oauth-title">OAuth scopes</div>
                <ul>
                  {selectedEntry.oauth.scopes.map((scope) => (
                    <li key={scope}>{scope}</li>
                  ))}
                </ul>
              </div>
            )}

            <button
              type="button"
              className="mcp-button"
              onClick={handlePreview}
              disabled={isSubmitting}
            >
              Review install
            </button>
          </div>
        )}

        {preview && (
          <div className="mcp-section">
            <div className="mcp-section-title">Capability review</div>
            {preview.sandbox_issues.length > 0 && (
              <div className="mcp-panel-error">
                Sandbox issues: {preview.sandbox_issues.join(", ")}
              </div>
            )}
            {preview.missing_credentials.length > 0 && (
              <div className="mcp-panel-error">
                Missing credentials: {preview.missing_credentials.join(", ")}
              </div>
            )}
            {hasBlockingChecks && (
              <div className="mcp-panel-error">
                Resolve blocking security issues before confirming install.
              </div>
            )}
            {preview.security_checks.length > 0 && (
              <div className="mcp-subsection">
                <div className="mcp-subsection-title">Security pipeline</div>
                <div className="mcp-security-checks">
                  {preview.security_checks.map((check) => (
                    <div key={check.id} className={`mcp-security-check ${check.status}`}>
                      <div className="mcp-security-check-header">
                        <span className="mcp-security-check-title">{check.label}</span>
                        <span className={`mcp-security-tag ${check.status}`}>
                          {check.status}
                        </span>
                      </div>
                      {check.details && (
                        <div className="mcp-security-check-details">{check.details}</div>
                      )}
                      {check.issues && check.issues.length > 0 && (
                        <ul className="mcp-security-issues">
                          {check.issues.map((issue) => (
                            <li key={issue}>{issue}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="mcp-subsection">
              <div className="mcp-subsection-title">Permissions requested</div>
              {preview.permission_scopes.length === 0 && preview.required_env.length === 0 && (
                <div className="mcp-panel-state">No permission scopes declared.</div>
              )}
              {preview.permission_scopes.length > 0 && (
                <>
                  <div className="mcp-subsection-label">OAuth scopes</div>
                  <ul className="mcp-permissions-list">
                    {preview.permission_scopes.map((scope) => (
                      <li key={scope}>{scope}</li>
                    ))}
                  </ul>
                </>
              )}
              {preview.required_env.length > 0 && (
                <>
                  <div className="mcp-subsection-label">Required environment keys</div>
                  <ul className="mcp-permissions-list">
                    {preview.required_env.map((envKey) => (
                      <li key={envKey}>{envKey}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
            <div className="mcp-subsection">
              <div className="mcp-subsection-title">Tools</div>
              <div className="mcp-approve-all">
                <label>
                  <input
                    type="checkbox"
                    checked={
                      preview.tools.length > 0 &&
                      preview.tools.every(
                        (tool) =>
                          tool.security_level === "blocked" ||
                          approvedTools[tool.name] === true
                      )
                    }
                    onChange={(event) => toggleApproveAll(event.target.checked)}
                  />
                  Approve all non-blocked tools
                </label>
              </div>
              <div className="mcp-tool-list">
                {preview.tools.map((tool) => {
                  const isBlocked = tool.security_level === "blocked";
                  return (
                    <label key={tool.name} className={`mcp-tool ${isBlocked ? "blocked" : ""}`}>
                      <input
                        type="checkbox"
                        disabled={isBlocked}
                        checked={Boolean(approvedTools[tool.name])}
                        onChange={(event) =>
                          setApprovedTools((prev) => ({
                            ...prev,
                            [tool.name]: event.target.checked,
                          }))
                        }
                      />
                      <div>
                        <div className="mcp-tool-name">{tool.name}</div>
                        <div className="mcp-tool-meta">
                          {tool.description ?? "No description"}
                        </div>
                        <div className={`mcp-security ${tool.security_level ?? "unknown"}`}>
                          {tool.security_level ?? "unknown"}
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="mcp-subsection">
              <div className="mcp-subsection-title">Resources</div>
              {preview.resources.length === 0 && (
                <div className="mcp-panel-state">No resources declared.</div>
              )}
              {preview.resources.length > 0 && (
                <div className="mcp-capability-list">
                  {preview.resources.map((resource) => (
                    <div key={resource.uri} className="mcp-capability">
                      <div className="mcp-capability-title">{resource.name}</div>
                      <div className="mcp-capability-meta">{resource.uri}</div>
                      {resource.description && (
                        <div className="mcp-capability-meta">{resource.description}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="mcp-subsection">
              <div className="mcp-subsection-title">Prompts</div>
              {preview.prompts.length === 0 && (
                <div className="mcp-panel-state">No prompts declared.</div>
              )}
              {preview.prompts.length > 0 && (
                <div className="mcp-capability-list">
                  {preview.prompts.map((prompt) => (
                    <div key={prompt.name} className="mcp-capability">
                      <div className="mcp-capability-title">{prompt.name}</div>
                      <div className="mcp-capability-meta">
                        {prompt.description ?? "No description"}
                      </div>
                      {prompt.arguments && prompt.arguments.length > 0 && (
                        <div className="mcp-capability-meta">
                          {prompt.arguments.length} argument(s)
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <button
              type="button"
              className="mcp-button primary"
              onClick={handleConfirm}
              disabled={isSubmitting || hasBlockingChecks}
            >
              Confirm install
            </button>
          </div>
        )}

        <div className="mcp-section">
          <div className="mcp-section-title">Configured MCPs</div>
          {servers.length === 0 && (
            <div className="mcp-panel-state">No MCPs configured yet.</div>
          )}
          {servers.length > 0 && (
            <ul className="mcp-server-list">
              {servers.map((server) => (
                <li key={server.server_id}>
                  <span>{server.name}</span>
                  <span className={server.enabled ? "enabled" : "disabled"}>
                    {server.enabled ? "Enabled" : "Disabled"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <style jsx>{`
        .mcp-panel {
          border-radius: 0.9rem;
          border: 1px solid #1f2937;
          background: linear-gradient(180deg, #0f172a 0%, #0b1120 100%);
          color: #e2e8f0;
          box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45);
          overflow: hidden;
        }

        .mcp-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.85rem 1rem 0.75rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.85);
        }

        .mcp-panel-title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: #94a3b8;
        }

        .mcp-panel-subtitle {
          font-size: 0.85rem;
          color: #e2e8f0;
          margin-top: 0.2rem;
        }

        .mcp-panel-body {
          padding: 0.85rem 1rem 1rem;
          max-height: min(58vh, 520px);
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 0.85rem;
        }

        .mcp-section {
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
          padding: 0.75rem;
          border-radius: 0.6rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.5);
        }

        .mcp-section-title {
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: #94a3b8;
        }

        .mcp-subsection {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          padding: 0.6rem;
          border-radius: 0.55rem;
          border: 1px solid rgba(148, 163, 184, 0.15);
          background: rgba(15, 23, 42, 0.35);
        }

        .mcp-subsection-title {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: #94a3b8;
        }

        .mcp-subsection-label {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #cbd5f5;
        }

        .mcp-select,
        .mcp-field input,
        .mcp-field textarea {
          background: rgba(15, 23, 42, 0.6);
          border: 1px solid rgba(148, 163, 184, 0.3);
          color: #e2e8f0;
          padding: 0.5rem 0.6rem;
          border-radius: 0.45rem;
          font-size: 0.85rem;
        }

        .mcp-select {
          width: 100%;
        }

        .mcp-description {
          font-size: 0.85rem;
          color: #cbd5f5;
        }

        .mcp-field {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
        }

        .mcp-field label {
          font-size: 0.8rem;
          color: #cbd5f5;
          display: flex;
          gap: 0.4rem;
          align-items: center;
        }

        .mcp-required {
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: #facc15;
        }

        .mcp-oauth {
          font-size: 0.75rem;
          color: #cbd5f5;
        }

        .mcp-oauth ul {
          margin: 0.35rem 0 0;
          padding-left: 1.1rem;
        }

        .mcp-panel-state {
          font-size: 0.85rem;
          color: #94a3b8;
        }

        .mcp-panel-error {
          font-size: 0.85rem;
          color: #fca5a5;
          background: rgba(127, 29, 29, 0.35);
          border: 1px solid rgba(239, 68, 68, 0.4);
          padding: 0.5rem 0.65rem;
          border-radius: 0.5rem;
        }

        .mcp-panel-success {
          font-size: 0.85rem;
          color: #bbf7d0;
          background: rgba(22, 101, 52, 0.35);
          border: 1px solid rgba(34, 197, 94, 0.4);
          padding: 0.5rem 0.65rem;
          border-radius: 0.5rem;
        }

        .mcp-button {
          border-radius: 0.5rem;
          border: 1px solid rgba(148, 163, 184, 0.35);
          background: rgba(15, 23, 42, 0.7);
          color: #e2e8f0;
          padding: 0.55rem 0.75rem;
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
        }

        .mcp-button.primary {
          border-color: rgba(14, 116, 144, 0.8);
          background: rgba(14, 116, 144, 0.3);
        }

        .mcp-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .mcp-tool-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .mcp-security-checks {
          display: flex;
          flex-direction: column;
          gap: 0.45rem;
        }

        .mcp-security-check {
          padding: 0.5rem;
          border-radius: 0.45rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.5);
        }

        .mcp-security-check.passed {
          border-color: rgba(34, 197, 94, 0.5);
        }

        .mcp-security-check.pending {
          border-color: rgba(250, 204, 21, 0.5);
        }

        .mcp-security-check.failed {
          border-color: rgba(248, 113, 113, 0.55);
        }

        .mcp-security-check-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 0.5rem;
        }

        .mcp-security-check-title {
          font-size: 0.8rem;
          font-weight: 600;
        }

        .mcp-security-tag {
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          padding: 0.1rem 0.4rem;
          border-radius: 999px;
          border: 1px solid rgba(148, 163, 184, 0.4);
          color: #e2e8f0;
        }

        .mcp-security-tag.passed {
          border-color: rgba(34, 197, 94, 0.6);
          color: #86efac;
        }

        .mcp-security-tag.pending {
          border-color: rgba(250, 204, 21, 0.6);
          color: #fde047;
        }

        .mcp-security-tag.failed {
          border-color: rgba(248, 113, 113, 0.6);
          color: #fecaca;
        }

        .mcp-security-check-details {
          font-size: 0.75rem;
          color: #cbd5f5;
          margin-top: 0.25rem;
        }

        .mcp-security-issues {
          margin: 0.35rem 0 0;
          padding-left: 1rem;
          font-size: 0.75rem;
          color: #fca5a5;
        }

        .mcp-permissions-list {
          margin: 0;
          padding-left: 1rem;
          font-size: 0.8rem;
          color: #cbd5f5;
        }

        .mcp-capability-list {
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
        }

        .mcp-capability {
          padding: 0.45rem 0.55rem;
          border-radius: 0.45rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.55);
        }

        .mcp-capability-title {
          font-size: 0.82rem;
          font-weight: 600;
        }

        .mcp-capability-meta {
          font-size: 0.74rem;
          color: #94a3b8;
        }

        .mcp-tool {
          display: flex;
          gap: 0.5rem;
          align-items: flex-start;
          padding: 0.5rem;
          border-radius: 0.5rem;
          background: rgba(15, 23, 42, 0.6);
          border: 1px solid rgba(148, 163, 184, 0.2);
        }

        .mcp-tool.blocked {
          opacity: 0.7;
        }

        .mcp-tool-name {
          font-weight: 600;
          font-size: 0.85rem;
        }

        .mcp-tool-meta {
          font-size: 0.75rem;
          color: #94a3b8;
        }

        .mcp-security {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          margin-top: 0.3rem;
          color: #fbbf24;
        }

        .mcp-security.allowed {
          color: #86efac;
        }

        .mcp-security.requires_confirm {
          color: #facc15;
        }

        .mcp-security.blocked {
          color: #f87171;
        }

        .mcp-server-list {
          list-style: none;
          padding: 0;
          margin: 0;
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
          font-size: 0.85rem;
        }

        .mcp-server-list li {
          display: flex;
          justify-content: space-between;
          padding: 0.45rem 0.55rem;
          border-radius: 0.45rem;
          background: rgba(15, 23, 42, 0.5);
          border: 1px solid rgba(148, 163, 184, 0.2);
        }

        .mcp-server-list .enabled {
          color: #86efac;
        }

        .mcp-server-list .disabled {
          color: #facc15;
        }
      `}</style>
    </section>
  );
}
