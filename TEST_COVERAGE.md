# Test Coverage Targets & CI Enforcement

**PRD Reference:** NFR-MAINT-004 - Test Coverage & CI Enforcement

## Overview

This document defines the test coverage targets and CI enforcement strategy for IntentUI MVP. It ensures code quality, maintainability, and confidence in deployments through automated testing.

## Coverage Targets

### Backend (Python/FastAPI)

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Line Coverage** | 80% | Balance between thoroughness and pragmatism |
| **Branch Coverage** | 75% | Ensure critical logic paths are tested |
| **Function Coverage** | 85% | Most functions should have tests |

**Key Areas Requiring Higher Coverage (90%+):**
- Gateway client (single point of LLM interaction)
- Agent orchestration logic
- Workspace state management
- Security checks (prompt injection, secret redaction)

**Exclusions (with justification):**
- Configuration models (pydantic validation covers this)
- Simple data transfer objects (DTOs)
- Development/debugging endpoints

### Frontend (Next.js/React)

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Line Coverage** | 75% | UI code has more dynamic patterns |
| **Branch Coverage** | 70% | Component logic varies |
| **Function Coverage** | 80% | Core utilities and hooks |

**Key Areas Requiring Higher Coverage (85%+):**
- AG-UI protocol layer
- State management (Zustand stores)
- WebSocket state sync
- Canvas mutation operations
- Critical hooks (useWebSocket, useAutoSave)

**Exclusions (with justification):**
- Static component props rendering
- Type definitions (TypeScript covers this)
- Third-party integration glue code

## Implementation

### Backend Coverage Setup

**Tool:** `coverage.py` (already in requirements.txt)

**Configuration:** Create `intentuimvp/backend/.coveragerc`:

```ini
[run]
source = app
omit =
    */tests/*
    */conftest.py
    */__pycache__/*
    */migrations/*
    */test_*.py

[report]
precision = 2
show_missing = true
skip_empty = true
sort = Cover

[html]
directory = htmlcov
```

**Usage:**
```bash
# Run tests with coverage
cd intentuimvp/backend
.venv/bin/pytest --cov=app --cov-report=term --cov-report=html

# Generate coverage report
.venv/bin/coverage report
.venv/bin/coverage html  # Open htmlcov/index.html
```

### Frontend Coverage Setup

**Tool:** Vitest built-in coverage (using `c8`)

**Configuration:** Update `intentuimvp/frontend/vitest.config.ts`:

```typescript
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.test.ts',
        '**/*.test.tsx',
        '**/*.config.*',
        '**/dist/**',
      ],
      thresholds: {
        lines: 75,
        functions: 80,
        branches: 70,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

**Usage:**
```bash
cd intentuimvp/frontend
npm run test -- --run --coverage
```

## CI Enforcement

### GitHub Actions Updates

**Add to `.github/workflows/ci.yml`:**

```yaml
coverage-backend:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: intentuimvp/backend
  steps:
    - name: Checkout
      uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
        cache: "pip"
        cache-dependency-path: intentuimvp/backend/requirements.txt
    - name: Install backend dependencies
      run: |
        python -m pip install --upgrade pip
        python -m pip install --no-deps -r requirements.txt
    - name: Run tests with coverage
      run: pytest --cov=app --cov-report=xml --cov-report=term
    - name: Check coverage thresholds
      run: coverage report --fail-under=80
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: intentuimvp/backend/coverage.xml
        flags: backend
        token: ${{ secrets.CODECOV_TOKEN }}

coverage-frontend:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: intentuimvp/frontend
  steps:
    - name: Checkout
      uses: actions/checkout@v4
    - name: Set up Node
      uses: actions/setup-node@v4
      with:
        node-version: "20"
        cache: "npm"
        cache-dependency-path: intentuimvp/frontend/package-lock.json
    - name: Install frontend dependencies
      run: npm ci
    - name: Run tests with coverage
      run: npm run test -- --run --coverage
    - name: Check coverage thresholds
      run: |
        COVERAGE=$(cat coverage/coverage-summary.json | jq '.total.lines.pct')
        if (( $(echo "$COVERAGE < 75" | bc -l) )); then
          echo "Coverage $COVERAGE% is below 75% threshold"
          exit 1
        fi
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: intentuimvp/frontend/coverage/coverage-final.json
        flags: frontend
        token: ${{ secrets.CODECOV_TOKEN }}
```

### Pre-commit Hook (Optional)

Add to `.pre-commit-config.yaml` for local enforcement:

```yaml
  - repo: local
    hooks:
      - id: pytest-cov
        name: pytest with coverage
        entry: bash -c 'cd intentuimvp/backend && .venv/bin/pytest --cov=app --cov-report=term-missing --cov-fail-under=80'
        language: system
        pass_filenames: false
        always_run: true
```

## Coverage Reporting

### Dashboard Integration

1. **Codecov** (Recommended):
   - Free for open source
   - PR comments showing coverage diff
   - Trend tracking over time
   - Token required in GitHub secrets

2. **GitHub-native** (Alternative):
   - Use coverage annotations in PRs
   - Store coverage JSON as artifact
   - Simple script to comment on PRs

### Local Development

```bash
# Backend - see which lines aren't covered
cd intentuimvp/backend
.venv/bin/pytest --cov=app --cov-report=term-missing

# Frontend - open HTML report
cd intentuimvp/frontend
npm run test -- --run --coverage
# Open coverage/index.html in browser
```

## Phase-in Strategy

### Phase 1: Baseline (Current)
- Run coverage reports without enforcement
- Document current coverage levels
- Identify gaps

### Phase 2: Gradual Enforcement
- Set initial thresholds at current levels - 5%
- Increment thresholds by 5% per sprint
- Require PR comments for coverage drops

### Phase 3: Full Enforcement
- Enforce 80%/75% targets
- Block PRs that drop coverage
- Require tests for new code paths

## Tracking

| Milestone | Backend Coverage | Frontend Coverage | Status |
|-----------|------------------|-------------------|--------|
| Baseline | TBD | TBD | Pending |
| Phase 2 | Current - 5% | Current - 5% | Pending |
| Phase 3 | 80% | 75% | Target |

## Acceptance Criteria

- [x] Coverage targets defined (this document)
- [ ] Backend `.coveragerc` created
- [ ] Frontend `vitest.config.ts` updated with coverage
- [ ] CI workflow updated with coverage jobs
- [ ] Baseline coverage measured
- [ ] Coverage reporting integrated (Codecov or GitHub-native)
- [ ] Pre-commit hook added (optional)
