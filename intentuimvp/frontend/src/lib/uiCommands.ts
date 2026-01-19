"use client";

export type PanelView =
  | "chat"
  | "wheel"
  | "events"
  | "mcp"
  | "context"
  | "hooks"
  | "memory"
  | "notifications";

export type UiCommand =
  | { type: "close_panels" }
  | { type: "show_panel"; panel: PanelView }
  | { type: "clear_selection" };

export type UiCommandMatch = UiCommand & {
  raw: string;
  normalized: string;
};

export const PANEL_LABELS: Record<PanelView, string> = {
  chat: "Chat",
  wheel: "Wheel",
  events: "Events",
  mcp: "MCP",
  context: "Context",
  hooks: "Hooks",
  memory: "Memory",
  notifications: "Notifications",
};

const SHOW_PREFIXES = new Set(["show", "open", "display"]);
const CLOSE_ALIASES = new Set([
  "close panels",
  "close all panels",
  "hide panels",
  "hide all panels",
]);
const CLEAR_SELECTION_ALIASES = new Set([
  "clear selection",
  "clear selections",
  "clear selected",
]);

const PANEL_ALIASES: Record<PanelView, string[]> = {
  chat: ["chat", "chat panel", "chat view"],
  wheel: ["wheel", "wheel panel", "wheel view"],
  events: ["events", "event", "events panel", "event panel", "events view", "event view"],
  mcp: ["mcp", "mcp panel", "mcp install", "mcp install panel"],
  context: [
    "context",
    "context panel",
    "context preview",
    "context preview panel",
  ],
  hooks: ["hooks", "hooks panel"],
  memory: ["memory", "memory panel", "intent memory", "intent memory panel"],
  notifications: [
    "notifications",
    "notification",
    "notifications panel",
    "notification panel",
  ],
};

const aliasLookup = new Map<string, PanelView>();
Object.entries(PANEL_ALIASES).forEach(([panel, aliases]) => {
  aliases.forEach((alias) => {
    aliasLookup.set(alias, panel as PanelView);
  });
});

export const normalizeUiCommandText = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const stripLeadingArticle = (value: string): string =>
  value.replace(/^(the|a|an)\s+/, "");

const matchShowPanel = (normalized: string): PanelView | null => {
  const parts = normalized.split(" ");
  const prefix = parts[0];
  if (!SHOW_PREFIXES.has(prefix)) {
    return null;
  }
  const remainder = stripLeadingArticle(parts.slice(1).join(" ").trim());
  if (!remainder) {
    return null;
  }
  const panel = aliasLookup.get(remainder);
  return panel ?? null;
};

export const parseUiCommand = (
  input: string,
  customCommands?: Record<string, UiCommand>
): UiCommandMatch | null => {
  const raw = input.trim();
  if (!raw) {
    return null;
  }
  if (raw.startsWith("/")) {
    return null;
  }
  const normalized = normalizeUiCommandText(raw);
  if (!normalized) {
    return null;
  }
  if (customCommands) {
    const custom = customCommands[normalized];
    if (custom) {
      return { ...custom, raw, normalized };
    }
  }
  if (CLOSE_ALIASES.has(normalized)) {
    return { type: "close_panels", raw, normalized };
  }
  if (CLEAR_SELECTION_ALIASES.has(normalized)) {
    return { type: "clear_selection", raw, normalized };
  }
  const panel = matchShowPanel(normalized);
  if (panel) {
    return { type: "show_panel", panel, raw, normalized };
  }
  return null;
};

const normalizeCommandKey = (value: string): string =>
  value
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_")
    .replace(/[^a-z0-9_]/g, "");

export const resolveUiCommandKey = (value: string): UiCommand | null => {
  const normalized = normalizeCommandKey(value);
  if (!normalized) {
    return null;
  }
  if (normalized === "close_panels" || normalized === "close_panel") {
    return { type: "close_panels" };
  }
  if (
    normalized === "clear_selection" ||
    normalized === "clear_selected" ||
    normalized === "clear_selections"
  ) {
    return { type: "clear_selection" };
  }
  const showPrefix = normalized.startsWith("show_")
    ? "show_"
    : normalized.startsWith("open_")
      ? "open_"
      : null;
  if (showPrefix) {
    const panel = normalized.slice(showPrefix.length);
    if (panel in PANEL_LABELS) {
      return { type: "show_panel", panel: panel as PanelView };
    }
  }
  if (normalized in PANEL_LABELS) {
    return { type: "show_panel", panel: normalized as PanelView };
  }
  return null;
};

export const getUiCommandKey = (command: UiCommand): string => {
  if (command.type === "show_panel") {
    return `show_${command.panel}`;
  }
  return command.type;
};
