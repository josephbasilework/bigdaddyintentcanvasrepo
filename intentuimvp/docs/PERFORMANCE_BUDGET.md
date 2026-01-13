# Performance Budget & Measurement Baseline

**Document Version:** 1.0
**Last Updated:** 2026-01-13
**Issue:** [T1-F9.1](bigdaddyintentcanvasrepo-444)

## 1. Baseline Testing Environment

### 1.1 Hardware Specifications

All performance measurements MUST be taken against the following baseline:

| Component | Specification | Rationale |
|-----------|---------------|-----------|
| **CPU** | Apple M1 / Intel i5-10400 (6-core) | Represents typical developer laptop |
| **RAM** | 8GB available to application | Minimum viable for development |
| **Storage** | SSD (NVMe or SATA) | Standard for modern deployments |
| **Network** | 25 Mbps down, 5 Mbps up, <50ms latency | Typical broadband connection |

### 1.2 Browser Baseline

| Browser | Minimum Version | Notes |
|---------|-----------------|-------|
| Chrome | 120+ | Primary target |
| Firefox | 121+ | Secondary target |
| Safari | 17+ | macOS/iOS target |
| Edge | 120+ | Chromium-based |

### 1.3 Backend Environment

| Component | Specification |
|-----------|---------------|
| **Python** | 3.11+ |
| **Database** | SQLite (local), PostgreSQL 14+ (prod) |
| **Redis** | 7.0+ |
| **Gateway** | Pydantic AI Gateway (default model: claude-opus-4-5-20251101) |

### 1.4 Dataset Sizes for Testing

| Metric | Test Dataset | Definition |
|--------|--------------|------------|
| **Canvas initial load** | 50 nodes, 75 edges, 10 documents | Typical workspace after 1 week of use |
| **State update propagation** | Single node/edge change | Minimal payload |
| **Intent deciphering** | 200-character user command | Average command length |
| **Simple command execution** | Single LLM call + 1 tool use | Non-composite request |
| **Canvas with 100 nodes** | 100 nodes, 150 edges, 20 documents | Stress test for smoothness |
| **WebSocket reconnection** | N/A | Connection dropout simulation |

## 2. Measurement Methods

### 2.1 Frontend Metrics

| Metric ID | Metric | Measurement Tool | Measurement Method |
|-----------|--------|------------------|---------------------|
| NFR-PERF-001 | Canvas initial load | Chrome DevTools Performance | Network idle + main thread idle > 500ms after `navigationStart` |
| NFR-PERF-002 | State update propagation | Custom `performance.mark()` | Time from WebSocket message receipt to React state commit |
| NFR-PERF-003 | Intent deciphering | Backend latency headers | Time from POST request to LLM response completion |
| NFR-PERF-004 | Simple command execution | Backend job duration | Time from job enqueue to completion callback |
| NFR-PERF-005 | WebSocket reconnection | WebSocket event timing | Time from `onclose` to successful `onopen` |
| NFR-PERF-006 | Canvas with 100 nodes | Chrome DevTools FPS meter | Sustained 60fps during pan/zoom operations |

### 2.2 Backend Metrics

| Metric ID | Metric | Measurement Tool | Measurement Method |
|-----------|--------|------------------|---------------------|
| NFR-PERF-003 | Intent deciphering | Logfire/spans | Gateway client call duration |
| NFR-PERF-004 | Simple command execution | ARQ job metadata | Job function execution time |
| NFR-OBS-002 | Agent invocations | Logfire metrics | Per-agent latency percentiles |

### 2.3 Network Conditions

Tests SHOULD be run under the following simulated network conditions (Chrome DevTools Network Throttling):

| Profile | Bandwidth | Latency | Use Case |
|---------|-----------|---------|----------|
| **Online** | Unrestricted | <5ms | Local development |
| **Fast 3G** | 1.6 Mbps down, 750K up | 150ms | Baseline mobile |
| **Slow 3G** | 400 Kbps down, 400K up | 2000ms | Degraded conditions |

**Target:** All NFR-PERF metrics MUST pass under **Online** conditions. Metrics SHOULD pass under **Fast 3G** where applicable.

## 3. Agreed Thresholds

All thresholds are from [PRD §12.1](intentuimvp/PRD.md):

| ID | Metric | Target | Measurement Point |
|----|--------|--------|-------------------|
| NFR-PERF-001 | Canvas initial load | < 2000ms | Application-ready, not just DOMContentLoaded |
| NFR-PERF-002 | State update propagation | < 100ms | WebSocket receipt to UI render |
| NFR-PERF-003 | Intent deciphering | < 5000ms | Backend Gateway call duration |
| NFR-PERF-004 | Simple command execution | < 30000ms | End-to-end job completion |
| NFR-PERF-005 | WebSocket reconnection | < 5000ms | Connection recovery time |
| NFR-PERF-006 | Canvas with 100 nodes | 60fps | Sustained during pan/zoom (no drops below 55fps) |

## 4. Running Performance Tests

### 4.1 Frontend Performance

```bash
cd intentuimvp/frontend

# Canvas load time (manual, with DevTools)
npm run dev
# Open DevTools > Performance > Record > Reload canvas > Stop

# State update propagation (automated, in test)
npm test -- --run perf-state-update
```

### 4.2 Backend Performance

```bash
cd intentuimvp/backend

# Intent deciphering latency (uses Logfire spans)
.venv/bin/pytest tests/app/api/test_jobs.py -v -k "intent_decipher"

# Job execution duration
.venv/bin/pytest tests/jobs/test_worker.py -v -k "execution_time"
```

## 5. Continuous Monitoring

### 5.1 Pre-Commit Gates

- No automated enforcement in MVP (manual DevTools verification)
- Future: Lighthouse CI integration

### 5.2 Production Monitoring (Future)

- OpenTelemetry metrics for NFR-OBS compliance
- Synthetic monitoring via Playwright/Puppeteer
- Real User Monitoring (RUM) via Logfire or similar

## 6. Exemptions & Notes

1. **Cold Start**: First-load may exceed 2s due to asset compilation; measure warm loads
2. **Gateway Latency**: NFR-PERF-003 assumes Gateway responds within SLA; failures are exempt
3. **Local Development**: SQLite is acceptable for baseline; PostgreSQL may show different characteristics

## 7. References

- [PRD §12.1 Performance Targets](intentuimvp/PRD.md#121-performance-targets-nfr-perf)
- [PRD §12.5 Observability](intentuimvp/PRD.md#125-observability-nfr-obs)
- Issue: [F9.1: Performance Targets](bigdaddyintentcanvasrepo-ehh)
