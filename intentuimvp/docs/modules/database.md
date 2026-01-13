# Database Connection

**Bounded Context:** Data Management
**Location:** `intentuimvp/backend/app/database.py`
**PRD References:** §15 Data Storage, NFR-MAINT-003

---

## Where

**Location in codebase:**
- File path: `intentuimvp/backend/app/database.py`
- Parent module: Data Management Context
- Related modules: All repositories, all models

**Physical placement:**
- Directory: `backend/app/` (root-level for universal access)
- Entry points: `get_async_db()`, `get_db()`, `AsyncSessionLocal`, `Base`

---

## What

**Purpose:** Provide database connection and session management for SQLAlchemy.

**Responsibilities:**
- Async and sync engine creation
- Session factory management
- Dependency injection for FastAPI endpoints
- Database URL conversion (sync → async)
- Base class for SQLAlchemy models

**Key entities/exports:**
- `Base` - Declarative base for all SQLAlchemy models
- `async_engine` - Async SQLAlchemy engine
- `AsyncSessionLocal` - Async session factory
- `get_async_db()` - Dependency injection for async sessions
- `engine` - Sync engine (for backwards compatibility)
- `SessionLocal` - Sync session factory (for backwards compatibility)

---

## How

**Implementation approach:**

SQLAlchemy 2.0 async-first pattern:
1. Create async engine from `database_url` (with URL conversion)
2. Create session factory with `expire_on_commit=False`
3. Provide dependency injection helpers for FastAPI

**Key algorithms/patterns:**

- **URL conversion**: `sqlite://` → `sqlite+aiosqlite://`, `postgresql://` → `postgresql+asyncpg://`
- **Async generator pattern**: `get_async_db()` yields session with cleanup in `finally`
- **Session context manager**: Ensures proper cleanup on exceptions

**Dependencies:**
- Internal: `app.config` (settings, DATABASE_URL)
- External: `sqlalchemy` (core, ORM, async), `aiosqlite` (SQLite async driver), `asyncpg` (PostgreSQL async driver)

**Data flow:**
```
FastAPI endpoint → Depends(get_async_db)
  → AsyncSessionLocal() → session
  → [endpoint uses session]
  → finally: session.close()
```

---

## Why

**Problem being solved:**

Consistent database access patterns across the application:
1. Centralized connection configuration
2. Async-first for FastAPI performance
3. Proper session lifecycle management
4. Easy testing with `INTENTUI_TEST_DATABASE_URL` override

**Design decisions:**

1. **Async-first**: Primary API is async, sync is legacy
   - Rationale: FastAPI is async-first, better performance

2. **expire_on_commit=False**: Objects remain accessible after transaction
   - Rationale: Simplifies code, prevents detached instance errors

3. **Test URL override**: `INTENTUI_TEST_DATABASE_URL` environment variable
   - Rationale: Easy test isolation without changing production code

4. **SQLite for development**: Default URL is `sqlite:///./intentui.db`
   - Rationale: Zero configuration for local development

**Trade-offs:**

- **Sync retained**: Maintains `engine` and `SessionLocal` for backwards compatibility
  - Accepted: Some legacy code may still use sync; can be removed later

- **Global state**: Module-level engine and session factories
  - Accepted: Standard SQLAlchemy pattern; lifecycle matches app process

**Alternatives considered:**

- Pydantic-based ORM (Piccolo, Tortoise) - **Rejected**: SQLAlchemy is more mature
- Multiple databases - **Rejected**: No current requirement for multi-DB
- Connection pooling middleware - **Rejected**: SQLAlchemy handles pooling internally

---

## Acceptance Criteria

- [x] Async sessions work with FastAPI dependency injection
- [x] SQLite URLs converted to aiosqlite format
- [x] PostgreSQL URLs converted to asyncpg format
- [x] Sessions properly closed on exception
- [x] `INTENTUI_TEST_DATABASE_URL` overrides production URL
- [x] All models inherit from `Base` class

---

## Testing

**Test coverage:**
- Unit tests: `tests/unit/test_database.py`
- Integration tests: Covered by repository tests
- Coverage target: 70%+ (simple module)

**Key test scenarios:**
- `get_async_db()` yields session that closes properly
- SQLite URL converted to `sqlite+aiosqlite://`
- PostgreSQL URL converted to `postgresql+asyncpg://`
- Test database URL override works
- `Base` class provides declarative metadata

---

## Future Work

- [ ] Remove sync engine and SessionLocal (when fully migrated)
- [ ] Add connection pooling configuration options
- [ ] Add health check endpoint for database connectivity
- [ ] Consider read replica support for scaling
- [ ] Add migration status tracking

---

**Last Updated:** 2026-01-13
**Author:** nastysandbox
