/**
 * AG-UI Client: WebSocket client for Agent-Gateway UI communication
 *
 * This client manages the WebSocket connection to the gateway and handles
 * message routing between agents and the UI.
 */

import {
  AbstractAgent,
  AgentSubscriber,
  BaseEvent,
  CustomEvent,
  EventSchemas,
  EventType,
  RunAgentInput,
  RunAgentParameters,
  RunFinishedEvent,
  RunStartedEvent,
  RunErrorEvent,
  StateDeltaEvent,
  StateSnapshotEvent,
} from "@ag-ui/client";
import { Observable, Subscriber } from "rxjs";
import {
  AGUIClientConfig,
  AgentToUIMessageHandler,
  AgentToUIMessageType,
  AGUI_PROTOCOL_VERSION,
  UIToAgentMessageType,
  StateUpdateMessage,
  StateSnapshotMessage,
  StateSyncStatus,
  generateMessageId,
  getTimestamp,
  computeChecksum,
  DashboardUpdatePayload,
  DashboardSubscribedPayload,
} from "./protocol";

export interface AGUIClientState {
  connected: boolean;
  connecting: boolean;
  error: Error | null;
  stateSync: StateSyncStatus;
}

const AGENT_MESSAGE_TYPES = new Set<string>([
  "status",
  "progress",
  "result",
  "error",
  "request",
  "notification",
  "job.progress",
  "node.created",
  "node.updated",
  "node.deleted",
  "edge.created",
  "edge.updated",
  "edge.deleted",
  "run.start",
  "run.end",
  "tool.call",
  "tool.result",
  "state.update",
  "state.snapshot",
  "turn.created",
  "event.created",
  "dashboard.update",
  "dashboard.subscribed",
]);

type RunStreamMode = "connect" | "run";

type RunStreamOptions = {
  mode: RunStreamMode;
  input: RunAgentInput;
};

type RunStartEnvelope = {
  version: string;
  messageId: string;
  timestamp: string;
  source: "ui";
  target: "agent";
  type: "run.start";
  payload: RunAgentInput;
};

type EnvelopeKeys = "version" | "messageId" | "timestamp";

type OutboundMessageInput = Omit<UIToAgentMessageType, EnvelopeKeys> &
  Partial<Pick<UIToAgentMessageType, EnvelopeKeys>>;

/** A message queued for outbound delivery */
type QueuedOutboundMessage = UIToAgentMessageType;

class CopilotKitWebSocketAgent extends AbstractAgent {
  private client: AGUIClient;

  constructor(client: AGUIClient) {
    super();
    this.client = client;
  }

  run(input: RunAgentInput): Observable<BaseEvent> {
    return this.client.createEventStream({ mode: "run", input });
  }

  protected connect(input: RunAgentInput): Observable<BaseEvent> {
    return this.client.createEventStream({ mode: "connect", input });
  }
}

export class AGUIClient {
  private ws: WebSocket | null = null;
  private config: AGUIClientConfig;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private isManualDisconnect = false;
  private messageHandlers: Set<AgentToUIMessageHandler> = new Set();
  private agent: CopilotKitWebSocketAgent;

  // Local state cache
  private localState: Record<string, unknown> = {};

  private state: AGUIClientState = {
    connected: false,
    connecting: false,
    error: null,
    stateSync: {
      lastSequence: null,
      isSynced: false,
      needsSync: false,
    },
  };

  // State change listeners
  private stateListeners: Set<(state: AGUIClientState) => void> = new Set();

  // State update listeners
  private stateUpdateListeners: Set<(state: Record<string, unknown>) => void> =
    new Set();

  // State sync status listeners
  private stateSyncListeners: Set<(status: StateSyncStatus) => void> = new Set();

  // Dashboard streaming listeners
  private dashboardUpdateListeners: Map<
    number,
    Set<(payload: DashboardUpdatePayload) => void>
  > = new Map();
  private dashboardSubscribedListeners: Map<
    number,
    Set<(payload: DashboardSubscribedPayload) => void>
  > = new Map();
  private activeDashboardSubscriptions: Set<number> = new Set();
  private outboundQueue: QueuedOutboundMessage[] = [];
  private isFlushingQueue = false;
  private snapshotSyncPending = false;
  private snapshotSyncInFlight = false;
  private disconnectTime: number | null = null;

  constructor(config: AGUIClientConfig) {
    this.config = {
      reconnectInterval: 1000,
      maxReconnectAttempts: 10,
      ...config,
    };
    this.agent = new CopilotKitWebSocketAgent(this);
    this.localState = this.toRecordState(this.agent.state);

    this.agent.subscribe({
      onStateChanged: ({ state }) => {
        this.localState = this.toRecordState(state);
        for (const listener of this.stateUpdateListeners) {
          listener(this.localState);
        }
      },
    });
  }

  /**
   * Connect to the gateway via WebSocket
   */
  connect(): void {
    if (this.state.connecting || this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isManualDisconnect = false;
    this.clearReconnectTimer();
    this.setState({ connecting: true, error: null });

    void this.agent.connectAgent().catch((error) => {
      const resolvedError =
        error instanceof Error ? error : new Error(String(error));
      this.setState({ error: resolvedError, connecting: false });
      this.config.onError?.(resolvedError);
    });
  }

  /**
   * Disconnect from the gateway
   */
  disconnect(): void {
    this.isManualDisconnect = true;
    this.reconnectAttempts = 0;
    this.clearReconnectTimer();
    this.outboundQueue = [];
    this.isFlushingQueue = false;
    this.snapshotSyncPending = false;
    this.snapshotSyncInFlight = false;
    this.disconnectTime = null;

    void this.agent.detachActiveRun();

    if (this.ws) {
      this.ws.close(1000, "Client disconnect");
      this.ws = null;
    }

    this.setState({ connected: false, connecting: false });
  }

  /**
   * Start an AG-UI run using CopilotKit run management.
   */
  runAgent(parameters?: RunAgentParameters, subscriber?: AgentSubscriber) {
    return this.agent.runAgent(parameters, subscriber);
  }

  /**
   * Connect to the agent event stream using CopilotKit run management.
   */
  connectAgent(parameters?: RunAgentParameters, subscriber?: AgentSubscriber) {
    return this.agent.connectAgent(parameters, subscriber);
  }

  /**
   * Access the underlying CopilotKit agent instance.
   */
  getAgent(): AbstractAgent {
    return this.agent;
  }

  /**
   * Clear any pending reconnection timer.
   */
  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Calculate reconnection delay with exponential backoff.
   */
  private getReconnectDelay(attempt: number): number {
    const baseDelay = this.config.reconnectInterval ?? 1000;
    const delay = baseDelay * Math.pow(2, Math.max(0, attempt - 1));
    return Math.min(delay, 30000);
  }

  /**
   * Send a message to the agent/gateway
   */
  send(message: OutboundMessageInput): void {
    const envelope = this.buildOutboundEnvelope(message);

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.outboundQueue.push(envelope);
      return;
    }

    this.ws.send(JSON.stringify(envelope));
  }

  /**
   * Ensure outbound messages include a full envelope.
   */
  private buildOutboundEnvelope(
    message: OutboundMessageInput
  ): UIToAgentMessageType {
    return {
      ...message,
      version: message.version ?? AGUI_PROTOCOL_VERSION,
      messageId: message.messageId ?? generateMessageId(),
      timestamp: message.timestamp ?? getTimestamp(),
    } as UIToAgentMessageType;
  }

  /**
   * Subscribe to messages from agents
   */
  onMessage(handler: AgentToUIMessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  /**
   * Subscribe to state changes
   */
  onStateChange(listener: (state: AGUIClientState) => void): () => void {
    this.stateListeners.add(listener);
    return () => this.stateListeners.delete(listener);
  }

  /**
   * Get current state
   */
  getState(): AGUIClientState {
    return { ...this.state };
  }

  /**
   * Get current local state
   */
  getLocalState(): Record<string, unknown> {
    return { ...this.localState };
  }

  /**
   * Subscribe to state updates (when local state changes)
   */
  onStateUpdate(listener: (state: Record<string, unknown>) => void): () => void {
    this.stateUpdateListeners.add(listener);
    // Immediately call with current state
    listener(this.localState);
    return () => this.stateUpdateListeners.delete(listener);
  }

  /**
   * Subscribe to state sync status changes
   */
  onStateSyncStatus(listener: (status: StateSyncStatus) => void): () => void {
    this.stateSyncListeners.add(listener);
    // Immediately call with current status
    listener(this.state.stateSync);
    return () => this.stateSyncListeners.delete(listener);
  }

  /**
   * Manually request a full state sync
   */
  refreshState(): void {
    this.requestStateSync();
  }

  /**
   * Create an AG-UI event stream bridged through CopilotKit.
   */
  createEventStream(options: RunStreamOptions): Observable<BaseEvent> {
    return new Observable<BaseEvent>((subscriber) => {
      this.isManualDisconnect = false;
      const { input, mode } = options;
      let runStarted = false;
      let runStartSent = false;
      let finished = false;

      const emitEvent = (event: BaseEvent) => {
        if (!subscriber.closed) {
          subscriber.next(event);
        }
      };

      const emitRunStarted = () => {
        if (runStarted) {
          return;
        }
        runStarted = true;
        const event: RunStartedEvent = {
          type: EventType.RUN_STARTED,
          threadId: input.threadId,
          runId: input.runId,
          parentRunId: input.parentRunId,
          input,
          timestamp: Date.now(),
        };
        emitEvent(event);
      };

      const emitRunFinished = () => {
        if (!runStarted) {
          return;
        }
        const event: RunFinishedEvent = {
          type: EventType.RUN_FINISHED,
          threadId: input.threadId,
          runId: input.runId,
          timestamp: Date.now(),
        };
        emitEvent(event);
      };

      const emitRunError = (error: Error) => {
        const event: RunErrorEvent = {
          type: EventType.RUN_ERROR,
          message: error.message,
          timestamp: Date.now(),
        };
        emitEvent(event);
      };

      const finishStream = (error?: Error) => {
        if (finished) {
          return;
        }
        finished = true;
        this.clearReconnectTimer();

        if (error) {
          emitRunError(error);
        } else {
          emitRunFinished();
        }

        if (!subscriber.closed) {
          subscriber.complete();
        }
      };

      const scheduleReconnect = () => {
        if (this.reconnectTimer || finished) {
          return;
        }

        const maxAttempts = this.config.maxReconnectAttempts ?? 10;
        if (this.reconnectAttempts >= maxAttempts) {
          const error = new Error(
            `WebSocket: Max reconnection attempts (${maxAttempts}) reached`
          );
          this.setState({ error });
          this.config.onError?.(error);
          finishStream(error);
          return;
        }

        this.reconnectAttempts += 1;
        const delay = this.getReconnectDelay(this.reconnectAttempts);

        this.reconnectTimer = setTimeout(() => {
          this.reconnectTimer = null;
          openSocket();
        }, delay);
      };

      const openSocket = () => {
        if (finished) {
          return;
        }

        if (
          this.ws &&
          (this.ws.readyState === WebSocket.OPEN ||
            this.ws.readyState === WebSocket.CONNECTING)
        ) {
          return;
        }

        this.setState({ connecting: true, error: null });

        try {
          const wsUrl = this.config.gatewayUrl.replace(/^http/, "ws");
          const ws = new WebSocket(wsUrl);
          this.ws = ws;

          ws.onopen = () => {
            this.setState({ connected: true, connecting: false, error: null });
            this.reconnectAttempts = 0;

            emitRunStarted();

            if (mode === "run" && !runStartSent) {
              this.sendRunStart(input);
              runStartSent = true;
            }

            this.requestStateSync();
            if (this.snapshotSyncPending) {
              void this.requestSnapshotSync();
            }
            this.flushQueuedMessages();
            this.config.onConnect?.();
          };

          ws.onmessage = (event) => {
            if (typeof event.data === "string") {
              this.handleIncomingMessage(event.data, subscriber);
            }
          };

          ws.onclose = () => {
            this.setState({ connected: false, connecting: false });
            this.config.onDisconnect?.();

            if (!this.isManualDisconnect) {
              scheduleReconnect();
            } else {
              finishStream();
            }
          };

          ws.onerror = () => {
            const error = new Error("WebSocket connection error");
            this.setState({ error });
            this.config.onError?.(error);

            if (!this.isManualDisconnect) {
              scheduleReconnect();
            } else {
              finishStream(error);
            }
          };
        } catch (error) {
          const resolvedError =
            error instanceof Error ? error : new Error(String(error));
          this.setState({ connected: false, connecting: false, error: resolvedError });
          this.config.onError?.(resolvedError);

          if (!this.isManualDisconnect) {
            scheduleReconnect();
          } else {
            finishStream(resolvedError);
          }
        }
      };

      openSocket();

      return () => {
        this.isManualDisconnect = true;
        finishStream();

        if (this.ws) {
          this.ws.close(1000, "Client disconnect");
          this.ws = null;
        }
      };
    });
  }

  /**
   * Handle incoming messages from gateway and emit AG-UI events.
   */
  private handleIncomingMessage(
    data: string,
    subscriber: Subscriber<BaseEvent>
  ): void {
    let message: unknown;

    try {
      message = JSON.parse(data);
    } catch (error) {
      console.error("Failed to parse AG-UI message:", error);
      return;
    }

    const parsedEvent = EventSchemas.safeParse(message);
    if (parsedEvent.success) {
      const event = parsedEvent.data as BaseEvent;
      const enrichedEvent =
        "rawEvent" in event ? event : { ...event, rawEvent: message };
      if (!subscriber.closed) {
        subscriber.next(enrichedEvent);
      }
      return;
    }

    if (this.isAgentMessage(message)) {
      const agentMessage = message as AgentToUIMessageType;
      if (agentMessage.type === "dashboard.update") {
        this.dispatchDashboardUpdate(agentMessage.payload);
      } else if (agentMessage.type === "dashboard.subscribed") {
        this.dispatchDashboardSubscribed(agentMessage.payload);
      }
      this.dispatchAgentMessage(agentMessage);

      const event = this.mapAgentMessageToEvent(agentMessage);
      if (event) {
        if (!subscriber.closed) {
          subscriber.next(event);
        }
      }
      return;
    }

    console.warn("Unknown AG-UI message:", message);
  }

  /**
   * Dispatch agent messages to registered handlers.
   */
  private dispatchAgentMessage(message: AgentToUIMessageType): void {
    for (const handler of this.messageHandlers) {
      handler(message);
    }

    if (this.config.onMessage) {
      this.config.onMessage(message);
    }
  }

  /**
   * Map protocol messages to AG-UI events.
   */
  private mapAgentMessageToEvent(message: AgentToUIMessageType): BaseEvent | null {
    if (message.type === "state.update") {
      return this.handleStateUpdate(message);
    }

    if (message.type === "state.snapshot") {
      return this.handleStateSnapshot(message);
    }

    const event: CustomEvent = {
      type: EventType.CUSTOM,
      name: message.type,
      value: message.payload,
      timestamp: this.parseTimestamp(message.timestamp),
      rawEvent: message,
    };
    return event;
  }

  /**
   * Handle state update message with sequence validation
   */
  private handleStateUpdate(message: StateUpdateMessage): BaseEvent | null {
    const { sequence, patch, checksum } = message.payload;

    // Check for sequence gap or duplicates
    const lastSeq = this.state.stateSync.lastSequence;
    if (lastSeq !== null) {
      if (sequence <= lastSeq) {
        console.warn(
          `Duplicate or out-of-order sequence: expected > ${lastSeq}, got ${sequence}`
        );
        return null;
      }

      if (sequence !== lastSeq + 1) {
        console.warn(
          `Sequence gap detected: expected ${lastSeq + 1}, got ${sequence}`
        );

        this.snapshotSyncPending = true;

        // Update state sync status
        this.setState({
          stateSync: {
            ...this.state.stateSync,
            needsSync: true,
            isSynced: false,
          },
        });

        // Request full state sync
        this.requestStateSync();
        void this.requestSnapshotSync();

        // Notify listeners about the gap
        this.notifyStateSyncListeners();

        return null;
      }
    }

    // Validate checksum (optional but recommended)
    this.validateChecksum(patch, checksum).catch((err) => {
      console.error("Checksum validation failed:", err);
    });

    // Update last sequence
    this.setState({
      stateSync: {
        lastSequence: sequence,
        isSynced: true,
        needsSync: false,
      },
    });
    this.snapshotSyncPending = false;

    // Notify state sync listeners
    this.notifyStateSyncListeners();
    this.flushQueuedMessages();

    const event: StateDeltaEvent = {
      type: EventType.STATE_DELTA,
      delta: patch,
      timestamp: this.parseTimestamp(message.timestamp),
      rawEvent: message,
    };
    return event;
  }

  /**
   * Handle state snapshot message
   */
  private handleStateSnapshot(message: StateSnapshotMessage): BaseEvent {
    const { sequence, state, checksum } = message.payload;

    // Validate checksum (optional but recommended)
    this.validateChecksum(state, checksum).catch((err) => {
      console.error("Checksum validation failed for snapshot:", err);
    });

    // Update last sequence
    this.snapshotSyncPending = false;
    this.setState({
      stateSync: {
        lastSequence: sequence,
        isSynced: true,
        needsSync: false,
      },
    });

    // Notify state sync listeners
    this.notifyStateSyncListeners();
    this.flushQueuedMessages();

    const event: StateSnapshotEvent = {
      type: EventType.STATE_SNAPSHOT,
      snapshot: state,
      timestamp: this.parseTimestamp(message.timestamp),
      rawEvent: message,
    };
    return event;
  }

  /**
   * Validate checksum for data
   */
  private async validateChecksum(
    data: unknown,
    expectedChecksum: string
  ): Promise<boolean> {
    try {
      const actualChecksum = await computeChecksum(data);
      if (actualChecksum !== expectedChecksum) {
        console.error(
          `Checksum mismatch: expected ${expectedChecksum}, got ${actualChecksum}`
        );
        return false;
      }
      return true;
    } catch (error) {
      console.error("Checksum validation error:", error);
      return false;
    }
  }

  /**
   * Request full state sync from server
   */
  private requestStateSync(): void {
    const syncRequest: UIToAgentMessageType = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: generateMessageId(),
      timestamp: getTimestamp(),
      source: "ui",
      target: "agent",
      type: "state.sync_request",
      payload: {
        last_sequence: this.state.stateSync.lastSequence,
      },
    };

    if (
      this.outboundQueue.some(
        (message) => message.type === "state.sync_request"
      )
    ) {
      console.info("Requested state sync");
      return;
    }

    try {
      this.send(syncRequest);
      console.info("Requested state sync");
    } catch (error) {
      console.error("Failed to request state sync:", error);
    }
  }

  /**
   * Request REST snapshot sync when available (sequence gaps).
   */
  private async requestSnapshotSync(): Promise<void> {
    if (!this.config.snapshotRequest || this.snapshotSyncInFlight) {
      return;
    }

    this.snapshotSyncInFlight = true;
    try {
      const snapshot = await this.config.snapshotRequest({
        lastSequence: this.state.stateSync.lastSequence,
      });
      if (!snapshot) {
        return;
      }

      const { sequence, state, checksum } = snapshot;
      this.validateChecksum(state, checksum).catch((err) => {
        console.error("Checksum validation failed for snapshot:", err);
      });

      this.snapshotSyncPending = false;
      this.setState({
        stateSync: {
          lastSequence: sequence,
          isSynced: true,
          needsSync: false,
        },
      });

      this.agent.setState(state as Record<string, unknown>);
      this.notifyStateSyncListeners();
      this.flushQueuedMessages();
    } catch (error) {
      console.error("Snapshot sync failed:", error);
    } finally {
      this.snapshotSyncInFlight = false;
    }
  }

  /**
   * Send a run start envelope to the server.
   */
  private sendRunStart(input: RunAgentInput): void {
    const envelope: RunStartEnvelope = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: generateMessageId(),
      timestamp: getTimestamp(),
      source: "ui",
      target: "agent",
      type: "run.start",
      payload: input,
    };

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(envelope));
    }
  }

  /**
   * Update state and notify listeners
   */
  private setState(newState: Partial<AGUIClientState>): void {
    this.state = { ...this.state, ...newState };
    for (const listener of this.stateListeners) {
      listener(this.getState());
    }
  }

  /**
   * Notify state sync listeners
   */
  private notifyStateSyncListeners(): void {
    const status = this.state.stateSync;
    for (const listener of this.stateSyncListeners) {
      listener(status);
    }
  }

  /**
   * Flush queued outbound messages
   */
  private flushQueuedMessages(): void {
    if (this.isFlushingQueue || this.outboundQueue.length === 0) {
      return;
    }

    this.isFlushingQueue = true;
    const messages = [...this.outboundQueue];
    this.outboundQueue = [];

    for (const message of messages) {
      try {
        this.send(message);
      } catch (error) {
        console.error("Failed to send queued message:", error);
        // Re-queue on error
        this.outboundQueue.push(message);
      }
    }

    this.isFlushingQueue = false;
  }

  private isAgentMessage(message: unknown): message is AgentToUIMessageType {
    if (!message || typeof message !== "object") {
      return false;
    }

    const candidate = message as {
      source?: unknown;
      target?: unknown;
      type?: unknown;
    };

    return (
      candidate.source === "agent" &&
      candidate.target === "ui" &&
      typeof candidate.type === "string" &&
      AGENT_MESSAGE_TYPES.has(candidate.type)
    );
  }

  private parseTimestamp(value?: string): number | undefined {
    if (!value) {
      return undefined;
    }

    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? undefined : parsed;
  }

  private toRecordState(state: unknown): Record<string, unknown> {
    if (state && typeof state === "object") {
      return { ...(state as Record<string, unknown>) };
    }

    return {};
  }

  // ============================================================================
  // Dashboard Streaming Methods
  // ============================================================================

  /**
   * Subscribe to dashboard updates for a specific dashboard node
   */
  subscribeToDashboard(dashboardNodeId: number, canvasId: number): void {
    if (this.activeDashboardSubscriptions.has(dashboardNodeId)) {
      return;
    }
    this.activeDashboardSubscriptions.add(dashboardNodeId);

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: UIToAgentMessageType = {
        version: AGUI_PROTOCOL_VERSION,
        messageId: generateMessageId(),
        timestamp: getTimestamp(),
        source: "ui",
        target: "agent",
        type: "dashboard.subscribe",
        payload: {
          dashboard_node_id: dashboardNodeId,
          canvas_id: canvasId,
          targets: [
            "workspace_state",
            "node",
            "edge",
            "job",
            "artifact",
            "tool_output",
            "external_state",
          ],
        },
      };
      this.send(message);
    }
  }

  /**
   * Unsubscribe from dashboard updates
   */
  unsubscribeFromDashboard(dashboardNodeId: number): void {
    this.activeDashboardSubscriptions.delete(dashboardNodeId);
    this.dashboardUpdateListeners.delete(dashboardNodeId);
    this.dashboardSubscribedListeners.delete(dashboardNodeId);

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: UIToAgentMessageType = {
        version: AGUI_PROTOCOL_VERSION,
        messageId: generateMessageId(),
        timestamp: getTimestamp(),
        source: "ui",
        target: "agent",
        type: "dashboard.unsubscribe",
        payload: { dashboard_node_id: dashboardNodeId },
      };
      this.send(message);
    }
  }

  /**
   * Register a listener for dashboard update events
   */
  onDashboardUpdate(
    dashboardNodeId: number,
    handler: (payload: DashboardUpdatePayload) => void
  ): () => void {
    let listeners = this.dashboardUpdateListeners.get(dashboardNodeId);
    if (!listeners) {
      listeners = new Set();
      this.dashboardUpdateListeners.set(dashboardNodeId, listeners);
    }
    listeners.add(handler);

    return () => {
      listeners?.delete(handler);
      if (listeners?.size === 0) {
        this.dashboardUpdateListeners.delete(dashboardNodeId);
      }
    };
  }

  /**
   * Register a listener for dashboard subscribed events
   */
  onDashboardSubscribed(
    dashboardNodeId: number,
    handler: (payload: DashboardSubscribedPayload) => void
  ): () => void {
    let listeners = this.dashboardSubscribedListeners.get(dashboardNodeId);
    if (!listeners) {
      listeners = new Set();
      this.dashboardSubscribedListeners.set(dashboardNodeId, listeners);
    }
    listeners.add(handler);

    return () => {
      listeners?.delete(handler);
      if (listeners?.size === 0) {
        this.dashboardSubscribedListeners.delete(dashboardNodeId);
      }
    };
  }

  /**
   * Dispatch a dashboard update to registered listeners
   */
  dispatchDashboardUpdate(payload: DashboardUpdatePayload): void {
    const listeners = this.dashboardUpdateListeners.get(payload.dashboard_node_id);
    if (listeners) {
      for (const handler of listeners) {
        handler(payload);
      }
    }
  }

  /**
   * Dispatch a dashboard subscribed event to registered listeners
   */
  dispatchDashboardSubscribed(payload: DashboardSubscribedPayload): void {
    const listeners = this.dashboardSubscribedListeners.get(
      payload.dashboard_node_id
    );
    if (listeners) {
      for (const handler of listeners) {
        handler(payload);
      }
    }
  }
}

/**
 * Create a singleton AG-UI client instance
 */
let aguiClient: AGUIClient | null = null;

export function createAGUIClient(config: AGUIClientConfig): AGUIClient {
  if (!aguiClient) {
    aguiClient = new AGUIClient(config);
  }
  return aguiClient;
}

export function getAGUIClient(): AGUIClient | null {
  return aguiClient;
}

/**
 * React hook for AG-UI client
 */
export function useAGUIClient() {
  return {
    client: getAGUIClient(),
    connect: (config: AGUIClientConfig) => {
      const client = createAGUIClient(config);
      client.connect();
      return client;
    },
    disconnect: () => {
      aguiClient?.disconnect();
      aguiClient = null;
    },
  };
}
