# Module Documentation

**PRD Reference:** NFR-MAINT-002 - Where/What/How/Why module documentation

This directory contains module-level documentation for IntentUI's key modules using the **Where/What/How/Why** framework.

---

## Quick Index

### Backend Modules

| Module | Bounded Context | Description |
|--------|---------------|-------------|
| [Gateway Client](./backend_gateway_client.md) | Integration | Pydantic AI Gateway client (EI-001 enforcement) |
| [Context Router](./backend_context_router.md) | Agent | Command routing with 3-priority algorithm (FR-006) |
| [Base Repository](./backend_base_repository.md) | Data Management | Generic CRUD base for SQLAlchemy models |

### Frontend Modules

| Module | Bounded Context | Description |
|--------|---------------|-------------|
| [AG-UI Protocol](./frontend_agui_protocol.md) | Agent | Agent-UI WebSocket communication types (FR-009) |
| [Canvas Store](./frontend_canvas_store.md) | Workspace | Zustand store for canvas state (FR-001, FR-002) |

---

## Documentation Template

When adding new module documentation, use the template at [`../MODULE_DOCS_TEMPLATE.md`](../MODULE_DOCS_TEMPLATE.md).

### Quick Reference Card Format

For inline code comments, use this condensed format:

```python
# ============================================================================
# MODULE: [Name]
# WHERE: [path/to/module]
# WHAT: [One-line summary]
# HOW: [Implementation approach in 1-2 sentences]
# WHY: [Rationale in 1-2 sentences]
# ============================================================================
```

---

## Adding New Module Docs

1. Copy the template from `../MODULE_DOCS_TEMPLATE.md`
2. Fill in all sections (Where, What, How, Why, Acceptance Criteria, Testing, Future Work)
3. Name the file: `[context]_[module_name].md` (e.g., `backend_gateway_client.md`)
4. Update this index with a link to the new doc
5. Run linters to ensure formatting is correct

---

## Related Documentation

- [BOUNDED_CONTEXTS.md](../BOUNDED_CONTEXTS.md) - Architecture overview and module map
- [TEST_COVERAGE.md](../../TEST_COVERAGE.md) - Coverage targets and enforcement
- [PRD.md](../PRD.md) - Requirements specification

---

**Last Updated:** 2026-01-13
**PRD Reference:** NFR-MAINT-002, §12.7
