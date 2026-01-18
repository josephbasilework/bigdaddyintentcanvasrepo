export type ResponseType =
  | "conversational"
  | "proposal"
  | "clarification"
  | "acknowledgment"
  | "tool_invocation";

export type TurnResponse = {
  id: number;
  sessionId: string;
  sequenceNumber: number;
  timestamp: string;
  actor: string;
  type: string;
  summary: string;
  payload: Record<string, unknown>;
  responseType?: ResponseType | null;
  originSequenceNumber: number | null;
  relatedNodeId: number | null;
  relatedEdgeId: number | null;
};

export type TurnListResponse = {
  turns: TurnResponse[];
  count: number;
};

const RESPONSE_TYPE_LABELS: Record<ResponseType, string> = {
  conversational: "Conversational",
  proposal: "Proposal",
  clarification: "Clarification",
  acknowledgment: "Acknowledgment",
  tool_invocation: "Tool invocation",
};

const RESPONSE_TYPE_ALIASES: Record<string, ResponseType> = {
  acknowledgement: "acknowledgment",
  tool: "tool_invocation",
  "tool-invocation": "tool_invocation",
};

const RESPONSE_TYPE_VALUES = new Set<ResponseType>(
  Object.keys(RESPONSE_TYPE_LABELS) as ResponseType[]
);

const normalizeResponseType = (value: unknown): ResponseType | null => {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toLowerCase().replace(/-/g, "_");
  const aliased = RESPONSE_TYPE_ALIASES[normalized] ?? normalized;
  if (RESPONSE_TYPE_VALUES.has(aliased as ResponseType)) {
    return aliased as ResponseType;
  }
  return null;
};

const responseTypeFromPayload = (
  payload: Record<string, unknown>
): ResponseType | null => {
  const explicit = normalizeResponseType(
    payload.responseType ?? payload.response_type
  );
  if (explicit) {
    return explicit;
  }
  const nested = payload.result;
  if (nested && typeof nested === "object") {
    const nestedPayload = nested as Record<string, unknown>;
    const nestedExplicit = normalizeResponseType(
      nestedPayload.responseType ?? nestedPayload.response_type
    );
    if (nestedExplicit) {
      return nestedExplicit;
    }
  }
  return null;
};

const responseTypeFromRequest = (
  payload: Record<string, unknown>
): ResponseType | null => {
  const requestType = payload.request_type ?? payload.requestType;
  if (typeof requestType !== "string") {
    return null;
  }
  const normalized = requestType.trim().toLowerCase();
  if (normalized === "confirmation") {
    return "proposal";
  }
  if (["input", "choice", "file"].includes(normalized)) {
    return "clarification";
  }
  return null;
};

const hasNonEmptyList = (payload: Record<string, unknown>, keys: string[]): boolean =>
  keys.some((key) => Array.isArray(payload[key]) && payload[key].length > 0);

export const getResponseType = (turn: TurnResponse): ResponseType | null => {
  const payload = turn.payload ?? {};
  const topLevel = normalizeResponseType(turn.responseType);
  if (topLevel) {
    return topLevel;
  }
  const payloadType = responseTypeFromPayload(payload);
  if (payloadType) {
    return payloadType;
  }
  const requestType = responseTypeFromRequest(payload);
  if (requestType) {
    return requestType;
  }
  const nested = payload.result;
  if (nested && typeof nested === "object") {
    const nestedPayload = nested as Record<string, unknown>;
    const nestedRequestType = responseTypeFromRequest(nestedPayload);
    if (nestedRequestType) {
      return nestedRequestType;
    }
    if (
      hasNonEmptyList(nestedPayload, [
        "clarifying_questions",
        "clarifyingQuestions",
      ])
    ) {
      return "clarification";
    }
    if (hasNonEmptyList(nestedPayload, ["assumptions"])) {
      return "proposal";
    }
  }
  if (hasNonEmptyList(payload, ["clarifying_questions", "clarifyingQuestions"])) {
    return "clarification";
  }
  if (hasNonEmptyList(payload, ["assumptions"])) {
    return "proposal";
  }
  if (turn.type === "assumption_presented") {
    return "proposal";
  }
  if (turn.type === "mcp_tool_invoked" || turn.type === "mcp_tool_result") {
    return "tool_invocation";
  }
  if (turn.type === "agent_response") {
    return "conversational";
  }
  if (turn.type === "system_message" || turn.type === "external_state_change") {
    return "acknowledgment";
  }
  return null;
};

export const getResponseTypeLabel = (responseType: ResponseType): string =>
  RESPONSE_TYPE_LABELS[responseType] ?? responseType;
