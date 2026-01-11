/**
 * AG-UI Protocol: Agent-Gateway UI Communication Protocol
 *
 * This protocol defines the message types and structures for communication
 * between agents (backend) and the UI (frontend).
 *
 * Message Flow:
 * 1. Agent -> Gateway -> UI (AgentToUIMessage)
 * 2. UI -> Gateway -> Agent (UIToAgentMessage)
 */

// ============================================================================
// Common Types
// ============================================================================

/**
 * Message envelope for all AG-UI communications
 */
export interface AGUIMessageEnvelope {
  version: string; // Protocol version
  messageId: string; // Unique message ID
  timestamp: string; // ISO 8601 timestamp
  source: 'agent' | 'ui';
  target: 'agent' | 'ui';
  correlationId?: string; // For request/response correlation
}

// ============================================================================
// Agent -> UI Messages
// ============================================================================

/**
 * Base type for messages sent from Agent to UI
 */
export interface AgentToUIMessage extends AGUIMessageEnvelope {
  source: 'agent';
  target: 'ui';
}

/**
 * Message types from Agent to UI
 */
export type AgentToUIMessageType =
  | AgentStatusMessage
  | AgentProgressMessage
  | AgentResultMessage
  | AgentErrorMessage
  | AgentRequestMessage
  | AgentNotificationMessage
  | StateUpdateMessage
  | StateSnapshotMessage;

/**
 * Agent status update (working, idle, error)
 */
export interface AgentStatusMessage extends AgentToUIMessage {
  type: 'status';
  payload: {
    status: 'idle' | 'working' | 'waiting' | 'error';
    agentId: string;
    agentName: string;
    message?: string;
    progress?: number; // 0-1
  };
}

/**
 * Agent progress update for long-running operations
 */
export interface AgentProgressMessage extends AgentToUIMessage {
  type: 'progress';
  payload: {
    agentId: string;
    operation: string;
    progress: number; // 0-1
    message?: string;
    total?: number;
    current?: number;
  };
}

/**
 * Agent result (successful operation outcome)
 */
export interface AgentResultMessage extends AgentToUIMessage {
  type: 'result';
  payload: {
    agentId: string;
    operation: string;
    result: unknown;
    correlationId?: string;
  };
}

/**
 * Agent error notification
 */
export interface AgentErrorMessage extends AgentToUIMessage {
  type: 'error';
  payload: {
    agentId: string;
    error: string;
    code?: string;
    details?: Record<string, unknown>;
    recoverable?: boolean;
  };
}

/**
 * Agent request for user input or confirmation
 */
export interface AgentRequestMessage extends AgentToUIMessage {
  type: 'request';
  payload: {
    agentId: string;
    requestId: string;
    requestType: 'input' | 'confirmation' | 'choice' | 'file';
    prompt: string;
    placeholder?: string;
    choices?: Array<{ value: string; label: string; description?: string }>;
    default?: string;
    required?: boolean;
  };
}

/**
 * Agent notification (info, warning, success)
 */
export interface AgentNotificationMessage extends AgentToUIMessage {
  type: 'notification';
  payload: {
    level: 'info' | 'success' | 'warning';
    title: string;
    message: string;
    duration?: number; // Auto-dismiss after ms (0 = no auto-dismiss)
    actions?: Array<{ label: string; action: string; primary?: boolean }>;
  };
}

/**
 * State update message with sequence tracking and checksum
 */
export interface StateUpdateMessage extends AgentToUIMessage {
  type: 'state.update';
  payload: {
    sequence: number; // Monotonically increasing sequence number
    patch: JSONPatchOperation[]; // JSON Patch operations to apply
    checksum: string; // SHA-256 checksum of the patch data
  };
}

/**
 * State snapshot message (full state response)
 */
export interface StateSnapshotMessage extends AgentToUIMessage {
  type: 'state.snapshot';
  payload: {
    sequence: number; // Current sequence number at snapshot time
    state: Record<string, unknown>; // Full state snapshot
    checksum: string; // SHA-256 checksum of the state data
  };
}

// ============================================================================
// UI -> Agent Messages
// ============================================================================

/**
 * Base type for messages sent from UI to Agent
 */
export interface UIToAgentMessage extends AGUIMessageEnvelope {
  source: 'ui';
  target: 'agent';
}

/**
 * Message types from UI to Agent
 */
export type UIToAgentMessageType =
  | UICommandMessage
  | UIResponseMessage
  | UICancelMessage
  | UIContextMessage
  | UIStateSyncRequestMessage;

/**
 * UI command to agent (execute an operation)
 */
export interface UICommandMessage extends UIToAgentMessage {
  type: 'command';
  payload: {
    agentId?: string; // Optional: let gateway route to appropriate agent
    command: string;
    parameters?: Record<string, unknown>;
    context?: UIContext;
  };
}

/**
 * UI response to agent request
 */
export interface UIResponseMessage extends UIToAgentMessage {
  type: 'response';
  payload: {
    agentId: string;
    requestId: string;
    response: unknown;
    cancelled?: boolean;
  };
}

/**
 * UI cancel request for ongoing operation
 */
export interface UICancelMessage extends UIToAgentMessage {
  type: 'cancel';
  payload: {
    agentId: string;
    operationId?: string;
    reason?: string;
  };
}

/**
 * UI context update (selection, viewport, etc.)
 */
export interface UIContextMessage extends UIToAgentMessage {
  type: 'context';
  payload: {
    context: UIContext;
  };
}

/**
 * UI state sync request (request full state from server)
 */
export interface UIStateSyncRequestMessage extends UIToAgentMessage {
  type: 'state.sync_request';
  payload: {
    last_sequence: number | null; // The last sequence number the client received
  };
}

// ============================================================================
// Context Types
// ============================================================================

/**
 * JSON Patch operation as per RFC 6902
 */
export interface JSONPatchOperation {
  op: 'add' | 'remove' | 'replace' | 'move' | 'copy' | 'test';
  path: string;
  value?: unknown;
  from?: string;
}

// ============================================================================
// State Sync Types
// ============================================================================

/**
 * State sync status for the client
 */
export interface StateSyncStatus {
  lastSequence: number | null; // The last sequence number received
  isSynced: boolean; // Whether the client is in sync
  needsSync: boolean; // Whether the client needs a full state sync
}

/**
 * State update result
 */
export interface StateUpdateResult {
  applied: boolean; // Whether the update was applied
  reason?: string; // Reason why it wasn't applied (if any)
  gapDetected: boolean; // Whether a sequence gap was detected
}

/**
 * Apply JSON Patch operations to a target object
 *
 * @param target - The target object to apply patches to
 * @param patches - Array of JSON Patch operations
 * @returns The patched object
 */
export function applyJSONPatch(
  target: Record<string, unknown>,
  patches: JSONPatchOperation[]
): Record<string, unknown> {
  const result = { ...target };

  for (const patch of patches) {
    switch (patch.op) {
      case 'add':
      case 'replace':
        setAtPath(result, patch.path, patch.value);
        break;
      case 'remove':
        removeAtPath(result, patch.path);
        break;
      case 'move':
        if (patch.from) {
          const value = getAtPath(result, patch.from);
          removeAtPath(result, patch.from);
          setAtPath(result, patch.path, value);
        }
        break;
      case 'copy':
        if (patch.from) {
          const value = getAtPath(result, patch.from);
          setAtPath(result, patch.path, value);
        }
        break;
      case 'test':
        const current = getAtPath(result, patch.path);
        if (current !== patch.value) {
          throw new Error(
            `Test failed at ${patch.path}: expected ${JSON.stringify(patch.value)}, got ${JSON.stringify(current)}`
          );
        }
        break;
    }
  }

  return result;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/**
 * Set a value at a JSON Pointer path
 */
function setAtPath(obj: Record<string, unknown>, path: string, value: unknown): void {
  if (path === '' || path === '/') {
    if (typeof value === 'object' && value !== null) {
      Object.assign(obj, value);
    }
    return;
  }

  const parts = path.slice(1).split('/');
  let current: Record<string, unknown> = obj;

  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    if (!(part in current)) {
      current[part] = {};
    }
    const next = current[part];
    if (isRecord(next)) {
      current = next;
    } else {
      current = {};
    }
  }

  current[parts[parts.length - 1]] = value;
}

/**
 * Get a value at a JSON Pointer path
 */
function getAtPath(obj: Record<string, unknown>, path: string): unknown {
  if (path === '' || path === '/') {
    return obj;
  }

  const parts = path.slice(1).split('/');
  let current: Record<string, unknown> | unknown = obj;

  for (const part of parts) {
    if (typeof current !== 'object' || current === null || !(part in current)) {
      throw new Error(`Path not found: ${path}`);
    }
    current = (current as Record<string, unknown>)[part];
  }

  return current;
}

/**
 * Remove a value at a JSON Pointer path
 */
function removeAtPath(obj: Record<string, unknown>, path: string): void {
  if (path === '' || path === '/') {
    Object.keys(obj).forEach((key) => delete obj[key]);
    return;
  }

  const parts = path.slice(1).split('/');
  let current: Record<string, unknown> = obj;

  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    if (!(part in current)) {
      throw new Error(`Path not found: ${path}`);
    }
    const next = current[part];
    if (!isRecord(next)) {
      throw new Error(`Path not found: ${path}`);
    }
    current = next;
  }

  const lastPart = parts[parts.length - 1];
  if (!(lastPart in current)) {
    throw new Error(`Path not found: ${path}`);
  }

  delete current[lastPart];
}

/**
 * Compute SHA-256 checksum for data
 *
 * @param data - The data to checksum
 * @returns A string in format "sha256:{hexdigest}"
 */
export async function computeChecksum(data: unknown): Promise<string> {
  const jsonStr = JSON.stringify(data, Object.keys(data as Record<string, unknown>).sort());
  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(jsonStr);
  const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  return `sha256:${hashHex}`;
}

// ============================================================================
// Context Types
// ============================================================================

/**
 * UI context snapshot for agent awareness
 */
export interface UIContext {
  canvas: {
    selectedNodes: string[];
    selectedEdges: string[];
    viewport: {
      x: number;
      y: number;
      zoom: number;
    };
  };
  workspace: {
    workspaceId: string;
    userId?: string;
  };
  userInput?: string;
}

// ============================================================================
// Event Types (for AG-UI Protocol Advanced Events)
// ============================================================================

/**
 * Event types for agent-to-UI event streaming
 */
export interface AGUIEvent {
  eventType: AGUIEventType;
  eventId: string;
  timestamp: string;
  data: unknown;
}

export type AGUIEventType =
  | 'node.created'
  | 'node.updated'
  | 'node.deleted'
  | 'edge.created'
  | 'edge.deleted'
  | 'canvas.cleared'
  | 'workspace.changed'
  | 'selection.changed'
  | 'viewport.changed';

// ============================================================================
// Helper Types
// ============================================================================

/**
 * Message handler for Agent -> UI messages
 */
export type AgentToUIMessageHandler = (
  message: AgentToUIMessageType
) => void | Promise<void>;

/**
 * Message handler for UI -> Agent messages
 */
export type UIToAgentMessageHandler = (
  message: UIToAgentMessageType
) => void | Promise<void>;

/**
 * AG-UI client configuration
 */
export interface AGUIClientConfig {
  gatewayUrl: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  onMessage?: AgentToUIMessageHandler;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
}

// ============================================================================
// Protocol Version
// ============================================================================

export const AGUI_PROTOCOL_VERSION = '1.0.0';

// ============================================================================
// Message Builders
// ============================================================================

/**
 * Create a message envelope with standard fields
 */
export function createEnvelope(
  source: 'agent' | 'ui',
  target: 'agent' | 'ui',
  correlationId?: string
): Omit<AGUIMessageEnvelope, 'messageId' | 'timestamp'> {
  return {
    version: AGUI_PROTOCOL_VERSION,
    source,
    target,
    correlationId,
  };
}

/**
 * Generate a unique message ID
 */
export function generateMessageId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
}

/**
 * Get current timestamp as ISO string
 */
export function getTimestamp(): string {
  return new Date().toISOString();
}
