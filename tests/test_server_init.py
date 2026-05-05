"""
TDD RED phase — server initialization tests for sas_schema_analyzer.

These tests verify that the FastMCP server is constructed correctly after the
FastMCP v3.1.0 breaking change that removed the `dependencies` kwarg.

Bug: FastMCP(dependencies=[...]) raises TypeError in v3.1.0+.
Fix: Remove the `dependencies` kwarg from the FastMCP() call in server.py line 46.

All three tests are expected to PASS once the fix is applied.
"""

import ast
import inspect
import sys
from pathlib import Path
from typing import Optional

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Server initialization tests require Python 3.10+.",
        allow_module_level=True,
    )

fastmcp = pytest.importorskip(
    "fastmcp",
    reason="Server initialization tests require fastmcp on Python 3.10+.",
)
FastMCP = fastmcp.FastMCP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SERVER_PY = Path(__file__).parent.parent / "sas_schema_analyzer" / "server.py"


def _parse_fastmcp_call(source: str) -> Optional[ast.Call]:
    """Return the first ast.Call node whose function name is 'FastMCP'."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Bare name: FastMCP(...)
            if isinstance(func, ast.Name) and func.id == "FastMCP":
                return node
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFastMCPInstance:
    """Verify that the module-level `mcp` object is a valid FastMCP instance."""

    def test_fastmcp_instance_created(self):
        """Importing the server module must not raise and mcp must be a FastMCP."""
        # Import is intentionally deferred so that a constructor TypeError
        # surfaces as a test failure rather than a collection error.
        import sas_schema_analyzer.server as server_module

        assert isinstance(server_module.mcp, FastMCP), (
            f"Expected mcp to be an instance of FastMCP, got {type(server_module.mcp)}"
        )

    def test_mcp_has_correct_name(self):
        """The FastMCP instance must advertise the canonical server name."""
        import sas_schema_analyzer.server as server_module

        assert server_module.mcp.name == "SAS Schema Analyzer", (
            f"Expected mcp.name == 'SAS Schema Analyzer', got {server_module.mcp.name!r}"
        )


class TestFastMCPConstructorSignature:
    """Verify that server.py does not pass the removed `dependencies` kwarg."""

    def test_no_dependencies_kwarg(self):
        """
        Inspect the AST of server.py to confirm `dependencies` is not passed
        as a keyword argument to FastMCP().

        FastMCP v3.1.0 removed this parameter; its presence causes a TypeError
        at import time, breaking the MCP server entirely.
        """
        source = SERVER_PY.read_text(encoding="utf-8")
        call_node = _parse_fastmcp_call(source)

        assert call_node is not None, (
            "Could not locate a FastMCP(...) constructor call in server.py. "
            "Ensure the module-level mcp = FastMCP(...) assignment is present."
        )

        kwarg_names = [kw.arg for kw in call_node.keywords]

        assert "dependencies" not in kwarg_names, (
            "FastMCP() is called with a `dependencies` kwarg in server.py. "
            "This parameter was removed in FastMCP v3.1.0 and causes a TypeError. "
            f"Keywords found: {kwarg_names}"
        )
