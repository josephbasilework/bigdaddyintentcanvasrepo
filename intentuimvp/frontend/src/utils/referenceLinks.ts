import type { CanvasNode } from "@/state/canvasStore";

type ReferenceTarget =
  | { type: "turn"; id: number }
  | { type: "node"; id: string };

export type ReferenceToken =
  | { type: "text"; value: string }
  | { type: "reference"; value: string; target: ReferenceTarget };

type ReferenceMatch = {
  start: number;
  end: number;
  value: string;
  target: ReferenceTarget;
  priority: number;
};

type ReferenceOptions = {
  turnIdBySequence?: Map<number, number>;
  nodes?: CanvasNode[];
};

const TURN_REF_RE = /\bturn\s*#?\s*(\d+)\b/gi;
const NODE_ID_RE = /\bnode\s*#?\s*([a-z0-9_-]+)\b/gi;
const NODE_HANDLE_RE = /(?<!\w)@([a-z0-9][\w-]{1,64})/gi;

const isWordChar = (value: string): boolean => /[A-Za-z0-9_]/.test(value);

const normalizeHandle = (value: string): string =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, "");

const isEligibleTitle = (title: string): boolean => {
  const trimmed = title.trim();
  if (!trimmed) {
    return false;
  }
  const words = trimmed.split(/\s+/);
  return trimmed.length >= 6 || words.length >= 2;
};

const collectReferenceMatches = (
  text: string,
  options: ReferenceOptions
): ReferenceMatch[] => {
  const matches: ReferenceMatch[] = [];
  const turnIdBySequence = options.turnIdBySequence;
  const nodes = options.nodes ?? [];
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const handleIndex = new Map<string, string>();

  for (const node of nodes) {
    const key = normalizeHandle(node.title);
    if (!key) {
      continue;
    }
    if (!handleIndex.has(key)) {
      handleIndex.set(key, node.id);
    }
  }

  if (turnIdBySequence && turnIdBySequence.size > 0) {
    TURN_REF_RE.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = TURN_REF_RE.exec(text)) !== null) {
      const sequence = Number(match[1]);
      const turnId = turnIdBySequence.get(sequence);
      if (!Number.isFinite(sequence) || turnId === undefined) {
        continue;
      }
      matches.push({
        start: match.index,
        end: match.index + match[0].length,
        value: match[0],
        target: { type: "turn", id: turnId },
        priority: 2,
      });
    }
  }

  if (nodes.length > 0) {
    NODE_ID_RE.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = NODE_ID_RE.exec(text)) !== null) {
      const rawId = match[1];
      if (!nodeById.has(rawId)) {
        continue;
      }
      matches.push({
        start: match.index,
        end: match.index + match[0].length,
        value: match[0],
        target: { type: "node", id: rawId },
        priority: 2,
      });
    }

    NODE_HANDLE_RE.lastIndex = 0;
    while ((match = NODE_HANDLE_RE.exec(text)) !== null) {
      const handle = normalizeHandle(match[1]);
      const nodeId = handleIndex.get(handle);
      if (!nodeId) {
        continue;
      }
      matches.push({
        start: match.index,
        end: match.index + match[0].length,
        value: match[0],
        target: { type: "node", id: nodeId },
        priority: 2,
      });
    }

    const lowerText = text.toLowerCase();
    for (const node of nodes) {
      if (!isEligibleTitle(node.title)) {
        continue;
      }
      const title = node.title.trim();
      const lowerTitle = title.toLowerCase();
      let index = lowerText.indexOf(lowerTitle);
      while (index >= 0) {
        const end = index + lowerTitle.length;
        const prevChar = index > 0 ? text[index - 1] : "";
        const nextChar = end < text.length ? text[end] : "";
        const atBoundary =
          (index === 0 || !isWordChar(prevChar)) &&
          (end === text.length || !isWordChar(nextChar));
        if (atBoundary && prevChar !== "@") {
          matches.push({
            start: index,
            end,
            value: text.slice(index, end),
            target: { type: "node", id: node.id },
            priority: 1,
          });
        }
        index = lowerText.indexOf(lowerTitle, end);
      }
    }
  }

  return matches;
};

export const buildReferenceTokens = (
  text: string,
  options: ReferenceOptions = {}
): ReferenceToken[] => {
  if (!text) {
    return [{ type: "text", value: text }];
  }
  const matches = collectReferenceMatches(text, options);
  if (matches.length === 0) {
    return [{ type: "text", value: text }];
  }

  const sorted = matches.sort((a, b) => {
    if (a.start !== b.start) {
      return a.start - b.start;
    }
    if (a.priority !== b.priority) {
      return b.priority - a.priority;
    }
    return b.end - a.end;
  });
  const ordered: ReferenceMatch[] = [];
  let lastEnd = -1;
  for (const match of sorted) {
    if (match.start < lastEnd) {
      continue;
    }
    ordered.push(match);
    lastEnd = match.end;
  }

  const tokens: ReferenceToken[] = [];
  let cursor = 0;
  for (const match of ordered) {
    if (match.start > cursor) {
      tokens.push({ type: "text", value: text.slice(cursor, match.start) });
    }
    tokens.push({
      type: "reference",
      value: match.value,
      target: match.target,
    });
    cursor = match.end;
  }
  if (cursor < text.length) {
    tokens.push({ type: "text", value: text.slice(cursor) });
  }
  if (tokens.length === 0) {
    tokens.push({ type: "text", value: text });
  }
  return tokens;
};

export const linkifyReferences = (
  text: string,
  options: ReferenceOptions = {}
): string => {
  const tokens = buildReferenceTokens(text, options);
  if (tokens.length === 1 && tokens[0].type === "text") {
    return text;
  }
  return tokens
    .map((token) => {
      if (token.type === "text") {
        return token.value;
      }
      const href =
        token.target.type === "turn"
          ? `#turn-${token.target.id}`
          : `#node-${token.target.id}`;
      return `[${token.value}](${href})`;
    })
    .join("");
};
