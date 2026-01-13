# Canvas Store Module

**Bounded Context:** Workspace
**Location:** `intentuimvp/frontend/src/state/canvasStore.ts`
**PRD References:** FR-001 (Canvas Initialization), FR-002 (Canvas Node CRUD)

---

## Where

**Location:** `intentuimvp/frontend/src/state/canvasStore.ts`

**Part of:** Workspace Context (Frontend State Management)

**Imports:**
- `zustand` - Lightweight state management

**Exports:**
- `useCanvasStore` - Zustand hook for canvas state
- `CanvasNode`, `CanvasEdge`, `CanvasDocument` - Canvas entity types
- `JobData`, `PlanData`, `DAGData` - Specialized node data types

---

## What

**Purpose:** Manages the client-side canvas state (nodes, edges, selection) with undo/redo history.

**Description:** The canvas store is the single source of truth for all canvas state in the frontend. It provides reactive state updates via Zustand, supports undo/redo with history snapshots, and handles multi-select operations. All canvas mutations flow through this store.

**Key Types/Classes:**
- `CanvasState` - Store interface with state and actions
- `CanvasNode` - Node entity with position, type, and typed data
- `CanvasEdge` - Edge with source/target and relation type
- `CanvasSnapshot` - History snapshot (nodes, edges, documents)

---

## How

**Implementation approach:** Zustand store with manual history management via snapshots.

**Key algorithms/flows:**

**1. State Structure:**
```typescript
{
  canvasId: number | null,
  canvasName: string | null,
  nodes: CanvasNode[],
  edges: CanvasEdge[],
  documents: CanvasDocument[],
  selectedNodeId: string | null,      // Single selection (primary)
  selectedNodeIds: string[],          // Multi-select
  past: CanvasSnapshot[],             // Undo stack
  future: CanvasSnapshot[],           // Redo stack
}
```

**2. History-Aware Updates:**
- `withHistory()` helper wraps state updaters
- Before mutation: push current state to `past` (max 50)
- After mutation: clear `future` (new branch)
- Direct setters (e.g., `setNodes`) don't record history (for bulk loads)

**3. Node Types (discriminated union via `type` field):**
- `text` - Basic text note
- `document` - Rich text document
- `audio` - Audio recording block
- `graph` - Graph visualization (with `graphAnnotation`)
- `plan` - Plan node (with `planData`)
- `dag` - Task DAG visualization (with `dagData`)
- `dashboard` - Dashboard widget
- `job` - Background job (with `jobData` for progress)

**4. Selection Modes:**
- **Single click:** Replace selection with clicked node
- **Ctrl+click:** Toggle clicked node in/out of selection
- **Shift+click:** Add clicked node to selection
- Handled in `selectNode(nodeId, { additive, toggle })`

**5. Cascade Deletes:**
- `removeNode()` also removes connected edges and documents
- `removeNodes()` handles bulk deletes

**6. ID Generation:**
```typescript
node ID: `node-${Date.now()}-${random}`
edge ID: `edge-${Date.now()}-${random}`
```

**Dependencies:**
- Internal: None (leaf module)
- External: `zustand` (state management)

**State management:**
- Zustand hook pattern (`useCanvasStore`)
- History stored in store (not localStorage)
- Persisted to backend via separate save logic

---

## Why

**Rationale:** FR-001 and FR-002 require canvas state management with nodes, edges, and selection. Zustand provides a lightweight alternative to Redux with TypeScript support and no boilerplate.

**Design decisions:**
- **Zustand over Redux** - Less boilerplate, better TypeScript, smaller bundle
- **Manual history over library** - Simple snapshot approach; no time-travel needed
- **Multi-select with primary node** - Enables linked operations (e.g., "connect to selection")
- **Cascade deletes** - Maintain referential integrity (no dangling edges)
- **Direct setters bypass history** - Bulk loads from backend shouldn't create undo entries
- **50-history limit** - Prevents unbounded memory growth

**Alternatives considered:**
- Redux - Rejected (boilerplate-heavy, larger bundle)
- React Context - Rejected (no fine-grained reactivity, performance issues)
- URL state sync - Rejected (canvas too large for URL)
- Backend-only state - Rejected (latency unacceptable for drag/pan)

**Trade-offs:**
- **Gain:** Simple, intuitive API
- **Gain:** Excellent TypeScript support
- **Gain:** No middleware boilerplate
- **Loss:** History in memory (lost on refresh) - acceptable with backend persistence
- **Gain:** Fine-grained reactivity (only dependent components re-render)

---

## Acceptance Criteria

- [x] CRUD operations for nodes (add, remove, update, position)
- [x] CRUD operations for edges (add, remove, update)
- [x] Multi-select with additive/toggle modes
- [x] Undo/redo with history (50 snapshots max)
- [x] Cascade deletes (node removes edges, documents)
- [x] Typed node data (job, plan, dag, graph)
- [x] Bulk setters bypass history (for backend sync)

---

## Testing

**Test location:** `intentuimvp/frontend/src/state/canvasStore.test.ts`

**Coverage notes:**
- Node CRUD operations
- Edge CRUD operations
- Selection modes (single, additive, toggle)
- Undo/redo with history branching
- Cascade deletes on node removal
- History limit (50 snapshots)

---

## Future Work

- [ ] Partial updates (node moves only) to reduce re-renders
- [ ] Optimistic updates with rollback on error
- [ ] LocalStorage persistence for crash recovery
- [ ] Virtual scrolling for 1000+ nodes

---

**Last Updated:** 2026-01-13
**Author:** System (BigDaddyIntentCanvasRepo)
