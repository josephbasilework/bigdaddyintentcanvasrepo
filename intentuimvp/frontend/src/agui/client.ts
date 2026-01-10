/**
 * AG-UI Client: WebSocket client for Agent-Gateway UI communication
 *
 * This client manages the WebSocket connection to the gateway and handles
 * message routing between agents and the UI.
 */

import {
  AGUIClientConfig,
  AgentToUIMessageHandler,
  AgentToUIMessageType,
  UIToAgentMessage,
  UIToAgentMessageType,
  generateMessageId,
  getTimestamp,
  AGUI_PROTOCOL_VERSION,
  StateUpdateMessage,
  StateSnapshotMessage,
  StateSyncStatus,
  applyJSONPatch,
  computeChecksum,
} from './protocol';

export interface AGUIClientState {
  connected: boolean;
  connecting: boolean;
  error: Error | null;
  stateSync: StateSyncStatus;
}

export class AGUIClient {
  private ws: WebSocket | null = null;
  private config: AGUIClientConfig;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private isManualDisconnect = false;
  private messageHandlers: Set<AgentToUIMessageHandler> = new Set();

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
  private stateUpdateListeners: Set<(state: Record<string, unknown>) => void> = new Set();

  // State sync status listeners
  private stateSyncListeners: Set<(status: StateSyncStatus) => void> = new Set();

  constructor(config: AGUIClientConfig) {
    this.config = {
      reconnectInterval: 1000,
      maxReconnectAttempts: 10,
      ...config,
    };
  }

  /**
   * Connect to the gateway via WebSocket
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isManualDisconnect = false;
    this.clearReconnectTimer();
    this.setState({ connecting: true, error: null });

    try {
      const wsUrl = this.config.gatewayUrl.replace(/^http/, 'ws');
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.setState({ connected: true, connecting: false, error: null });
        this.reconnectAttempts = 0;

        // Request full state sync on connection
        this.requestStateSync();

        this.config.onConnect?.();
      };

      this.ws.onclose = () => {
        this.setState({ connected: false, connecting: false });
        this.config.onDisconnect?.();

        // Attempt to reconnect if not intentionally closed
        if (!this.isManualDisconnect) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        const error = new Error('WebSocket connection error');
        this.setState({ error });
        this.config.onError?.(error);
        if (!this.isManualDisconnect) {
          this.scheduleReconnect();
        }
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };
    } catch (error) {
      this.setState({ connected: false, connecting: false, error: error as Error });
      this.config.onError?.(error as Error);
      if (!this.isManualDisconnect) {
        this.scheduleReconnect();
      }
    }
  }

  /**
   * Disconnect from the gateway
   */
  disconnect(): void {
    this.isManualDisconnect = true;
    this.reconnectAttempts = 0;
    this.clearReconnectTimer();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.setState({ connected: false, connecting: false });
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
  send(message: UIToAgentMessageType): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not connected');
    }

    const envelope: UIToAgentMessage = {
      ...message,
      version: AGUI_PROTOCOL_VERSION,
      messageId: generateMessageId(),
      timestamp: getTimestamp(),
    };

    this.ws.send(JSON.stringify(envelope));
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
   * Handle incoming message from gateway
   */
  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data) as AgentToUIMessageType;

      // Validate message structure
      if (!message.version || !message.messageId || !message.timestamp) {
        console.error('Invalid AG-UI message:', message);
        return;
      }

      // Handle state update messages
      if (message.type === 'state.update') {
        this.handleStateUpdate(message);
        return;
      }

      // Handle state snapshot messages
      if (message.type === 'state.snapshot') {
        this.handleStateSnapshot(message);
        return;
      }

      // Call all registered handlers for other message types
      for (const handler of this.messageHandlers) {
        handler(message);
      }

      // Call legacy onMessage handler if provided
      if (this.config.onMessage) {
        this.config.onMessage(message);
      }
    } catch (error) {
      console.error('Failed to parse AG-UI message:', error);
    }
  }

  /**
   * Handle state update message with sequence validation
   */
  private handleStateUpdate(message: StateUpdateMessage): void {
    const { sequence, patch, checksum } = message.payload;

    // Check for sequence gap
    const lastSeq = this.state.stateSync.lastSequence;
    if (lastSeq !== null && sequence !== lastSeq + 1) {
      console.warn(
        `Sequence gap detected: expected ${lastSeq + 1}, got ${sequence}`
      );

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

      // Notify listeners about the gap
      for (const listener of this.stateSyncListeners) {
        listener(this.state.stateSync);
      }

      return;
    }

    // Validate checksum (optional but recommended)
    this.validateChecksum(patch, checksum).catch((err) => {
      console.error('Checksum validation failed:', err);
    });

    // Apply the patch
    try {
      this.localState = applyJSONPatch(this.localState, patch);

      // Update last sequence
      this.setState({
        stateSync: {
          lastSequence: sequence,
          isSynced: true,
          needsSync: false,
        },
      });

      // Notify state update listeners
      for (const listener of this.stateUpdateListeners) {
        listener(this.localState);
      }

      // Notify state sync listeners
      for (const listener of this.stateSyncListeners) {
        listener(this.state.stateSync);
      }
    } catch (error) {
      console.error('Failed to apply state update:', error);

      // Request full state sync on error
      this.requestStateSync();
    }
  }

  /**
   * Handle state snapshot message
   */
  private handleStateSnapshot(message: StateSnapshotMessage): void {
    const { sequence, state, checksum } = message.payload;

    // Validate checksum (optional but recommended)
    this.validateChecksum(state, checksum).catch((err) => {
      console.error('Checksum validation failed for snapshot:', err);
    });

    // Replace entire state with snapshot
    this.localState = { ...state };

    // Update last sequence
    this.setState({
      stateSync: {
        lastSequence: sequence,
        isSynced: true,
        needsSync: false,
      },
    });

    // Notify state update listeners
    for (const listener of this.stateUpdateListeners) {
      listener(this.localState);
    }

    // Notify state sync listeners
    for (const listener of this.stateSyncListeners) {
      listener(this.state.stateSync);
    }

    console.info(
      `State snapshot applied: sequence=${sequence}, keys=${Object.keys(state).join(', ')}`
    );
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
      console.error('Checksum validation error:', error);
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
      source: 'ui',
      target: 'agent',
      type: 'state.sync_request',
      payload: {
        last_sequence: this.state.stateSync.lastSequence,
      },
    };

    try {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(syncRequest));
        console.info('Requested state sync');
      }
    } catch (error) {
      console.error('Failed to request state sync:', error);
    }
  }

  /**
   * Schedule reconnection attempt
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }

    const maxAttempts = this.config.maxReconnectAttempts ?? 10;
    if (this.reconnectAttempts >= maxAttempts) {
      const error = new Error(
        `WebSocket: Max reconnection attempts (${maxAttempts}) reached`
      );
      this.setState({ error });
      this.config.onError?.(error);
      return;
    }

    this.reconnectAttempts += 1;
    const delay = this.getReconnectDelay(this.reconnectAttempts);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
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
