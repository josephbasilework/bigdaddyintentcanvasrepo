"""Gateway-only enforcement test.

Scans the codebase to ensure no direct imports of LLM provider SDKs
(except in app/gateway/client.py where they are explicitly allowed).

This test enforces the Gateway-only pattern at the test level.
Run with: pytest tests/test_gateway_only_enforcement.py
"""

import ast
from pathlib import Path

import pytest

# Files that are allowed to import provider SDKs directly
ALLOWED_PROVIDER_IMPORT_FILES = {
    "app/gateway/client.py",
}

# Banned provider module names
BANNED_PROVIDERS = {
    "openai",
    "anthropic",
    "google.generativeai",  # Gemini
    "cohere",  # Cohere
    "langchain",  # LangChain (wraps providers)
}


class TestGatewayOnlyEnforcement:
    """Tests to verify Gateway-only enforcement across the codebase."""

    def test_no_direct_provider_imports(self):
        """Scan all Python files for direct provider imports."""
        violations = []
        app_dir = Path(__file__).parent.parent / "app"

        for py_file in app_dir.rglob("*.py"):
            # Skip __pycache__ and test files
            if "__pycache__" in str(py_file) or "test_" in py_file.name:
                continue

            relative_path = py_file.relative_to(app_dir.parent)
            relative_path_str = str(relative_path)

            # Skip allowed files
            if relative_path_str in ALLOWED_PROVIDER_IMPORT_FILES:
                continue

            # Parse the file and check for banned imports
            try:
                with open(py_file) as f:
                    source = f.read()

                tree = ast.parse(source, filename=str(py_file))
                imports = self._extract_imports(tree)

                for imp in imports:
                    if any(banned in imp for banned in BANNED_PROVIDERS):
                        violations.append({
                            "file": relative_path_str,
                            "import": imp,
                        })

            except SyntaxError:
                # Skip files with syntax errors (they'll be caught by other tests)
                continue

        # Format error message
        if violations:
            error_lines = [
                "\nDirect LLM provider SDK imports detected!",
                "All LLM calls must go through GatewayClient (app/gateway/client.py).",
                "\nViolations found:",
            ]
            for v in violations:
                error_lines.append(f"  - {v['file']}: {v['import']}")

            error_lines.append(
                f"\nAllowed files: {', '.join(sorted(ALLOWED_PROVIDER_IMPORT_FILES))}"
            )

            pytest.fail("\n".join(error_lines))

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract all import names from an AST."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
                    for alias in node.names:
                        full_import = f"{node.module}.{alias.name}"
                        imports.append(full_import)

        return imports

    def test_gateway_client_allowed_imports(self):
        """Verify that gateway/client.py is explicitly allowed."""
        app_dir = Path(__file__).parent.parent / "app"
        gateway_client = app_dir / "gateway" / "client.py"

        assert gateway_client.exists(), "app/gateway/client.py must exist"
        assert str(gateway_client.relative_to(app_dir.parent)) in ALLOWED_PROVIDER_IMPORT_FILES
