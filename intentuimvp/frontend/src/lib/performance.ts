/**
 * Frontend performance tracking utilities for NFR-PERF metrics.
 *
 * Tracks client-side performance metrics:
 * - NFR-PERF-001: Canvas initial load time
 * - NFR-PERF-002: State update propagation time
 * - NFR-PERF-005: WebSocket reconnection time
 * - NFR-PERF-006: Canvas render FPS
 *
 * Reference: intentuimvp/docs/PERFORMANCE_BUDGET.md
 */

interface TelemetryEvent {
  metric_name: string;
  value: number;
  unit?: string;
  extra_attrs?: Record<string, unknown>;
}

interface PerformanceMark {
  name: string;
  startTime: number;
}

/**
 * Send a telemetry event to the backend.
 */
async function sendTelemetry(event: TelemetryEvent): Promise<void> {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const endpoint = `${apiBase}/api/v1/telemetry`;

  try {
    await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(event),
    });
  } catch (error) {
    // Silently fail - telemetry shouldn''t break the app
    console.debug("Telemetry send failed:", error);
  }
}

/**
 * Performance tracker for timing operations.
 */
class PerformanceTracker {
  private marks: Map<string, PerformanceMark> = new Map();
  private correlationId: string;

  constructor(correlationId?: string) {
    this.correlationId = correlationId || this.generateCorrelationId();
  }

  private generateCorrelationId(): string {
    return `perf-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  }

  getCorrelationId(): string {
    return this.correlationId;
  }

  start(name: string): void {
    this.marks.set(name, {
      name,
      startTime: performance.now(),
    });
  }

  end(
    name: string,
    metricName: string = name,
    extraAttrs?: Record<string, unknown>,
  ): number | undefined {
    const mark = this.marks.get(name);
    if (!mark) {
      console.warn(`Performance mark "${name}" not found`);
      return undefined;
    }

    const duration = performance.now() - mark.startTime;
    this.marks.delete(name);

    sendTelemetry({
      metric_name: metricName,
      value: duration,
      unit: "ms",
      extra_attrs: {
        ...extraAttrs,
        correlation_id: this.correlationId,
      },
    });

    return duration;
  }

  measure(name: string): number | undefined {
    const mark = this.marks.get(name);
    if (!mark) {
      return undefined;
    }

    const duration = performance.now() - mark.startTime;
    this.marks.delete(name);

    return duration;
  }
}

/**
 * NFR-PERF-001: Track canvas initial load performance.
 * Target: < 2000ms per NFR-PERF-001.
 */
export function trackCanvasLoad(
  user_id: string,
  node_count: number,
  edge_count: number,
): PerformanceTracker {
  const tracker = new PerformanceTracker();

  // Use Navigation Timing API for initial page load
  if (performance.getEntriesByType) {
    const navigationEntries = performance.getEntriesByType("navigation");
    if (navigationEntries.length > 0) {
      const navEntry = navigationEntries[0] as PerformanceNavigationTiming;
      const loadTime = navEntry.loadEventEnd - navEntry.fetchStart;

      sendTelemetry({
        metric_name: "canvas_load",
        value: loadTime,
        unit: "ms",
        extra_attrs: {
          user_id,
          node_count,
          edge_count,
          correlation_id: tracker.getCorrelationId(),
        },
      });
    }
  }

  return tracker;
}

/**
 * NFR-PERF-002: Track state update propagation time.
 * Target: < 100ms per NFR-PERF-002.
 */
export function trackStateUpdate(
  update_type: string,
  entity_type: string,
): PerformanceTracker {
  const tracker = new PerformanceTracker();
  tracker.start("state_update");

  // Return the tracker with a custom end method that includes telemetry
  const originalEnd = tracker.end.bind(tracker);
  (tracker as unknown as { end: () => number | undefined }).end = (): number | undefined => {
    const duration = originalEnd("state_update", "state_update", {
      update_type,
      entity_type,
    });
    return duration;
  };

  return tracker;
}

/**
 * NFR-PERF-005: Track WebSocket reconnection time.
 * Target: < 5000ms per NFR-PERF-005.
 */
export function recordWsReconnect(duration_ms: number, success: boolean): void {
  sendTelemetry({
    metric_name: "ws_reconnect",
    value: duration_ms,
    unit: "ms",
    extra_attrs: { success },
  });
}

/**
 * NFR-PERF-006: Track canvas rendering frame rate.
 * Target: 60fps with 100 nodes per NFR-PERF-006.
 */
export function recordCanvasFps(node_count: number, fps: number): void {
  sendTelemetry({
    metric_name: "canvas_fps",
    value: fps,
    unit: "fps",
    extra_attrs: { node_count },
  });
}

/**
 * FPS meter for measuring canvas render performance.
 */
export class FpsMeter {
  private frames: number[] = [];
  private lastTime: number = performance.now();
  private isRunning: boolean = false;
  private rafId: number | null = null;

  start(): void {
    if (this.isRunning) return;

    this.isRunning = true;
    this.frames = [];
    this.lastTime = performance.now();
    this.measure();
  }

  stop(): number | undefined {
    this.isRunning = false;

    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }

    if (this.frames.length === 0) {
      return undefined;
    }

    const sum = this.frames.reduce((a, b) => a + b, 0);
    return sum / this.frames.length;
  }

  private measure(): void {
    if (!this.isRunning) return;

    const currentTime = performance.now();
    const delta = currentTime - this.lastTime;

    if (delta > 0) {
      const fps = 1000 / delta;
      this.frames.push(fps);

      if (this.frames.length > 60) {
        this.frames.shift();
      }
    }

    this.lastTime = currentTime;
    this.rafId = requestAnimationFrame(() => this.measure());
  }

  getCurrentFps(): number | undefined {
    if (this.frames.length === 0) {
      return undefined;
    }

    const sum = this.frames.reduce((a, b) => a + b, 0);
    return sum / this.frames.length;
  }
}

/**
 * WebSocket reconnection tracker.
 */
export class WsReconnectTracker {
  private disconnectTime: number | null = null;

  recordDisconnect(): void {
    this.disconnectTime = performance.now();
  }

  recordReconnect(success: boolean): number | undefined {
    if (this.disconnectTime === null) {
      return undefined;
    }

    const duration = performance.now() - this.disconnectTime;
    this.disconnectTime = null;

    recordWsReconnect(duration, success);
    return duration;
  }
}
