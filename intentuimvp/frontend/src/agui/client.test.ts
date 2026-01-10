import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AGUIClient } from './client';

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
  await Promise.resolve();
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

describe('AGUIClient reconnection', () => {
  beforeEach(() => {
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    MockWebSocket.reset();
  });

  afterEach(() => {
    MockWebSocket.reset();
    global.WebSocket = OriginalWebSocket;
    vi.useRealTimers();
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
