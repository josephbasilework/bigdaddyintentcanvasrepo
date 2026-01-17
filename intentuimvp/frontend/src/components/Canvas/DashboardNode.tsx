"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import type {
  DashboardSubscriptionSnapshot,
  DashboardSubscriptionTarget,
} from "../../agui/protocol";
import { useDashboardStream } from "../../hooks/useDashboardStream";
import { useCanvasStore, type CanvasNode } from "../../state/canvasStore";
import { SuccessMetricsDashboard } from "./SuccessMetricsDashboard";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const DEFAULT_POLL_INTERVAL = 15000;

interface DashboardNodeProps {
  nodeId?: string;
}

/** Dashboard types supported by the DashboardNode component */
export type DashboardType = "workspace_pulse" | "success_metrics";

type DashboardSourceType = "workspace" | "api" | "websocket" | "mcp";

type DashboardWriteMethod = "POST" | "PUT" | "PATCH";

interface DashboardSourceConfig {
  type: DashboardSourceType;
  endpoint?: string;
  pollIntervalMs?: number;
  mcpServerId?: string;
  mcpToolName?: string;
  mcpArgs?: Record<string, unknown>;
  allowWrite?: boolean;
  writeMethod?: DashboardWriteMethod;
  writePayload?: Record<string, unknown>;
}

interface DashboardSourceFormState {
  type: DashboardSourceType;
  endpoint: string;
  pollIntervalMs: string;
  mcpServerId: string;
  mcpToolName: string;
  mcpArgsJson: string;
  allowWrite: boolean;
  writeMethod: DashboardWriteMethod;
  writePayloadJson: string;
}

/** Get the dashboard type from a node's metadata */
function getDashboardType(node: CanvasNode | undefined): DashboardType {
  const dashboardType = node?.metadata?.dashboardType as string | undefined;
  return dashboardType === "success_metrics" ? "success_metrics" : "workspace_pulse";
}

type CountMap = Record<string, number>;

const formatLabel = (value: string) =>
  value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());

const countBy = <T,>(items: T[], getKey: (item: T) => string): CountMap =>
  items.reduce<CountMap>((acc, item) => {
    const key = getKey(item);
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const normalizeEndpoint = (
  endpoint: string | undefined,
  allowedProtocols: string[]
): string | null => {
  if (!endpoint) return null;
  const trimmed = endpoint.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith("/")) {
    return trimmed;
  }
  try {
    const url = new URL(trimmed);
    if (!allowedProtocols.includes(url.protocol)) {
      return null;
    }
    return url.toString();
  } catch {
    return null;
  }
};

const DEFAULT_DASHBOARD_CONFIG: DashboardSourceConfig = {
  type: "workspace",
  pollIntervalMs: DEFAULT_POLL_INTERVAL,
  allowWrite: false,
  writeMethod: "POST",
};

const coerceDashboardConfig = (node: CanvasNode | undefined): DashboardSourceConfig => {
  if (!node?.metadata || !isRecord(node.metadata)) {
    return DEFAULT_DASHBOARD_CONFIG;
  }

  const candidate =
    (isRecord(node.metadata.dashboardConfig) && node.metadata.dashboardConfig) ||
    (isRecord(node.metadata.dashboard_config) && node.metadata.dashboard_config) ||
    (isRecord(node.metadata.dashboardSource) && node.metadata.dashboardSource) ||
    (isRecord(node.metadata.dashboard_source) && node.metadata.dashboard_source) ||
    null;

  if (!candidate || !isRecord(candidate)) {
    return DEFAULT_DASHBOARD_CONFIG;
  }

  const typeCandidate =
    (typeof candidate.type === "string" && candidate.type) ||
    (typeof candidate.sourceType === "string" && candidate.sourceType) ||
    "workspace";

  const type: DashboardSourceType =
    typeCandidate === "api" || typeCandidate === "websocket" || typeCandidate === "mcp"
      ? typeCandidate
      : "workspace";

  const endpoint =
    (typeof candidate.endpoint === "string" && candidate.endpoint) ||
    (typeof candidate.url === "string" && candidate.url) ||
    (typeof candidate.source === "string" && candidate.source) ||
    undefined;

  const pollIntervalMs =
    (typeof candidate.pollIntervalMs === "number" && candidate.pollIntervalMs) ||
    (typeof candidate.poll_interval_ms === "number" && candidate.poll_interval_ms) ||
    DEFAULT_POLL_INTERVAL;

  const allowWrite =
    (typeof candidate.allowWrite === "boolean" && candidate.allowWrite) ||
    (typeof candidate.allow_write === "boolean" && candidate.allow_write) ||
    false;

  const writeMethodCandidate =
    (typeof candidate.writeMethod === "string" && candidate.writeMethod) ||
    (typeof candidate.write_method === "string" && candidate.write_method) ||
    "POST";

  const writeMethod: DashboardWriteMethod =
    writeMethodCandidate === "PUT" || writeMethodCandidate === "PATCH"
      ? writeMethodCandidate
      : "POST";

  const writePayload =
    (isRecord(candidate.writePayload) && candidate.writePayload) ||
    (isRecord(candidate.write_payload) && candidate.write_payload) ||
    undefined;

  const mcp = isRecord(candidate.mcp) ? candidate.mcp : null;

  const mcpServerId =
    (typeof candidate.mcpServerId === "string" && candidate.mcpServerId) ||
    (typeof candidate.mcp_server_id === "string" && candidate.mcp_server_id) ||
    (mcp && typeof mcp.serverId === "string" && mcp.serverId) ||
    (mcp && typeof mcp.server_id === "string" && mcp.server_id) ||
    undefined;

  const mcpToolName =
    (typeof candidate.mcpToolName === "string" && candidate.mcpToolName) ||
    (typeof candidate.mcp_tool_name === "string" && candidate.mcp_tool_name) ||
    (mcp && typeof mcp.toolName === "string" && mcp.toolName) ||
    (mcp && typeof mcp.tool_name === "string" && mcp.tool_name) ||
    undefined;

  const mcpArgs =
    (isRecord(candidate.mcpArgs) && candidate.mcpArgs) ||
    (isRecord(candidate.mcp_args) && candidate.mcp_args) ||
    (mcp && isRecord(mcp.args) && mcp.args) ||
    undefined;

  return {
    type,
    endpoint,
    pollIntervalMs: Number.isFinite(pollIntervalMs) ? pollIntervalMs : DEFAULT_POLL_INTERVAL,
    allowWrite,
    writeMethod,
    writePayload,
    mcpServerId,
    mcpToolName,
    mcpArgs,
  };
};

const toFormState = (config: DashboardSourceConfig): DashboardSourceFormState => ({
  type: config.type,
  endpoint: config.endpoint ?? "",
  pollIntervalMs: config.pollIntervalMs ? String(config.pollIntervalMs) : "",
  mcpServerId: config.mcpServerId ?? "",
  mcpToolName: config.mcpToolName ?? "",
  mcpArgsJson: config.mcpArgs ? JSON.stringify(config.mcpArgs, null, 2) : "",
  allowWrite: Boolean(config.allowWrite),
  writeMethod: config.writeMethod ?? "POST",
  writePayloadJson: config.writePayload ? JSON.stringify(config.writePayload, null, 2) : "",
});

const parseJsonField = (
  value: string,
  fieldLabel: string
): Record<string, unknown> | undefined => {
  if (!value.trim()) return undefined;
  try {
    const parsed = JSON.parse(value);
    if (!isRecord(parsed)) {
      throw new Error(`${fieldLabel} must be a JSON object`);
    }
    return parsed;
  } catch (error) {
    if (error instanceof Error && error.message.includes("JSON object")) {
      throw error;
    }
    throw new Error(`${fieldLabel} must be valid JSON`);
  }
};

const toConfig = (state: DashboardSourceFormState): DashboardSourceConfig => {
  const pollIntervalValue = state.pollIntervalMs.trim();
  let pollIntervalMs: number | undefined = undefined;
  if (pollIntervalValue.length > 0) {
    const parsed = Number(pollIntervalValue);
    if (!Number.isFinite(parsed) || parsed < 1000) {
      throw new Error("Poll interval must be at least 1000ms");
    }
    pollIntervalMs = parsed;
  }

  const mcpArgs = parseJsonField(state.mcpArgsJson, "MCP args");
  const writePayload = parseJsonField(state.writePayloadJson, "Write payload");

  return {
    type: state.type,
    endpoint: state.endpoint.trim() || undefined,
    pollIntervalMs: pollIntervalMs ?? DEFAULT_POLL_INTERVAL,
    mcpServerId: state.mcpServerId.trim() || undefined,
    mcpToolName: state.mcpToolName.trim() || undefined,
    mcpArgs,
    allowWrite: state.allowWrite,
    writeMethod: state.writeMethod,
    writePayload,
  };
};

type ExternalStatus = "idle" | "connecting" | "connected" | "error";

interface ExternalDataState {
  data: unknown;
  status: ExternalStatus;
  error: string | null;
  lastUpdated: Date | null;
}

const useUpdatePulse = (trigger: Date | null, durationMs = 1400): boolean => {
  const [pulse, setPulse] = useState(false);
  const triggerTime = trigger ? trigger.getTime() : null;

  useEffect(() => {
    if (triggerTime === null) return undefined;
    const startTimer = window.setTimeout(() => setPulse(true), 0);
    const endTimer = window.setTimeout(() => setPulse(false), durationMs);
    return () => {
      window.clearTimeout(startTimer);
      window.clearTimeout(endTimer);
    };
  }, [triggerTime, durationMs]);

  return pulse;
};

const parsePayload = async (response: Response): Promise<unknown> => {
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};

const useExternalDashboardData = (
  config: DashboardSourceConfig,
  enabled: boolean
): ExternalDataState => {
  const [state, setState] = useState<ExternalDataState>({
    data: null,
    status: "idle",
    error: null,
    lastUpdated: null,
  });

  useEffect(() => {
    if (!enabled || config.type === "workspace") {
      const resetTimer = window.setTimeout(
        () =>
          setState({ data: null, status: "idle", error: null, lastUpdated: null }),
        0
      );
      return () => window.clearTimeout(resetTimer);
    }

    let active = true;
    let intervalId: ReturnType<typeof setInterval> | null = null;
    let ws: WebSocket | null = null;
    let abortController: AbortController | null = null;

    const updateStatus = (status: ExternalStatus) => {
      if (!active) return;
      setState((prev) => ({ ...prev, status }));
    };

    const updateError = (message: string) => {
      if (!active) return;
      setState((prev) => ({ ...prev, status: "error", error: message }));
    };

    const updateData = (data: unknown) => {
      if (!active) return;
      setState((prev) => ({
        ...prev,
        data,
        status: "connected",
        error: null,
        lastUpdated: new Date(),
      }));
    };

    const fetchApi = async () => {
      const normalizedEndpoint = normalizeEndpoint(config.endpoint, ["http:", "https:"]);
      if (!normalizedEndpoint) {
        if (config.endpoint && config.endpoint.trim().length > 0) {
          updateError("API endpoint must use http or https");
        } else {
          updateStatus("idle");
        }
        return;
      }
      updateStatus("connecting");
      abortController = new AbortController();
      try {
        const response = await fetch(normalizedEndpoint, {
          signal: abortController.signal,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          updateError(`Request failed (${response.status})`);
          return;
        }
        const payload = await parsePayload(response);
        updateData(payload);
      } catch (error) {
        if (!active) return;
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        updateError(error instanceof Error ? error.message : "Failed to fetch data");
      }
    };

    const fetchMcp = async () => {
      if (!config.mcpToolName) {
        updateStatus("idle");
        return;
      }
      updateStatus("connecting");
      abortController = new AbortController();
      try {
        const response = await fetch(`${API_BASE_URL}/api/mcp/tools/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tool_name: config.mcpToolName,
            arguments: config.mcpArgs ?? {},
            server_id: config.mcpServerId ?? null,
            user_confirmed: false,
          }),
          signal: abortController.signal,
        });
        if (!response.ok) {
          updateError(`MCP request failed (${response.status})`);
          return;
        }
        const payload = (await response.json()) as {
          success?: boolean;
          result?: unknown;
          error?: string | null;
          requires_confirmation?: boolean;
        };
        if (payload.requires_confirmation) {
          updateError("MCP tool requires confirmation before execution");
          return;
        }
        if (payload.success === false) {
          updateError(payload.error ?? "MCP tool execution failed");
          return;
        }
        updateData(payload.result ?? {});
      } catch (error) {
        if (!active) return;
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        updateError(error instanceof Error ? error.message : "Failed to fetch MCP data");
      }
    };

    if (config.type === "api") {
      fetchApi();
      const interval = config.pollIntervalMs ?? DEFAULT_POLL_INTERVAL;
      if (interval > 0) {
        intervalId = window.setInterval(fetchApi, interval);
      }
    } else if (config.type === "mcp") {
      fetchMcp();
      const interval = config.pollIntervalMs ?? DEFAULT_POLL_INTERVAL;
      if (interval > 0) {
        intervalId = window.setInterval(fetchMcp, interval);
      }
    } else if (config.type === "websocket") {
      const normalizedEndpoint = normalizeEndpoint(config.endpoint, ["ws:", "wss:"]);
      if (!normalizedEndpoint) {
        if (config.endpoint && config.endpoint.trim().length > 0) {
          updateError("WebSocket endpoint must use ws or wss");
        } else {
          updateStatus("idle");
        }
        return () => undefined;
      }
      updateStatus("connecting");
      ws = new WebSocket(normalizedEndpoint);
      ws.onopen = () => updateStatus("connected");
      ws.onmessage = (event) => {
        if (!active) return;
        if (typeof event.data === "string") {
          try {
            updateData(JSON.parse(event.data));
            return;
          } catch {
            updateData(event.data);
            return;
          }
        }
        updateData(event.data);
      };
      ws.onerror = () => updateError("WebSocket error");
      ws.onclose = () => updateStatus("idle");
    }

    return () => {
      active = false;
      if (intervalId) {
        window.clearInterval(intervalId);
      }
      if (abortController) {
        abortController.abort();
      }
      if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.close();
      }
    };
  }, [
    enabled,
    config.type,
    config.endpoint,
    config.pollIntervalMs,
    config.mcpServerId,
    config.mcpToolName,
    config.mcpArgs,
  ]);

  return state;
};

const STREAM_TARGETS: Array<{
  key: DashboardSubscriptionTarget;
  label: string;
  accent: string;
}> = [
  { key: "workspace_state", label: "Workspace", accent: "#94a3b8" },
  { key: "node", label: "Node Events", accent: "#38bdf8" },
  { key: "edge", label: "Edge Events", accent: "#facc15" },
  { key: "job", label: "Jobs", accent: "#f97316" },
  { key: "artifact", label: "Artifacts", accent: "#34d399" },
  { key: "tool_output", label: "Tool Output", accent: "#22d3ee" },
];

const resolveSubscriptionTarget = (subscription: DashboardSubscriptionSnapshot): string => {
  const target =
    subscription.target ??
    subscription.subscriptionTarget ??
    subscription.subscription_target;
  if (typeof target === "string" && target.trim().length > 0) {
    return target;
  }
  return "unknown";
};

const resolveSubscriptionSource = (subscription: DashboardSubscriptionSnapshot): string | null => {
  const source = subscription.sourceId ?? subscription.source_id;
  if (typeof source === "string" && source.trim().length > 0) {
    return source;
  }
  return null;
};

const resolveStatusTone = (status: string) => {
  const normalized = status.toLowerCase();
  if (
    ["success", "ok", "healthy", "passed", "running", "online"].some((token) =>
      normalized.includes(token)
    )
  ) {
    return {
      color: "#34d399",
      background: "rgba(16, 185, 129, 0.15)",
      border: "rgba(52, 211, 153, 0.4)",
    };
  }
  if (
    ["error", "failed", "down", "offline", "cancelled"].some((token) =>
      normalized.includes(token)
    )
  ) {
    return {
      color: "#f87171",
      background: "rgba(248, 113, 113, 0.15)",
      border: "rgba(248, 113, 113, 0.4)",
    };
  }
  if (
    ["pending", "queued", "building", "degraded", "warning"].some((token) =>
      normalized.includes(token)
    )
  ) {
    return {
      color: "#fbbf24",
      background: "rgba(251, 191, 36, 0.15)",
      border: "rgba(251, 191, 36, 0.4)",
    };
  }
  return {
    color: "#38bdf8",
    background: "rgba(56, 189, 248, 0.15)",
    border: "rgba(56, 189, 248, 0.4)",
  };
};

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "boolean") return value ? "True" : "False";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.length ? `${value.length} items` : "0 items";
  if (isRecord(value)) return "Object";
  return String(value);
};

const truncateText = (value: string, maxLength = 42): string => {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 3)}...`;
};

const MiniBarChart = ({ values, color }: { values: number[]; color: string }) => {
  if (values.length === 0) {
    return null;
  }
  const safeValues = values.filter((val) => Number.isFinite(val));
  const max = Math.max(...safeValues, 1);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: "4px",
        height: "44px",
        paddingTop: "4px",
      }}
    >
      {safeValues.slice(0, 12).map((value, index) => (
        <div
          key={`bar-${index}`}
          style={{
            width: "6px",
            height: `${Math.max(6, (value / max) * 40)}px`,
            backgroundColor: color,
            borderRadius: "3px",
            opacity: 0.85,
          }}
        />
      ))}
    </div>
  );
};

const DataTable = ({ rows }: { rows: Array<Record<string, unknown>> }) => {
  if (rows.length === 0) return null;
  const columnKeys = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row)))
  ).slice(0, 4);
  return (
    <table
      style={{
        width: "100%",
        fontSize: "10px",
        color: "#e2e8f0",
        borderCollapse: "collapse",
      }}
    >
      <thead>
        <tr>
          {columnKeys.map((key) => (
            <th
              key={key}
              style={{
                textAlign: "left",
                fontWeight: 600,
                color: "#94a3b8",
                padding: "4px 6px",
                borderBottom: "1px solid rgba(148, 163, 184, 0.2)",
              }}
            >
              {formatLabel(key)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.slice(0, 5).map((row, rowIndex) => (
          <tr key={`row-${rowIndex}`}>
            {columnKeys.map((key) => {
          const cellValue = row[key];
              const cellText = truncateText(
                typeof cellValue === "string"
                  ? cellValue
                  : JSON.stringify(cellValue) ?? String(cellValue)
              );
              return (
                <td
                  key={`${rowIndex}-${key}`}
                  style={{
                    padding: "4px 6px",
                    borderTop: "1px solid rgba(148, 163, 184, 0.12)",
                  }}
                >
                  {cellText}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
};

const PulseDot = ({ active, color }: { active: boolean; color: string }) => (
  <span
    style={{
      display: "inline-block",
      width: "6px",
      height: "6px",
      borderRadius: "999px",
      backgroundColor: color,
      boxShadow: active ? `0 0 6px ${color}` : "none",
      transform: active ? "scale(1)" : "scale(0.8)",
      transition: "box-shadow 0.3s ease, transform 0.3s ease",
    }}
  />
);

const renderDashboardData = (data: unknown, emptyMessage: string) => {
  if (data === null || data === undefined) {
    return <div style={{ fontSize: "12px", color: "#64748b" }}>{emptyMessage}</div>;
  }

  if (typeof data === "number") {
    return (
      <div style={{ fontSize: "28px", fontWeight: 600, color: "#e2e8f0" }}>
        {data.toLocaleString()}
      </div>
    );
  }

  if (typeof data === "boolean") {
    const status = data ? "Active" : "Inactive";
    const tone = resolveStatusTone(status);
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
          padding: "6px 10px",
          borderRadius: "999px",
          backgroundColor: tone.background,
          border: `1px solid ${tone.border}`,
          color: tone.color,
          fontSize: "12px",
          fontWeight: 600,
        }}
      >
        {status}
      </div>
    );
  }

  if (typeof data === "string") {
    return (
      <div style={{ fontSize: "12px", color: "#e2e8f0" }}>
        {truncateText(data, 200)}
      </div>
    );
  }

  if (Array.isArray(data)) {
    if (data.every((item) => typeof item === "number")) {
      return <MiniBarChart values={data as number[]} color="#38bdf8" />;
    }
    if (data.every((item) => isRecord(item))) {
      return <DataTable rows={data as Array<Record<string, unknown>>} />;
    }
    return (
      <div style={{ fontSize: "12px", color: "#94a3b8" }}>
        {data.length} entries
      </div>
    );
  }

  if (isRecord(data)) {
    const statusValue =
      (typeof data.status === "string" && data.status) ||
      (typeof data.state === "string" && data.state) ||
      (typeof data.health === "string" && data.health) ||
      (typeof data.result === "string" && data.result) ||
      null;

    const progressValue =
      typeof data.progress === "number"
        ? data.progress
        : typeof data.percent === "number"
          ? data.percent
          : typeof data.percentage === "number"
            ? data.percentage
            : typeof data.completion === "number"
              ? data.completion
              : null;

    const items =
      (Array.isArray(data.items) && data.items) ||
      (Array.isArray(data.rows) && data.rows) ||
      null;

    if (items && items.every((item) => isRecord(item))) {
      return <DataTable rows={items as Array<Record<string, unknown>>} />;
    }

    const metricsSource =
      (isRecord(data.metrics) && data.metrics) ||
      (isRecord(data.counts) && data.counts) ||
      null;

    const metricEntries = metricsSource
      ? Object.entries(metricsSource).filter(([, value]) => typeof value === "number")
      : [];

    const recordEntries = Object.entries(data).filter(
      ([key, value]) =>
        ![
          "metrics",
          "counts",
          "items",
          "rows",
          "status",
          "state",
          "health",
          "result",
          "progress",
          "percent",
          "percentage",
          "completion",
        ].includes(key) &&
        (typeof value === "string" || typeof value === "number" || typeof value === "boolean")
    );

    if (statusValue) {
      const tone = resolveStatusTone(statusValue);
      const progress =
        typeof progressValue === "number"
          ? progressValue <= 1
            ? progressValue * 100
            : progressValue
          : null;
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 10px",
              borderRadius: "999px",
              backgroundColor: tone.background,
              border: `1px solid ${tone.border}`,
              color: tone.color,
              fontSize: "12px",
              fontWeight: 600,
              width: "fit-content",
            }}
          >
            {formatLabel(statusValue)}
          </div>
          {progress !== null && (
            <div>
              <div style={{ fontSize: "10px", color: "#94a3b8", marginBottom: "4px" }}>
                Progress {Math.round(progress)}%
              </div>
              <div
                style={{
                  width: "100%",
                  height: "6px",
                  borderRadius: "999px",
                  backgroundColor: "rgba(148, 163, 184, 0.2)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.min(100, Math.max(0, progress))}%`,
                    height: "100%",
                    backgroundColor: tone.color,
                  }}
                />
              </div>
            </div>
          )}
          {recordEntries.length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "6px" }}>
              {recordEntries.slice(0, 6).map(([key, value]) => (
                <div
                  key={key}
                  style={{
                    backgroundColor: "rgba(15, 23, 42, 0.45)",
                    border: "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: "6px",
                    padding: "6px",
                  }}
                >
                  <div style={{ fontSize: "10px", color: "#94a3b8" }}>{formatLabel(key)}</div>
                  <div style={{ fontSize: "12px", color: "#e2e8f0" }}>
                    {formatValue(value)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (metricEntries.length > 0) {
      const values = metricEntries.map(([, value]) => value as number);
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <MiniBarChart values={values} color="#60a5fa" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "6px" }}>
            {metricEntries.slice(0, 6).map(([key, value]) => (
              <div
                key={key}
                style={{
                  backgroundColor: "rgba(15, 23, 42, 0.45)",
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  borderRadius: "6px",
                  padding: "6px",
                }}
              >
                <div style={{ fontSize: "10px", color: "#94a3b8" }}>{formatLabel(key)}</div>
                <div style={{ fontSize: "12px", color: "#e2e8f0" }}>
                  {formatValue(value)}
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (recordEntries.length > 0) {
      return (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "6px" }}>
          {recordEntries.slice(0, 6).map(([key, value]) => (
            <div
              key={key}
              style={{
                backgroundColor: "rgba(15, 23, 42, 0.45)",
                border: "1px solid rgba(148, 163, 184, 0.2)",
                borderRadius: "6px",
                padding: "6px",
              }}
            >
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>{formatLabel(key)}</div>
              <div style={{ fontSize: "12px", color: "#e2e8f0" }}>{formatValue(value)}</div>
            </div>
          ))}
        </div>
      );
    }
  }

  return (
    <div style={{ fontSize: "11px", color: "#94a3b8", whiteSpace: "pre-wrap" }}>
      {truncateText(JSON.stringify(data, null, 2), 400)}
    </div>
  );
};

export function DashboardNode({ nodeId }: DashboardNodeProps) {
  const nodes = useCanvasStore((state) => state.nodes);
  const edges = useCanvasStore((state) => state.edges);
  const documents = useCanvasStore((state) => state.documents);
  const selectedNodeIds = useCanvasStore((state) => state.selectedNodeIds);
  const selectedNodeId = useCanvasStore((state) => state.selectedNodeId);
  const canvasId = useCanvasStore((state) => state.canvasId);
  const updateNode = useCanvasStore((state) => state.updateNode);

  // Get the current dashboard node to determine its type
  const dashboardNode = useMemo(
    () => (nodeId ? nodes.find((node) => node.id === nodeId) : undefined),
    [nodeId, nodes]
  );

  const dashboardType = useMemo(
    () => getDashboardType(dashboardNode),
    [dashboardNode]
  );

  const dashboardConfig = useMemo(
    () => coerceDashboardConfig(dashboardNode),
    [dashboardNode]
  );

  const [configOpen, setConfigOpen] = useState(false);
  const [configForm, setConfigForm] = useState<DashboardSourceFormState>(() =>
    toFormState(dashboardConfig)
  );
  const [configError, setConfigError] = useState<string | null>(null);
  const [writeStatus, setWriteStatus] = useState<{
    state: "idle" | "sending" | "success" | "error";
    message?: string;
  }>({ state: "idle" });

  useEffect(() => {
    if (!configOpen) {
      setConfigForm(toFormState(dashboardConfig));
      setConfigError(null);
    }
  }, [dashboardConfig, configOpen]);

  // Workspace Pulse dashboard data (compute before conditional return)
  const dashboardNumericId = useMemo(() => {
    if (!nodeId) return null;
    const parsed = Number(nodeId);
    return Number.isFinite(parsed) ? parsed : null;
  }, [nodeId]);

  const streamingEnabled = dashboardNumericId !== null && canvasId !== null;
  const { stats, isConnected, lastUpdate, recentChanges } = useDashboardStream(
    dashboardNumericId,
    canvasId,
    streamingEnabled
  );

  const externalEnabled =
    dashboardType !== "success_metrics" && dashboardConfig.type !== "workspace";
  const externalState = useExternalDashboardData(dashboardConfig, externalEnabled);

  const streamPulse = useUpdatePulse(lastUpdate);
  const externalPulse = useUpdatePulse(externalState.lastUpdated);

  const selectionCount =
    selectedNodeIds.length > 0
      ? selectedNodeIds.length
      : selectedNodeId
        ? 1
        : 0;

  const scopedNodes = useMemo(
    () => (nodeId ? nodes.filter((node) => node.id !== nodeId) : nodes),
    [nodeId, nodes]
  );

  const nodeTypeCounts = useMemo(
    () => countBy(scopedNodes, (node) => node.type),
    [scopedNodes]
  );

  const edgeRelationCounts = useMemo(
    () => countBy(edges, (edge) => edge.relationType ?? "untyped"),
    [edges]
  );

  const dagTasks = useMemo(
    () => scopedNodes.flatMap((node) => node.dagData?.tasks ?? []),
    [scopedNodes]
  );

  const dagStatusCounts = useMemo(() => countBy(dagTasks, (task) => task.status), [dagTasks]);

  const sortedTypeEntries = useMemo(
    () =>
      Object.entries(nodeTypeCounts).sort(([, a], [, b]) => b - a),
    [nodeTypeCounts]
  );

  const sortedRelationEntries = useMemo(
    () =>
      Object.entries(edgeRelationCounts).sort(([, a], [, b]) => b - a),
    [edgeRelationCounts]
  );

  const dagTotals = useMemo(
    () => ({
      total: dagTasks.length,
      pending: dagStatusCounts.pending ?? 0,
      in_progress: dagStatusCounts.in_progress ?? 0,
      completed: dagStatusCounts.completed ?? 0,
      blocked: dagStatusCounts.blocked ?? 0,
    }),
    [dagStatusCounts, dagTasks.length]
  );

  const streamCountEntries = useMemo(
    () =>
      STREAM_TARGETS.map(({ key, label, accent }) => ({
        key,
        label,
        accent,
        value: stats.entityCounts[key] ?? 0,
      })),
    [stats.entityCounts]
  );

  const recentSignals = useMemo(() => recentChanges.slice(0, 4), [recentChanges]);

  const subscriptionBadges = useMemo(
    () =>
      stats.activeSubscriptions.map((subscription, index) => {
        const target = resolveSubscriptionTarget(subscription);
        const sourceId = resolveSubscriptionSource(subscription);
        const label = sourceId
          ? `${formatLabel(target)} · ${sourceId}`
          : formatLabel(target);
        const idPart = subscription.id ? String(subscription.id) : null;
        const key = idPart ? `subscription-${idPart}` : `${target}-${sourceId ?? "all"}-${index}`;
        return { key, label };
      }),
    [stats.activeSubscriptions]
  );

  const streamStatusLabel = streamingEnabled
    ? isConnected
      ? "Connected"
      : "Connecting"
    : "Offline";
  const streamStatusTone = streamingEnabled
    ? isConnected
      ? {
          color: "#34d399",
          background: "rgba(16, 185, 129, 0.15)",
          border: "rgba(52, 211, 153, 0.4)",
        }
      : {
          color: "#fbbf24",
          background: "rgba(245, 158, 11, 0.15)",
          border: "rgba(251, 191, 36, 0.4)",
        }
    : {
        color: "#94a3b8",
        background: "rgba(148, 163, 184, 0.12)",
        border: "rgba(148, 163, 184, 0.35)",
      };
  const streamStatusDetail = streamingEnabled
    ? isConnected
      ? "Subscribed to backend updates."
      : "Awaiting subscription confirmation."
    : canvasId === null
      ? "Save the workspace to enable streaming."
      : "Sync the dashboard to the backend to enable streaming.";
  const lastUpdateLabel = lastUpdate ? lastUpdate.toLocaleTimeString() : "No updates yet";

  const hasExternalSource = dashboardConfig.type !== "workspace";
  const externalStatusLabel = hasExternalSource
    ? externalState.status === "connected"
      ? "Connected"
      : externalState.status === "connecting"
        ? "Connecting"
        : externalState.status === "error"
          ? "Error"
          : "Idle"
    : "Not configured";

  const externalStatusTone = hasExternalSource
    ? externalState.status === "connected"
      ? {
          color: "#34d399",
          background: "rgba(16, 185, 129, 0.15)",
          border: "rgba(52, 211, 153, 0.4)",
        }
      : externalState.status === "connecting"
        ? {
            color: "#fbbf24",
            background: "rgba(245, 158, 11, 0.15)",
            border: "rgba(251, 191, 36, 0.4)",
          }
        : externalState.status === "error"
          ? {
              color: "#f87171",
              background: "rgba(248, 113, 113, 0.15)",
              border: "rgba(248, 113, 113, 0.4)",
            }
          : {
              color: "#94a3b8",
              background: "rgba(148, 163, 184, 0.12)",
              border: "rgba(148, 163, 184, 0.35)",
            }
    : {
        color: "#94a3b8",
        background: "rgba(148, 163, 184, 0.12)",
        border: "rgba(148, 163, 184, 0.35)",
      };

  const externalStatusDetail = hasExternalSource
    ? externalState.status === "connecting"
      ? "Connecting to external source."
      : externalState.status === "error"
        ? "External source reported an error."
        : externalState.status === "connected"
          ? "Receiving external updates."
          : "Awaiting external updates."
    : "Configure a data source to view external state.";

  const externalLastUpdateLabel = hasExternalSource
    ? externalState.lastUpdated
      ? externalState.lastUpdated.toLocaleTimeString()
      : "No updates yet"
    : "Not configured";

  const externalEmptyMessage = hasExternalSource
    ? "No external data yet"
    : "Configure a data source to view external state.";

  const latestPayload = hasExternalSource ? externalState.data : null;

  const sourceSummary = hasExternalSource
    ? dashboardConfig.type === "api"
      ? dashboardConfig.endpoint
        ? `API: ${dashboardConfig.endpoint}`
        : "API endpoint not set"
      : dashboardConfig.type === "websocket"
        ? dashboardConfig.endpoint
          ? `WebSocket: ${dashboardConfig.endpoint}`
          : "WebSocket endpoint not set"
        : dashboardConfig.type === "mcp"
          ? `MCP: ${dashboardConfig.mcpServerId ?? "server"} · ${dashboardConfig.mcpToolName ?? "tool"}`
          : "External source"
    : "No external source configured";

  const pollSummary =
    dashboardConfig.type === "api" || dashboardConfig.type === "mcp"
      ? `Polling every ${Math.round(
          (dashboardConfig.pollIntervalMs ?? DEFAULT_POLL_INTERVAL) / 1000
        )}s`
      : null;

  const handleSaveConfig = useCallback(() => {
    if (!nodeId) return;
    try {
      const nextConfig = toConfig(configForm);
      const currentMetadata = (dashboardNode?.metadata ?? {}) as Record<string, unknown>;
      updateNode(nodeId, {
        metadata: { ...currentMetadata, dashboardConfig: nextConfig },
      });
      setConfigOpen(false);
      setConfigError(null);
    } catch (error) {
      setConfigError(error instanceof Error ? error.message : "Invalid configuration");
    }
  }, [configForm, dashboardNode?.metadata, nodeId, updateNode]);

  const handleWriteBack = useCallback(async () => {
    if (!dashboardConfig.allowWrite) return;
    if (!window.confirm("Send write-back update to external source?")) {
      return;
    }

    setWriteStatus({ state: "sending" });

    try {
      if (dashboardConfig.type === "api") {
        const normalizedEndpoint = normalizeEndpoint(dashboardConfig.endpoint, ["http:", "https:"]);
        if (!normalizedEndpoint) {
          throw new Error("API endpoint is missing or invalid");
        }
        const payload = dashboardConfig.writePayload ?? {};
        const response = await fetch(normalizedEndpoint, {
          method: dashboardConfig.writeMethod ?? "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          throw new Error(`Write-back failed (${response.status})`);
        }
        setWriteStatus({ state: "success", message: "Write-back sent" });
        return;
      }

      if (dashboardConfig.type === "mcp") {
        if (!dashboardConfig.mcpToolName) {
          throw new Error("MCP tool name is required for write-back");
        }
        const response = await fetch(`${API_BASE_URL}/api/mcp/tools/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tool_name: dashboardConfig.mcpToolName,
            arguments: dashboardConfig.writePayload ?? dashboardConfig.mcpArgs ?? {},
            server_id: dashboardConfig.mcpServerId ?? null,
            user_confirmed: true,
          }),
        });
        if (!response.ok) {
          throw new Error(`MCP write-back failed (${response.status})`);
        }
        const payload = (await response.json()) as { success?: boolean; error?: string | null };
        if (payload.success === false) {
          throw new Error(payload.error ?? "MCP write-back failed");
        }
        setWriteStatus({ state: "success", message: "MCP write-back sent" });
        return;
      }

      throw new Error("Write-back is not supported for this source type");
    } catch (error) {
      setWriteStatus({
        state: "error",
        message: error instanceof Error ? error.message : "Write-back failed",
      });
    }
  }, [dashboardConfig]);

  // Render SuccessMetricsDashboard if that's the type (after all hooks are called)
  if (dashboardType === "success_metrics") {
    return (
      <div style={{ color: "#e2e8f0" }}>
        <SuccessMetricsDashboard
          pollInterval={60000}
          enabled={true}
        />
      </div>
    );
  }

  // Otherwise render the Workspace Pulse dashboard (default)
  return (
    <div
      role="region"
      aria-label="Live dashboard"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        color: "#e2e8f0",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: "12px", letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8" }}>
          Workspace Pulse
        </div>
        <div
          style={{
            fontSize: "11px",
            color: "#38bdf8",
            backgroundColor: "rgba(14, 116, 144, 0.25)",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            padding: "2px 8px",
            borderRadius: "999px",
          }}
        >
          Live
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: "8px",
        }}
      >
        {[
          { label: "Nodes", value: scopedNodes.length },
          { label: "Edges", value: edges.length },
          { label: "Docs", value: documents.length },
          { label: "Selected", value: selectionCount },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              backgroundColor: "rgba(15, 23, 42, 0.55)",
              border: "1px solid rgba(148, 163, 184, 0.25)",
              borderRadius: "8px",
              padding: "8px 10px",
            }}
          >
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>{item.label}</div>
            <div style={{ fontSize: "18px", fontWeight: 600 }}>{item.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: "12px", color: "#a0aec0" }}>Streaming Signals</div>
          <div
            style={{
              fontSize: "11px",
              color: streamStatusTone.color,
              backgroundColor: streamStatusTone.background,
              border: `1px solid ${streamStatusTone.border}`,
              padding: "2px 8px",
              borderRadius: "999px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <PulseDot active={streamPulse} color={streamStatusTone.color} />
            {streamStatusLabel}
          </div>
        </div>
        <div style={{ fontSize: "11px", color: "#64748b" }}>{streamStatusDetail}</div>
        <div style={{ fontSize: "10px", color: "#64748b" }}>Last update: {lastUpdateLabel}</div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: "6px",
          }}
        >
          {streamCountEntries.map((entry) => (
            <div
              key={entry.key}
              style={{
                backgroundColor: "rgba(15, 23, 42, 0.5)",
                border: `1px solid ${entry.accent}55`,
                borderRadius: "8px",
                padding: "6px 8px",
              }}
            >
              <div style={{ fontSize: "10px", color: entry.accent }}>{entry.label}</div>
              <div style={{ fontSize: "14px", fontWeight: 600 }}>{entry.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: "12px", color: "#a0aec0" }}>External State</div>
          <button
            type="button"
            onClick={() => setConfigOpen((prev) => !prev)}
            onMouseDown={(event) => event.stopPropagation()}
            onTouchStart={(event) => event.stopPropagation()}
            style={{
              fontSize: "11px",
              color: "#e2e8f0",
              backgroundColor: "rgba(30, 41, 59, 0.6)",
              border: "1px solid rgba(148, 163, 184, 0.3)",
              borderRadius: "999px",
              padding: "2px 8px",
              cursor: "pointer",
            }}
          >
            {configOpen ? "Close" : "Configure"}
          </button>
        </div>

        <div style={{ fontSize: "11px", color: "#64748b" }}>{sourceSummary}</div>
        {pollSummary && (
          <div style={{ fontSize: "10px", color: "#64748b" }}>{pollSummary}</div>
        )}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: "10px", color: "#64748b" }}>
            Last update: {externalLastUpdateLabel}{" "}
            <PulseDot active={externalPulse} color={externalStatusTone.color} />
          </div>
          <div
            style={{
              fontSize: "11px",
              color: externalStatusTone.color,
              backgroundColor: externalStatusTone.background,
              border: `1px solid ${externalStatusTone.border}`,
              padding: "2px 8px",
              borderRadius: "999px",
            }}
          >
            {externalStatusLabel}
          </div>
        </div>
        <div style={{ fontSize: "11px", color: "#64748b" }}>{externalStatusDetail}</div>
        {externalState.error && (
          <div
            style={{
              fontSize: "11px",
              color: "#f87171",
              backgroundColor: "rgba(248, 113, 113, 0.12)",
              border: "1px solid rgba(248, 113, 113, 0.35)",
              borderRadius: "8px",
              padding: "6px 8px",
            }}
          >
            {externalState.error}
          </div>
        )}
        <div
          style={{
            backgroundColor: "rgba(15, 23, 42, 0.55)",
            border: `1px solid ${externalPulse ? "rgba(56, 189, 248, 0.6)" : "rgba(148, 163, 184, 0.25)"}`,
            boxShadow: externalPulse ? "0 0 12px rgba(56, 189, 248, 0.35)" : "none",
            borderRadius: "8px",
            padding: "10px",
            transition: "box-shadow 0.3s ease, border-color 0.3s ease",
          }}
        >
          {renderDashboardData(latestPayload, externalEmptyMessage)}
        </div>

        {dashboardConfig.allowWrite && (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <button
              type="button"
              onClick={handleWriteBack}
              onMouseDown={(event) => event.stopPropagation()}
              onTouchStart={(event) => event.stopPropagation()}
              disabled={writeStatus.state === "sending"}
              style={{
                fontSize: "11px",
                color: "#e2e8f0",
                backgroundColor: "rgba(14, 116, 144, 0.25)",
                border: "1px solid rgba(56, 189, 248, 0.4)",
                borderRadius: "8px",
                padding: "6px 10px",
                cursor: writeStatus.state === "sending" ? "default" : "pointer",
                opacity: writeStatus.state === "sending" ? 0.6 : 1,
                width: "fit-content",
              }}
            >
              {writeStatus.state === "sending" ? "Sending..." : "Write-back"}
            </button>
            {writeStatus.state !== "idle" && writeStatus.message && (
              <div
                style={{
                  fontSize: "11px",
                  color: writeStatus.state === "error" ? "#f87171" : "#34d399",
                }}
              >
                {writeStatus.message}
              </div>
            )}
          </div>
        )}

        {configOpen && (
          <div
            style={{
              border: "1px solid rgba(148, 163, 184, 0.2)",
              borderRadius: "10px",
              padding: "10px",
              backgroundColor: "rgba(15, 23, 42, 0.6)",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}
          >
            <label style={{ fontSize: "11px", color: "#94a3b8" }}>
              Source type
            </label>
            <select
              value={configForm.type}
              onChange={(event) =>
                setConfigForm((prev) => ({
                  ...prev,
                  type: event.target.value as DashboardSourceType,
                }))
              }
              onMouseDown={(event) => event.stopPropagation()}
              onTouchStart={(event) => event.stopPropagation()}
              style={{
                width: "100%",
                padding: "6px 8px",
                borderRadius: "6px",
                border: "1px solid rgba(148, 163, 184, 0.25)",
                backgroundColor: "rgba(15, 23, 42, 0.7)",
                color: "#e2e8f0",
                fontSize: "11px",
              }}
            >
              <option value="workspace">Workspace stream</option>
              <option value="api">API</option>
              <option value="websocket">WebSocket</option>
              <option value="mcp">MCP</option>
            </select>

            {(configForm.type === "api" || configForm.type === "websocket") && (
              <label style={{ fontSize: "11px", color: "#94a3b8" }}>
                Endpoint URL
                <input
                  value={configForm.endpoint}
                  onChange={(event) =>
                    setConfigForm((prev) => ({ ...prev, endpoint: event.target.value }))
                  }
                  onMouseDown={(event) => event.stopPropagation()}
                  onTouchStart={(event) => event.stopPropagation()}
                  style={{
                    width: "100%",
                    marginTop: "4px",
                    padding: "6px 8px",
                    borderRadius: "6px",
                    border: "1px solid rgba(148, 163, 184, 0.25)",
                    backgroundColor: "rgba(15, 23, 42, 0.7)",
                    color: "#e2e8f0",
                    fontSize: "11px",
                  }}
                />
              </label>
            )}

            {configForm.type === "mcp" && (
              <>
                <label style={{ fontSize: "11px", color: "#94a3b8" }}>
                  MCP server ID
                  <input
                    value={configForm.mcpServerId}
                    onChange={(event) =>
                      setConfigForm((prev) => ({
                        ...prev,
                        mcpServerId: event.target.value,
                      }))
                    }
                    onMouseDown={(event) => event.stopPropagation()}
                    onTouchStart={(event) => event.stopPropagation()}
                    style={{
                      width: "100%",
                      marginTop: "4px",
                      padding: "6px 8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(148, 163, 184, 0.25)",
                      backgroundColor: "rgba(15, 23, 42, 0.7)",
                      color: "#e2e8f0",
                      fontSize: "11px",
                    }}
                  />
                </label>
                <label style={{ fontSize: "11px", color: "#94a3b8" }}>
                  MCP tool name
                  <input
                    value={configForm.mcpToolName}
                    onChange={(event) =>
                      setConfigForm((prev) => ({
                        ...prev,
                        mcpToolName: event.target.value,
                      }))
                    }
                    onMouseDown={(event) => event.stopPropagation()}
                    onTouchStart={(event) => event.stopPropagation()}
                    style={{
                      width: "100%",
                      marginTop: "4px",
                      padding: "6px 8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(148, 163, 184, 0.25)",
                      backgroundColor: "rgba(15, 23, 42, 0.7)",
                      color: "#e2e8f0",
                      fontSize: "11px",
                    }}
                  />
                </label>
                <label style={{ fontSize: "11px", color: "#94a3b8" }}>
                  MCP args (JSON)
                  <textarea
                    value={configForm.mcpArgsJson}
                    onChange={(event) =>
                      setConfigForm((prev) => ({
                        ...prev,
                        mcpArgsJson: event.target.value,
                      }))
                    }
                    onMouseDown={(event) => event.stopPropagation()}
                    onTouchStart={(event) => event.stopPropagation()}
                    rows={3}
                    style={{
                      width: "100%",
                      marginTop: "4px",
                      padding: "6px 8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(148, 163, 184, 0.25)",
                      backgroundColor: "rgba(15, 23, 42, 0.7)",
                      color: "#e2e8f0",
                      fontSize: "10px",
                      fontFamily: "monospace",
                    }}
                  />
                </label>
              </>
            )}

            {(configForm.type === "api" || configForm.type === "mcp") && (
              <label style={{ fontSize: "11px", color: "#94a3b8" }}>
                Poll interval (ms)
                <input
                  type="number"
                  value={configForm.pollIntervalMs}
                  onChange={(event) =>
                    setConfigForm((prev) => ({
                      ...prev,
                      pollIntervalMs: event.target.value,
                    }))
                  }
                  onMouseDown={(event) => event.stopPropagation()}
                  onTouchStart={(event) => event.stopPropagation()}
                  style={{
                    width: "100%",
                    marginTop: "4px",
                    padding: "6px 8px",
                    borderRadius: "6px",
                    border: "1px solid rgba(148, 163, 184, 0.25)",
                    backgroundColor: "rgba(15, 23, 42, 0.7)",
                    color: "#e2e8f0",
                    fontSize: "11px",
                  }}
                />
              </label>
            )}

            <label
              style={{
                fontSize: "11px",
                color: "#94a3b8",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <input
                type="checkbox"
                checked={configForm.allowWrite}
                onChange={(event) =>
                  setConfigForm((prev) => ({
                    ...prev,
                    allowWrite: event.target.checked,
                  }))
                }
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
              />
              Allow write-back
            </label>

            {configForm.allowWrite && (
              <>
                <label style={{ fontSize: "11px", color: "#94a3b8" }}>
                  Write method
                  <select
                    value={configForm.writeMethod}
                    onChange={(event) =>
                      setConfigForm((prev) => ({
                        ...prev,
                        writeMethod: event.target.value as DashboardWriteMethod,
                      }))
                    }
                    onMouseDown={(event) => event.stopPropagation()}
                    onTouchStart={(event) => event.stopPropagation()}
                    style={{
                      width: "100%",
                      marginTop: "4px",
                      padding: "6px 8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(148, 163, 184, 0.25)",
                      backgroundColor: "rgba(15, 23, 42, 0.7)",
                      color: "#e2e8f0",
                      fontSize: "11px",
                    }}
                  >
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                  </select>
                </label>
                <label style={{ fontSize: "11px", color: "#94a3b8" }}>
                  Write payload (JSON)
                  <textarea
                    value={configForm.writePayloadJson}
                    onChange={(event) =>
                      setConfigForm((prev) => ({
                        ...prev,
                        writePayloadJson: event.target.value,
                      }))
                    }
                    onMouseDown={(event) => event.stopPropagation()}
                    onTouchStart={(event) => event.stopPropagation()}
                    rows={3}
                    style={{
                      width: "100%",
                      marginTop: "4px",
                      padding: "6px 8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(148, 163, 184, 0.25)",
                      backgroundColor: "rgba(15, 23, 42, 0.7)",
                      color: "#e2e8f0",
                      fontSize: "10px",
                      fontFamily: "monospace",
                    }}
                  />
                </label>
              </>
            )}

            {configError && (
              <div style={{ fontSize: "11px", color: "#f87171" }}>{configError}</div>
            )}

            <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setConfigOpen(false)}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                style={{
                  fontSize: "11px",
                  color: "#94a3b8",
                  backgroundColor: "transparent",
                  border: "1px solid rgba(148, 163, 184, 0.3)",
                  borderRadius: "6px",
                  padding: "4px 8px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveConfig}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                style={{
                  fontSize: "11px",
                  color: "#e2e8f0",
                  backgroundColor: "rgba(56, 189, 248, 0.2)",
                  border: "1px solid rgba(56, 189, 248, 0.4)",
                  borderRadius: "6px",
                  padding: "4px 8px",
                  cursor: "pointer",
                }}
              >
                Save
              </button>
            </div>
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: "12px", color: "#a0aec0", marginBottom: "6px" }}>
          Active Subscriptions
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {subscriptionBadges.length === 0 ? (
            <span style={{ fontSize: "12px", color: "#64748b" }}>No subscriptions yet</span>
          ) : (
            subscriptionBadges.map((badge) => (
              <span
                key={badge.key}
                style={{
                  fontSize: "11px",
                  padding: "3px 8px",
                  borderRadius: "999px",
                  backgroundColor: "rgba(30, 41, 59, 0.7)",
                  border: "1px solid rgba(148, 163, 184, 0.25)",
                  color: "#e2e8f0",
                }}
              >
                {badge.label}
              </span>
            ))
          )}
        </div>
      </div>

      <div>
        <div style={{ fontSize: "12px", color: "#a0aec0", marginBottom: "6px" }}>
          Recent Signals
        </div>
        {recentSignals.length === 0 ? (
          <div style={{ fontSize: "12px", color: "#64748b" }}>No updates yet</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {recentSignals.map((signal, index) => (
              <div
                key={`${signal.target}-${signal.timestamp.toISOString()}-${index}`}
                style={{
                  backgroundColor: "rgba(15, 23, 42, 0.55)",
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  borderRadius: "8px",
                  padding: "6px 8px",
                }}
              >
                <div style={{ fontSize: "11px", color: "#e2e8f0" }}>
                  {formatLabel(signal.target)} · {formatLabel(signal.changeType)}
                </div>
                <div style={{ fontSize: "10px", color: "#64748b" }}>
                  {signal.sourceId ? `Source: ${signal.sourceId}` : "Source: workspace"} ·{" "}
                  {signal.timestamp.toLocaleTimeString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: "12px", color: "#a0aec0", marginBottom: "6px" }}>
          Node Types
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {sortedTypeEntries.length === 0 ? (
            <span style={{ fontSize: "12px", color: "#64748b" }}>No nodes yet</span>
          ) : (
            sortedTypeEntries.map(([type, count]) => (
              <span
                key={type}
                style={{
                  fontSize: "11px",
                  padding: "3px 8px",
                  borderRadius: "999px",
                  backgroundColor: "rgba(30, 41, 59, 0.7)",
                  border: "1px solid rgba(148, 163, 184, 0.25)",
                  color: "#e2e8f0",
                }}
              >
                {formatLabel(type)} · {count}
              </span>
            ))
          )}
        </div>
      </div>

      <div>
        <div style={{ fontSize: "12px", color: "#a0aec0", marginBottom: "6px" }}>Edge Signals</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {sortedRelationEntries.length === 0 ? (
            <span style={{ fontSize: "12px", color: "#64748b" }}>No edges yet</span>
          ) : (
            sortedRelationEntries.map(([relation, count]) => (
              <span
                key={relation}
                style={{
                  fontSize: "11px",
                  padding: "3px 8px",
                  borderRadius: "999px",
                  backgroundColor: "rgba(15, 23, 42, 0.6)",
                  border: "1px solid rgba(56, 189, 248, 0.35)",
                  color: "#bae6fd",
                }}
              >
                {formatLabel(relation)} · {count}
              </span>
            ))
          )}
        </div>
      </div>

      <div>
        <div style={{ fontSize: "12px", color: "#a0aec0", marginBottom: "6px" }}>
          DAG Task Flow
        </div>
        {dagTotals.total === 0 ? (
          <div style={{ fontSize: "12px", color: "#64748b" }}>
            No DAG tasks tracked yet.
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "6px" }}>
            {(
              [
                ["Pending", dagTotals.pending, "#94a3b8"],
                ["In Progress", dagTotals.in_progress, "#38bdf8"],
                ["Completed", dagTotals.completed, "#34d399"],
                ["Blocked", dagTotals.blocked, "#f87171"],
              ] as Array<[string, number, string]>
            ).map(([label, value, color]) => (
              <div
                key={label}
                style={{
                  backgroundColor: "rgba(15, 23, 42, 0.55)",
                  border: `1px solid ${color}66`,
                  borderRadius: "8px",
                  padding: "6px 8px",
                }}
              >
                <div style={{ fontSize: "10px", color }}>{label}</div>
                <div style={{ fontSize: "14px", fontWeight: 600 }}>{value}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
