# Beads Dependency Conventions

This document defines the conventions for using beads dependencies in the IntentUI MVP project.

## Problem Statement

When using beads (beads), cycles can occur when trying to make epics depend on their children because parent-child edges are directional and included in cycle checks. This document establishes clear conventions to avoid such issues.

## Core Principles

1. **Parent-Child relationships are for grouping only** - They create a hierarchy for organization and reporting, not for execution dependencies
2. **Blocks relationships are for execution gating** - They define what must be completed before work can begin
3. **Never mix parent-child and blocks relationships** - This creates circular dependencies that cannot be resolved

## Convention Details

### Epic → Feature Relationship

- **DO**: Use parent-child relationship to group features under an epic
- **DO NOT**: Use `blocks` relationship from epic to child features
- **RATIONALE**: Epics are containers for organization, not execution gates

```bash
# Correct: Feature is child of epic (grouping only)
bd create --title "My Feature" --type feature --parent "E-001"
# This creates a parent-child relationship without blocks

# Incorrect: Epic blocks child feature
bd dep add E-001 F-001  # DO NOT DO THIS - creates cycle
```

### Feature → Task Relationship

- **DO**: Use `blocks` relationship to define task dependencies within a feature
- **DO**: Use parent-child relationship to group tasks under a feature
- **RATIONALE**: Tasks can have both grouping (parent-child) and execution (blocks) relationships

```bash
# Correct: Task T1 blocks task T2
bd dep add T2 T1  # T1 must complete before T2

# Also correct: T1 and T2 are children of feature F-001 (grouping)
bd create --title "Task 1" --type task --parent "F-001"
bd create --title "Task 2" --type task --parent "F-001"
```

### Task → Task Relationships

- **DO**: Use `blocks` relationship for task dependencies
- **DO NOT**: Use parent-child between tasks unless purely for grouping

## Decision Matrix

| From | To | Relationship Type | Reason |
|------|-----|------------------|--------|
| Epic | Feature | Parent-child only | Grouping, not execution gating |
| Feature | Task | Parent-child + blocks | Both grouping and dependencies OK |
| Task | Task | Blocks only | Execution dependencies |
| Epic | Task | Neither (via feature) | Always route through feature |

## Visual Representation

```
E-001 (Epic - container only)
│
├── F-001 (Feature - parent-child grouping)
│   │
│   ├── T-001 (Task - blocks T-002)
│   └── T-002 (Task - blocked by T-001)
│
├── F-002 (Feature - parent-child grouping)
│   │
│   ├── T-003 (Task - blocks T-004)
│   └── T-004 (Task - blocked by T-003)
```

## Anti-Patterns to Avoid

### ❌ Epic Directly Blocking Child

```bash
# ANTI-PATTERN: Creates cycle
E-001 (epic)
├── F-001 (feature) [blocks: E-001]  # CYCLE!
```

### ❌ Cross-Level Blocks

```bash
# ANTI-PATTERN: Tasks blocking parent features
T-001
└── F-001 [blocks: T-001]  # CYCLE if F-001 is parent of T-001
```

## Implementation Commands

```bash
# Create a feature under an epic
bd create --title "New Feature" --type feature --parent "E-001"

# Create a task under a feature
bd create --title "Task 1" --type task --parent "F-001"

# Add task dependency (T-001 must complete before T-002)
bd dep add T-002 T-001

# Check for cycles before committing
bd sync  # Will warn if cycles detected
```

## Validation

To validate correct usage:

1. **No epic should have outgoing `blocks` edges**
   ```bash
   bd show E-XXX | grep "Blocks:"  # Should be empty
   ```

2. **Parent-child relationships should not create cycles**
   ```bash
   bd sync  # Validates and reports cycles
   ```

3. **Features should have at least one task child**
   ```bash
   bd list --parent "F-XXX" --type task
   ```

## References

- Beads documentation: `bd prime` for workflow context
- Issue creation: `bd create --title "..." --type task|feature|epic`
- Dependencies: `bd dep add <blocks> <blocked>`
