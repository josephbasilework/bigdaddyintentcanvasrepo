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
  | AgentNotificationMessage;

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
  | UIContextMessage;

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
