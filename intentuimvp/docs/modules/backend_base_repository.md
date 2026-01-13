# Base Repository Module

**Bounded Context:** Data Management
**Location:** `intentuimvp/backend/app/repositories/base.py`
**PRD References:** NFR-MAINT-003 (Modular Architecture)

---

## Where

**Location:** `intentuimvp/backend/app/repositories/base.py`

**Part of:** Data Management Context (Repository Layer)

**Imports:**
- `abc` - Abstract base class
- `sqlalchemy` - SQLAlchemy core (AsyncSession, select, func)
- `pydantic` - BaseModel for schema types
- `typing` - Generic type variables

**Exports:**
- `BaseRepository` - Abstract base class with CRUD operations

---

## What

**Purpose:** Provides a generic, async CRUD interface for SQLAlchemy models using the Repository pattern.

**Description:** BaseRepository is the abstract foundation for all data access in IntentUI. It encapsulates common database operations (create, read, update, delete, list, count) behind a clean interface. Subclasses only need to specify the SQLAlchemy model.

**Key Types/Classes:**
- `BaseRepository<ModelType, CreateSchemaType, UpdateSchemaType>` - Generic base with full CRUD
- Type variables enforce compile-time type safety for model and schema pairs

---

## How

**Implementation approach:** Abstract base class with Generic typing for SQLAlchemy async operations.

**Key algorithms/flows:**

**1. Generic Type Parameters:**
```python
ModelType = TypeVar("ModelType", bound=Base)  # SQLAlchemy model
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)  # Pydantic create schema
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)  # Pydantic update schema
```

**2. CRUD Operations:**
- `create(**kwargs)` → Insert new row, commit, refresh, return model
- `get_by_id(id)` → Select by primary key, return model or None
- `list(offset, limit, order_by)` → Paginated select, return list
- `update(id, **kwargs)` → Fetch, apply updates, commit, refresh
- `delete(id)` → Fetch, delete, commit, return bool
- `count()` → Select count(*), return int

**3. Abstract Property:**
- `model` (abstractmethod) - Subclass must provide SQLAlchemy model class

**Dependencies:**
- Internal: `app.database.Base` (SQLAlchemy base model)
- External: `sqlalchemy` (ORM core), `pydantic` (schemas)

**State management:**
- Receives `AsyncSession` in `__init__`
- No internal state (stateless repository pattern)
- Session lifecycle managed by caller (dependency injection)

---

## Why

**Rationale:** NFR-MAINT-003 requires "Modular Architecture" with "clear interfaces". The Repository pattern abstracts database access, prevents raw SQL in business logic, and enables easy testing via mocking.

**Design decisions:**
- **Generic base class** - DRY: avoid duplicating CRUD in every repository
- **Async only** - Matches FastAPI's async model throughout the stack
- **Abstract model property** - Compile-time enforcement: subclass MUST specify model
- **Type variables** - Catch type errors at compile time (model ↔ schema mismatch)
- **Session injection** - Enables transaction control and unit testing

**Alternatives considered:**
- Direct SQLAlchemy in business logic - Rejected (tight coupling, hard to test, raw SQL)
- Sync repositories - Rejected (blocks async worker pool)
- Separate read/write models (CQRS) - Rejected (overkill for MVP scale)

**Trade-offs:**
- **Gain:** Clean separation between business logic and data layer
- **Gain:** Easy to mock for unit tests
- **Gain:** Consistent interface across all repositories
- **Loss:** One level of indirection (justified by testability)
- **Gain:** Type safety with generics prevents model/schema mismatches

---

## Acceptance Criteria

- [x] Abstract base class with CRUD operations
- [x] Generic type parameters for model and schemas
- [x] Async session dependency injection
- [x] All subclasses must implement `model` property
- [x] Stateless (no internal state beyond session)

---

## Testing

**Test location:** `intentuimvp/backend/app/repositories/test_base.py` (to be created)

**Coverage notes:**
- Mock subclass for testing abstract base
- CRUD operations with test model
- Pagination in `list()`
- Non-existent ID returns None
- Session lifecycle (commit/refresh behavior)

---

## Future Work

- [ ] Add `bulk_create()` for batch inserts
- [ ] Add `bulk_update()` for batch updates
- [ ] Consider soft delete support
- [ ] Add `exists(id)` method

---

**Last Updated:** 2026-01-13
**Author:** System (BigDaddyIntentCanvasRepo)
