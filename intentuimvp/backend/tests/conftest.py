"""Pytest configuration for IntentUI backend tests."""

import sys
from pathlib import Path

# Add backend root to Python path for imports
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # This runs before test collection
    backend_root = Path(__file__).parent.parent
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
