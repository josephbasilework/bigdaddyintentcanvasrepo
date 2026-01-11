"""Pytest configuration for IntentUI backend tests."""

import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

DEFAULT_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"intentui_test_{uuid4().hex}.db"
DEFAULT_TEST_DB_URL = f"sqlite:///{DEFAULT_TEST_DB_PATH}"
TEST_DB_URL = os.environ.setdefault("INTENTUI_TEST_DATABASE_URL", DEFAULT_TEST_DB_URL)
TEST_DB_PATH = (
    Path(TEST_DB_URL.replace("sqlite:///", "", 1))
    if TEST_DB_URL.startswith("sqlite:///")
    else None
)
os.environ.setdefault("PYDANTIC_GATEWAY_API_KEY", "test-key")

# Add backend root to Python path for imports
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # This runs before test collection
    backend_root = Path(__file__).parent.parent
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    import app.models  # noqa: F401
    from app.database import Base, engine
    from app.models.intent import Base as IntentBase

    Base.metadata.create_all(bind=engine)
    IntentBase.metadata.create_all(bind=engine)


def pytest_sessionfinish(session, exitstatus):
    """Clean up test database files."""
    if TEST_DB_PATH and TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
