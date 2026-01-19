import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AGUIClient } from './client';
import { AGUI_PROTOCOL_VERSION, computeChecksum } from './protocol';

vi.mock('@/lib/performance', () => ({
  recordWsReconnect: vi.fn(),
}));

const suppressConsole = () => {
  const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => undefined);

  return () => {
    errorSpy.mockRestore();
    warnSpy.mockRestore();
    infoSpy.mockRestore();
  };
};

let restoreConsole: (() => void) | null = null;

beforeEach(() => {
  restoreConsole = suppressConsole();
});

afterEach(() => {
  restoreConsole?.();
  restoreConsole = null;
});

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];
  static autoOpen = true;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: MessageEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    if (MockWebSocket.autoOpen) {
      queueMicrotask(() => {
        if (this.readyState !== MockWebSocket.CLOSED) {
          this.readyState = MockWebSocket.OPEN;
          this.triggerOpen();
        }
      });
    }
  }

  send(data: string): void {
    this.sentMessages.push(data);
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    this.triggerClose(code ?? 1000, reason ?? '');
  }

  triggerOpen(): void {
    if (this.onopen) {
      this.onopen(new MessageEvent('open'));
    }
  }

  triggerMessage(data: string): void {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data }));
    }
  }

  triggerClose(code: number, reason: string): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(
        new CloseEvent('close', { code, reason, wasClean: code === 1000 })
      );
    }
  }

  triggerError(): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }

  static reset(): void {
    MockWebSocket.instances.forEach((ws) => {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
    });
    MockWebSocket.instances = [];
    MockWebSocket.autoOpen = true;
  }
}

const OriginalWebSocket = global.WebSocket;

const flushMicrotasks = async (): Promise<void> => {
  for (let i = 0; i < 5; i += 1) {
    await Promise.resolve();
  }
};

const hasStateSyncRequest = (messages: string[]): boolean => {
  return messages.some((message) => {
    try {
      return JSON.parse(message).type === 'state.sync_request';
    } catch {
      return false;
    }
  });
};

const hasMessageType = (messages: string[], type: string): boolean => {
  return messages.some((message) => {
    try {
      return JSON.parse(message).type === type;
    } catch {
      return false;
    }
  });
};

describe('AGUIClient reconnection', () => {
  beforeEach(() => {
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    MockWebSocket.reset();
  });

  afterEach(() => {
    MockWebSocket.reset();
    global.WebSocket = OriginalWebSocket;
  });

  it('reconnects with exponential backoff and caps at 30s', async () => {
    vi.useFakeTimers();
    MockWebSocket.autoOpen = false;

    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
      reconnectInterval: 1000,
      maxReconnectAttempts: 10,
    });

    client.connect();
    await flushMicrotasks();

    expect(MockWebSocket.instances.length).toBe(1);

    const delays = [1000, 2000, 4000, 8000, 16000, 30000];
    let expectedInstances = 1;

    for (const delay of delays) {
      const ws = MockWebSocket.instances[expectedInstances - 1];
      ws.triggerClose(1006, 'Abnormal closure');

      vi.advanceTimersByTime(delay - 1);
      expect(MockWebSocket.instances.length).toBe(expectedInstances);

      vi.advanceTimersByTime(1);
      expectedInstances += 1;
      expect(MockWebSocket.instances.length).toBe(expectedInstances);
    }
  });

  it('stops reconnecting after max attempts', async () => {
    vi.useFakeTimers();
    MockWebSocket.autoOpen = false;

    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
      reconnectInterval: 100,
      maxReconnectAttempts: 2,
    });

    client.connect();
    await flushMicrotasks();

    expect(MockWebSocket.instances.length).toBe(1);

    const delays = [100, 200];
    let expectedInstances = 1;

    for (const delay of delays) {
      const ws = MockWebSocket.instances[expectedInstances - 1];
      ws.triggerClose(1006, 'Abnormal closure');

      vi.advanceTimersByTime(delay);
      expectedInstances += 1;
      expect(MockWebSocket.instances.length).toBe(expectedInstances);
    }

    const ws = MockWebSocket.instances[expectedInstances - 1];
    ws.triggerClose(1006, 'Abnormal closure');
    vi.advanceTimersByTime(1000);

    expect(MockWebSocket.instances.length).toBe(expectedInstances);
  });

  it('requests state sync on reconnect', async () => {
    vi.useFakeTimers();

    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
      reconnectInterval: 1000,
    });

    client.connect();
    await flushMicrotasks();

    const firstSocket = MockWebSocket.instances[0];
    expect(hasStateSyncRequest(firstSocket.sentMessages)).toBe(true);

    firstSocket.triggerClose(1006, 'Abnormal closure');
    vi.advanceTimersByTime(1000);
    await flushMicrotasks();

    const secondSocket = MockWebSocket.instances[1];
    expect(hasStateSyncRequest(secondSocket.sentMessages)).toBe(true);
  });
});

describe('AGUIClient outbound queue', () => {
  beforeEach(() => {
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    MockWebSocket.reset();
  });

  afterEach(() => {
    MockWebSocket.reset();
    global.WebSocket = OriginalWebSocket;
    vi.useRealTimers();
  });

  it('queues outbound messages until the socket opens', async () => {
    MockWebSocket.autoOpen = false;

    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
    });

    client.connect();
    await flushMicrotasks();

    const ws = MockWebSocket.instances[0];

    const commandMessage = {
      source: 'ui',
      target: 'agent',
      type: 'command',
      payload: {
        command: 'ping',
      },
    };

    expect(() => client.send(commandMessage)).not.toThrow();
    expect(hasMessageType(ws.sentMessages, 'command')).toBe(false);

    ws.readyState = MockWebSocket.OPEN;
    ws.triggerOpen();
    await flushMicrotasks();

    const commandEnvelope = ws.sentMessages
      .map((message) => {
        try {
          return JSON.parse(message);
        } catch {
          return null;
        }
      })
      .find((message) => message?.type === 'command');

    expect(commandEnvelope).toMatchObject({
      version: AGUI_PROTOCOL_VERSION,
      source: 'ui',
      target: 'agent',
      type: 'command',
    });
    expect(commandEnvelope?.messageId).toEqual(expect.any(String));
    expect(commandEnvelope?.timestamp).toEqual(expect.any(String));
  });
});

describe('AGUIClient state sync', () => {
  beforeEach(() => {
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    MockWebSocket.reset();
  });

  afterEach(() => {
    MockWebSocket.reset();
    global.WebSocket = OriginalWebSocket;
    vi.useRealTimers();
  });

  it('applies state snapshots through the CopilotKit event pipeline', async () => {
    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
    });

    client.connect();
    await flushMicrotasks();

    const snapshotState = { canvas: { nodes: { n1: { id: 'n1' } } } };
    const checksum = await computeChecksum(snapshotState);
    const snapshotMessage = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: 'msg-1',
      timestamp: new Date().toISOString(),
      source: 'agent',
      target: 'ui',
      type: 'state.snapshot',
      payload: {
        sequence: 1,
        state: snapshotState,
        checksum,
      },
    };

    const ws = MockWebSocket.instances[0];
    ws.triggerMessage(JSON.stringify(snapshotMessage));
    await flushMicrotasks();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(client.getLocalState()).toEqual(snapshotState);
  });

  it('ignores duplicate state updates without side effects', async () => {
    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
    });

    client.connect();
    await flushMicrotasks();

    const checksum = await computeChecksum([{ op: 'add', path: '/test', value: 'data' }]);

    // Send sequence 1
    const update1 = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: 'msg-1',
      timestamp: new Date().toISOString(),
      source: 'agent',
      target: 'ui',
      type: 'state.update',
      payload: {
        sequence: 1,
        patch: [{ op: 'add', path: '/test', value: 'data' }],
        checksum,
      },
    };

    const ws = MockWebSocket.instances[0];
    ws.triggerMessage(JSON.stringify(update1));
    await flushMicrotasks();

    const stateAfterFirst = client.getState();
    expect(stateAfterFirst.stateSync.lastSequence).toBe(1);

    // Send duplicate sequence 1 (should be ignored)
    ws.triggerMessage(JSON.stringify(update1));
    await flushMicrotasks();

    const stateAfterDuplicate = client.getState();
    expect(stateAfterDuplicate.stateSync.lastSequence).toBe(1);
    expect(stateAfterDuplicate.stateSync.needsSync).toBe(false);
  });

  it('detects sequence gaps and requests full state sync', async () => {
    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
    });

    client.connect();
    await flushMicrotasks();

    const checksum = await computeChecksum([{ op: 'add', path: '/test', value: 'data' }]);

    // Send sequence 1
    const update1 = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: 'msg-1',
      timestamp: new Date().toISOString(),
      source: 'agent',
      target: 'ui',
      type: 'state.update',
      payload: {
        sequence: 1,
        patch: [{ op: 'add', path: '/test', value: 'data' }],
        checksum,
      },
    };

    const ws = MockWebSocket.instances[0];
    ws.triggerMessage(JSON.stringify(update1));
    await flushMicrotasks();

    expect(client.getState().stateSync.lastSequence).toBe(1);

    const gapChecksum = await computeChecksum([{ op: 'add', path: '/test2', value: 'data2' }]);

    // Send sequence 3 (gap: missing sequence 2)
    const update3 = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: 'msg-3',
      timestamp: new Date().toISOString(),
      source: 'agent',
      target: 'ui',
      type: 'state.update',
      payload: {
        sequence: 3,
        patch: [{ op: 'add', path: '/test2', value: 'data2' }],
        checksum: gapChecksum,
      },
    };

    ws.triggerMessage(JSON.stringify(update3));
    await flushMicrotasks();

    const stateAfterGap = client.getState();
    expect(stateAfterGap.stateSync.needsSync).toBe(true);
    expect(stateAfterGap.stateSync.isSynced).toBe(false);
    expect(stateAfterGap.stateSync.lastSequence).toBe(1); // Should not advance

    // Verify that state sync request was sent
    expect(hasStateSyncRequest(ws.sentMessages)).toBe(true);
  });

  it('requests REST snapshot when a sequence gap is detected', async () => {
    const snapshotState = { canvas: { nodes: { n1: { id: 'n1' } } } };
    const snapshotChecksum = await computeChecksum(snapshotState);
    const snapshotRequest = vi.fn().mockResolvedValue({
      sequence: 2,
      state: snapshotState,
      checksum: snapshotChecksum,
    });

    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
      snapshotRequest,
    });

    client.connect();
    await flushMicrotasks();

    const checksum = await computeChecksum([{ op: 'add', path: '/test', value: 'data' }]);
    const gapChecksum = await computeChecksum([{ op: 'add', path: '/test2', value: 'data2' }]);

    // Send sequence 1
    const update1 = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: 'msg-1',
      timestamp: new Date().toISOString(),
      source: 'agent',
      target: 'ui',
      type: 'state.update',
      payload: {
        sequence: 1,
        patch: [{ op: 'add', path: '/test', value: 'data' }],
        checksum,
      },
    };

    const ws = MockWebSocket.instances[0];
    ws.triggerMessage(JSON.stringify(update1));
    await flushMicrotasks();

    // Send sequence 3 (gap)
    const update3 = {
      version: AGUI_PROTOCOL_VERSION,
      messageId: 'msg-3',
      timestamp: new Date().toISOString(),
      source: 'agent',
      target: 'ui',
      type: 'state.update',
      payload: {
        sequence: 3,
        patch: [{ op: 'add', path: '/test2', value: 'data2' }],
        checksum: gapChecksum,
      },
    };

    ws.triggerMessage(JSON.stringify(update3));
    await flushMicrotasks();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(snapshotRequest).toHaveBeenCalledWith({ lastSequence: 1 });
    expect(client.getState().stateSync.lastSequence).toBe(2);
  });

  it('applies sequential state updates in order', async () => {
    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
    });

    client.connect();
    await flushMicrotasks();

    const checksum1 = await computeChecksum([{ op: 'add', path: '/key1', value: 'value1' }]);
    const checksum2 = await computeChecksum([{ op: 'add', path: '/key2', value: 'value2' }]);
    const checksum3 = await computeChecksum([{ op: 'replace', path: '/key1', value: 'updated' }]);

    const updates = [
      {
        version: AGUI_PROTOCOL_VERSION,
        messageId: 'msg-1',
        timestamp: new Date().toISOString(),
        source: 'agent',
        target: 'ui',
        type: 'state.update' as const,
        payload: {
          sequence: 1,
          patch: [{ op: 'add', path: '/key1', value: 'value1' }],
          checksum: checksum1,
        },
      },
      {
        version: AGUI_PROTOCOL_VERSION,
        messageId: 'msg-2',
        timestamp: new Date().toISOString(),
        source: 'agent',
        target: 'ui',
        type: 'state.update' as const,
        payload: {
          sequence: 2,
          patch: [{ op: 'add', path: '/key2', value: 'value2' }],
          checksum: checksum2,
        },
      },
      {
        version: AGUI_PROTOCOL_VERSION,
        messageId: 'msg-3',
        timestamp: new Date().toISOString(),
        source: 'agent',
        target: 'ui',
        type: 'state.update' as const,
        payload: {
          sequence: 3,
          patch: [{ op: 'replace', path: '/key1', value: 'updated' }],
          checksum: checksum3,
        },
      },
    ];

    const ws = MockWebSocket.instances[0];

    for (const update of updates) {
      ws.triggerMessage(JSON.stringify(update));
      await flushMicrotasks();
    }

    const finalState = client.getState();
    expect(finalState.stateSync.lastSequence).toBe(3);
    expect(finalState.stateSync.isSynced).toBe(true);
    expect(finalState.stateSync.needsSync).toBe(false);
  });

  it('requests explicit state sync on reconnect (no automatic replay)', async () => {
    vi.useFakeTimers();
    MockWebSocket.autoOpen = false;

    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
      reconnectInterval: 100,
    });

    client.connect();
    await flushMicrotasks();

    const firstSocket = MockWebSocket.instances[0];
    firstSocket.readyState = MockWebSocket.OPEN;
    firstSocket.triggerOpen();

    // Verify explicit state sync request on initial connect
    expect(hasStateSyncRequest(firstSocket.sentMessages)).toBe(true);

    // Close connection
    firstSocket.triggerClose(1006, 'Abnormal closure');

    // Advance timer to trigger reconnect
    vi.advanceTimersByTime(100);
    await flushMicrotasks();

    const secondSocket = MockWebSocket.instances[1];
    secondSocket.readyState = MockWebSocket.OPEN;
    secondSocket.triggerOpen();

    // Verify explicit state sync request on reconnect (not automatic replay)
    expect(hasStateSyncRequest(secondSocket.sentMessages)).toBe(true);
  });
});

describe('AGUIClient dashboard streaming', () => {
  beforeEach(() => {
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    MockWebSocket.reset();
  });

  afterEach(() => {
    MockWebSocket.reset();
    global.WebSocket = OriginalWebSocket;
  });

  it('dispatches dashboard update messages to listeners', async () => {
    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
    });

    client.connect();
    await flushMicrotasks();

    const handler = vi.fn();
    client.onDashboardUpdate(42, handler);

    const ws = MockWebSocket.instances[0];
    ws.triggerMessage(
      JSON.stringify({
        version: AGUI_PROTOCOL_VERSION,
        messageId: 'msg-1',
        timestamp: new Date().toISOString(),
        source: 'agent',
        target: 'ui',
        type: 'dashboard.update',
        payload: {
          dashboard_node_id: 42,
          subscription_target: 'job',
          source_id: 'job-1',
          change_type: 'created',
          data: { status: 'ok' },
          timestamp: new Date().toISOString(),
        },
      })
    );

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ dashboard_node_id: 42, subscription_target: 'job' })
    );
  });

  it('dispatches dashboard subscribed messages to listeners', async () => {
    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
    });

    client.connect();
    await flushMicrotasks();

    const handler = vi.fn();
    client.onDashboardSubscribed(7, handler);

    const ws = MockWebSocket.instances[0];
    ws.triggerMessage(
      JSON.stringify({
        version: AGUI_PROTOCOL_VERSION,
        messageId: 'msg-2',
        timestamp: new Date().toISOString(),
        source: 'agent',
        target: 'ui',
        type: 'dashboard.subscribed',
        payload: {
          dashboard_node_id: 7,
          subscriptions: [{ id: 1, subscriptionTarget: 'job', sourceId: 'job-1' }],
        },
      })
    );

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ dashboard_node_id: 7 })
    );
  });

  it('sends dashboard subscribe requests with envelope fields', async () => {
    const client = new AGUIClient({
      gatewayUrl: 'http://localhost:8000',
    });

    client.connect();
    await flushMicrotasks();

    client.subscribeToDashboard(12, 34);

    const ws = MockWebSocket.instances[0];
    const subscribeEnvelope = ws.sentMessages
      .map((message) => {
        try {
          return JSON.parse(message);
        } catch {
          return null;
        }
      })
      .find((message) => message?.type === 'dashboard.subscribe');

    expect(subscribeEnvelope).toMatchObject({
      version: AGUI_PROTOCOL_VERSION,
      source: 'ui',
      target: 'agent',
      type: 'dashboard.subscribe',
      payload: {
        dashboard_node_id: 12,
        canvas_id: 34,
        targets: [
          'workspace_state',
          'node',
          'edge',
          'job',
          'artifact',
          'tool_output',
          'external_state',
        ],
      },
    });
    expect(subscribeEnvelope?.messageId).toEqual(expect.any(String));
    expect(subscribeEnvelope?.timestamp).toEqual(expect.any(String));
  });
});
