/**
 * AG-UI Client: WebSocket client for Agent-Gateway UI communication
 *
 * This client manages the WebSocket connection to the gateway and handles
 * message routing between agents and the UI.
 */

import {
  AGUIClientConfig,
  AgentToUIMessage,
  AgentToUIMessageHandler,
  AgentToUIMessageType,
  UIToAgentMessage,
  UIToAgentMessageType,
  generateMessageId,
  getTimestamp,
  AGUI_PROTOCOL_VERSION,
} from './protocol';

export interface AGUIClientState {
  connected: boolean;
  connecting: boolean;
  error: Error | null;
}

export class AGUIClient {
  private ws: WebSocket | null = null;
  private config: AGUIClientConfig;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private messageHandlers: Set<AgentToUIMessageHandler> = new Set();
  private state: AGUIClientState = {
    connected: false,
    connecting: false,
    error: null,
  };

  // State change listeners
  private stateListeners: Set<(state: AGUIClientState) => void> = new Set();

  constructor(config: AGUIClientConfig) {
    this.config = {
      reconnectInterval: 3000,
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

    this.setState({ connecting: true, error: null });

    try {
      const wsUrl = this.config.gatewayUrl.replace(/^http/, 'ws');
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.setState({ connected: true, connecting: false, error: null });
        this.reconnectAttempts = 0;
        this.config.onConnect?.();
      };

      this.ws.onclose = (event) => {
        this.setState({ connected: false, connecting: false });
        this.config.onDisconnect?.();

        // Attempt to reconnect if not intentionally closed
        if (!event.wasClean && this.reconnectAttempts < (this.config.maxReconnectAttempts ?? 10)) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (event) => {
        const error = new Error('WebSocket connection error');
        this.setState({ error });
        this.config.onError?.(error);
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };
    } catch (error) {
      this.setState({ connected: false, connecting: false, error: error as Error });
      this.config.onError?.(error as Error);
    }
  }

  /**
   * Disconnect from the gateway
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.setState({ connected: false, connecting: false });
  }

  /**
   * Send a message to the agent/gateway
   */
  send(message: UIToAgentMessageType): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not connected');
    }

    const envelope: UIToAgentMessage = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: generateMessageId(),
      timestamp: getTimestamp(),
      ...message,
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
   * Handle incoming message from gateway
   */
  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data) as AgentToUIMessage;

      // Validate message structure
      if (!message.version || !message.messageId || !message.timestamp) {
        console.error('Invalid AG-UI message:', message);
        return;
      }

      // Call all registered handlers
      for (const handler of this.messageHandlers) {
        handler(message as AgentToUIMessageType);
      }

      // Call legacy onMessage handler if provided
      if (this.config.onMessage) {
        this.config.onMessage(message as AgentToUIMessageType);
      }
    } catch (error) {
      console.error('Failed to parse AG-UI message:', error);
    }
  }

  /**
   * Schedule reconnection attempt
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }

    this.reconnectAttempts++;
    const delay = (this.config.reconnectInterval ?? 3000) * this.reconnectAttempts;

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
