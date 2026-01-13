/**
 * Performance metrics instrumentation for the IntentUI frontend.
 *
 * Implements NFR-PERF metrics:
 * - NFR-PERF-001: Canvas initial load timing
 * - NFR-PERF-002: State update propagation timing
 * - NFR-PERF-006: Canvas FPS monitoring
 */

/**
 * Metric IDs for NFR-PERF compliance
 */
export const PERF_METRICS = {
  CANVAS_LOAD: 'NFR-PERF-001',
  STATE_UPDATE: 'NFR-PERF-002',
  CANVAS_FPS: 'NFR-PERF-006',
} as const;

/**
 * Performance measurement marks using the Performance API
 */
const PERF_MARK_PREFIX = 'intentui-';

/**
 * Log a performance mark for measurement
 */
export function mark(name: string): void {
  try {
    performance.mark(`${PERF_MARK_PREFIX}${name}`);
  } catch (e) {
    // Mark may already exist, ignore
    console.debug(`Performance mark failed: ${name}`, e);
  }
}

/**
 * Measure the time between two marks
 */
export function measure(name: string, startMark: string, endMark: string): number | undefined {
  try {
    const measureName = `${PERF_MARK_PREFIX}${name}`;
    performance.measure(
      measureName,
      `${PERF_MARK_PREFIX}${startMark}`,
      `${PERF_MARK_PREFIX}${endMark}`
    );
    const entry = performance.getEntriesByName(measureName)[0];
    return entry?.duration;
  } catch (e) {
    console.debug(`Performance measure failed: ${name}`, e);
    return undefined;
  }
}

/**
 * Get a performance entry and clean it up
 */
export function getAndClearMeasure(name: string): number | undefined {
  const entries = performance.getEntriesByName(`${PERF_MARK_PREFIX}${name}`, 'measure');
  if (entries.length === 0) return undefined;
  const duration = entries[0].duration;
  performance.clearMarks(`${PERF_MARK_PREFIX}${name}`);
  performance.clearMeasures(`${PERF_MARK_PREFIX}${name}`);
  return duration;
}

/**
 * Clear all performance marks and measures
 */
export function clearMarks(): void {
  // Standard Performance API doesn't have clearMarksByPrefix
  // So we iterate through all marks/measures and clear those with the prefix
  for (const entry of performance.getEntriesByType('mark')) {
    if (entry.name.startsWith(PERF_MARK_PREFIX)) {
      performance.clearMarks(entry.name);
    }
  }
  for (const entry of performance.getEntriesByType('measure')) {
    if (entry.name.startsWith(PERF_MARK_PREFIX)) {
      performance.clearMeasures(entry.name);
    }
  }
}

/**
 * Generate a correlation ID for tracking operations
 */
export function generateCorrelationId(): string {
  return `corr-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * NFR-PERF-001: Canvas initial load timing
 *
 * Tracks the time from navigation start to canvas-ready state.
 */
export class CanvasLoadTimer {
  private correlationId: string;
  private startTime: number;

  constructor() {
    this.correlationId = generateCorrelationId();
    this.startTime = performance.now();
    mark(`canvas-load-start-${this.correlationId}`);
  }

  /**
   * Mark when the canvas component mounts
   */
  markCanvasMounted(): void {
    mark(`canvas-mounted-${this.correlationId}`);
  }

  /**
   * Mark when initial data is loaded
   */
  markDataLoaded(): void {
    mark(`canvas-data-loaded-${this.correlationId}`);
  }

  /**
   * Mark when canvas is interactive (ready for user input)
   */
  markInteractive(): void {
    mark(`canvas-interactive-${this.correlationId}`);
    const duration = this.getDuration();
    this.log('canvas_load_complete', duration);
  }

  /**
   * Get the total load duration in milliseconds
   */
  getDuration(): number {
    return performance.now() - this.startTime;
  }

  /**
   * Log performance metric
   */
  private log(event: string, duration?: number): void {
    const metric = {
      metric: PERF_METRICS.CANVAS_LOAD,
      event,
      correlation_id: this.correlationId,
      duration_ms: duration ?? this.getDuration(),
      timestamp: new Date().toISOString(),
    };
    console.info('[Performance]', JSON.stringify(metric));

    // Also use PerformanceObserver for production monitoring
    if (typeof window !== 'undefined' && 'PerformanceObserver' in window) {
      performance.mark(`${PERF_MARK_PREFIX}metric:${JSON.stringify(metric)}`);
    }
  }
}

/**
 * NFR-PERF-002: State update propagation timing
 *
 * Tracks the time from WebSocket message receipt to React state commit.
 */
export class StateUpdateTimer {
  private correlationId: string;
  private startTime: number;

  constructor(correlationId?: string) {
    this.correlationId = correlationId ?? generateCorrelationId();
    this.startTime = performance.now();
    mark(`state-update-start-${this.correlationId}`);
  }

  /**
   * Mark when state update is applied
   */
  markStateApplied(): number {
    mark(`state-update-applied-${this.correlationId}`);
    const duration = this.getDuration();
    this.log('state_update_applied', duration);
    return duration;
  }

  /**
   * Get the propagation duration in milliseconds
   */
  getDuration(): number {
    return performance.now() - this.startTime;
  }

  /**
   * Log performance metric
   */
  private log(event: string, duration: number): void {
    const metric = {
      metric: PERF_METRICS.STATE_UPDATE,
      event,
      correlation_id: this.correlationId,
      duration_ms: duration,
      timestamp: new Date().toISOString(),
    };
    console.info('[Performance]', JSON.stringify(metric));
  }
}

/**
 * NFR-PERF-006: Canvas FPS monitoring
 *
 * Monitors frame rate during canvas interactions for smoothness metrics.
 */
export class FPSMonitor {
  private frames: number[] = [];
  private lastTime: number = performance.now();
  private rafId: number | null = null;
  private isRunning: boolean = false;
  private correlationId: string;

  constructor() {
    this.correlationId = generateCorrelationId();
  }

  /**
   * Start monitoring FPS
   */
  start(): void {
    if (this.isRunning) return;
    this.isRunning = true;
    this.lastTime = performance.now();
    this.frames = [];
    this.measureFrame();
  }

  /**
   * Stop monitoring and log results
   */
  stop(): void {
    if (!this.isRunning) return;
    this.isRunning = false;
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.logResults();
  }

  /**
   * Get current FPS
   */
  getCurrentFPS(): number | undefined {
    if (this.frames.length < 2) return undefined;
    const avgFrameTime = this.frames.reduce((a, b) => a + b, 0) / this.frames.length;
    return 1000 / avgFrameTime;
  }

  /**
   * Measure each frame
   */
  private measureFrame = (): void => {
    if (!this.isRunning) return;

    const now = performance.now();
    const frameTime = now - this.lastTime;
    this.lastTime = now;

    // Keep last 60 frames (1 second at 60fps)
    this.frames.push(frameTime);
    if (this.frames.length > 60) {
      this.frames.shift();
    }

    this.rafId = requestAnimationFrame(this.measureFrame);
  };

  /**
   * Log FPS statistics
   */
  private logResults(): void {
    if (this.frames.length === 0) return;

    const avgFrameTime = this.frames.reduce((a, b) => a + b, 0) / this.frames.length;
    const minFrameTime = Math.min(...this.frames);
    const maxFrameTime = Math.max(...this.frames);

    const avgFPS = 1000 / avgFrameTime;
    const minFPS = 1000 / maxFrameTime;
    const maxFPS = 1000 / minFrameTime;

    // Calculate p50 (median) and p95
    const sorted = [...this.frames].sort((a, b) => a - b);
    const p50FrameTime = sorted[Math.floor(sorted.length * 0.5)];
    const p95FrameTime = sorted[Math.floor(sorted.length * 0.95)];
    const p50FPS = 1000 / p50FrameTime;
    const p95FPS = 1000 / p95FrameTime;

    const metric = {
      metric: PERF_METRICS.CANVAS_FPS,
      event: 'fps_measurement',
      correlation_id: this.correlationId,
      avg_fps: Math.round(avgFPS * 100) / 100,
      min_fps: Math.round(minFPS * 100) / 100,
      max_fps: Math.round(maxFPS * 100) / 100,
      p50_fps: Math.round(p50FPS * 100) / 100,
      p95_fps: Math.round(p95FPS * 100) / 100,
      frame_count: this.frames.length,
      timestamp: new Date().toISOString(),
    };
    console.info('[Performance]', JSON.stringify(metric));
  }
}

/**
 * Check if the browser supports the Performance API
 */
export function isPerformanceAPISupported(): boolean {
  return (
    typeof performance !== 'undefined' &&
    'mark' in performance &&
    'measure' in performance &&
    'now' in performance
  );
}
