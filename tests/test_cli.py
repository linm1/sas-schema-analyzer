"""
TDD tests for the sas-schema CLI (cli.py).

RED phase: all tests fail because cli.py does not exist yet.
GREEN phase: tests pass after cli.py is implemented.

Tests use argparse + asyncio stubs and tmp_path to avoid needing real SAS files.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke_cli(args: List[str], capsys) -> Tuple[int, str, str]:
    """Call cli.main() with the given sys.argv args, return (exit_code, stdout, stderr)."""
    from sas_schema_analyzer import cli

    with patch("sys.argv", ["sas-schema"] + args):
        try:
            cli.main()
            exit_code = 0
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1

    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


FAKE_FILE_RESULT = {
    "success": True,
    "file_path": "/data/cars.sas7bdat",
    "row_count": 428,
    "column_count": 15,
    "columns": [{"name": "Make", "sas_data_type": "character"}],
}

FAKE_FOLDER_RESULT = {
    "success": True,
    "folder_path": "/data/",
    "successful_analyses": 2,
    "failed_analyses": 0,
    "results": [
        {**FAKE_FILE_RESULT, "file_path": "/data/cars.sas7bdat"},
        {**FAKE_FILE_RESULT, "file_path": "/data/demog.sas7bdat", "column_count": 10},
    ],
}

FAKE_LIST_RESULT = {
    "success": True,
    "directory": "/data/",
    "files_found": 2,
    "files": [
        {"file_path": "/data/cars.sas7bdat", "size_bytes": 102400},
        {"file_path": "/data/demog.sas7bdat", "size_bytes": 51200},
    ],
}


# ---------------------------------------------------------------------------
# Module import test
# ---------------------------------------------------------------------------

class TestCliModuleExists:
    def test_package_import_does_not_import_server(self):
        """Importing the package must not eagerly import the MCP server."""
        sys.modules.pop("sas_schema_analyzer.server", None)
        sys.modules.pop("sas_schema_analyzer", None)

        __import__("sas_schema_analyzer")

        assert "sas_schema_analyzer.server" not in sys.modules

    def test_package_main_reports_missing_fastmcp(self):
        """Package main() must fail clearly when server-only deps are unavailable."""
        import sas_schema_analyzer

        missing_dependency = ModuleNotFoundError(
            "No module named 'fastmcp'",
            name="fastmcp",
        )

        with patch("sas_schema_analyzer.import_module", side_effect=missing_dependency):
            with pytest.raises(SystemExit, match="Python 3\.10\+"):
                sas_schema_analyzer.main()

    def test_cli_module_importable(self):
        """cli.py must exist and be importable."""
        from sas_schema_analyzer import cli  # noqa: F401

    def test_cli_has_main(self):
        """cli module must expose a main() callable."""
        from sas_schema_analyzer import cli
        assert callable(cli.main)


# ---------------------------------------------------------------------------
# analyze sub-command — single file
# ---------------------------------------------------------------------------

class TestAnalyzeSingleFile:
    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_analyze_single_file_stdout(self, MockAnalyzer, capsys, tmp_path):
        """analyze <file.sas7bdat> prints JSON to stdout."""
        sas_file = tmp_path / "cars.sas7bdat"
        sas_file.touch()

        instance = MockAnalyzer.return_value
        instance.analyze_file = AsyncMock(return_value=FAKE_FILE_RESULT)

        exit_code, out, _ = _invoke_cli(["analyze", str(sas_file)], capsys)

        assert exit_code == 0
        data = json.loads(out)
        assert data["success"] is True
        assert data["column_count"] == 15

    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_analyze_single_file_output_flag(self, MockAnalyzer, capsys, tmp_path):
        """analyze <file> --output out.json writes JSON to that file."""
        sas_file = tmp_path / "cars.sas7bdat"
        sas_file.touch()
        out_file = tmp_path / "schema.json"

        instance = MockAnalyzer.return_value
        instance.analyze_file = AsyncMock(return_value=FAKE_FILE_RESULT)

        exit_code, stdout, _ = _invoke_cli(
            ["analyze", str(sas_file), "--output", str(out_file)], capsys
        )

        assert exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["success"] is True

    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_analyze_single_file_failure_exits_1(self, MockAnalyzer, capsys, tmp_path):
        """analyze returns exit code 1 when analysis reports failure."""
        sas_file = tmp_path / "bad.sas7bdat"
        sas_file.touch()

        instance = MockAnalyzer.return_value
        instance.analyze_file = AsyncMock(
            return_value={"success": False, "error": "Corrupt file", "file_path": str(sas_file)}
        )

        exit_code, _, _ = _invoke_cli(["analyze", str(sas_file)], capsys)
        assert exit_code == 1


# ---------------------------------------------------------------------------
# analyze sub-command — batch (directory)
# ---------------------------------------------------------------------------

class TestAnalyzeBatch:
    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_analyze_directory_writes_individual_jsons(self, MockAnalyzer, capsys, tmp_path):
        """analyze <dir> writes one .json per result next to its source file."""
        # Create fake SAS files so the dir exists
        (tmp_path / "cars.sas7bdat").touch()
        (tmp_path / "demog.sas7bdat").touch()

        # Patch folder result to reference our tmp_path files
        folder_result = {
            **FAKE_FOLDER_RESULT,
            "folder_path": str(tmp_path),
            "results": [
                {**FAKE_FILE_RESULT, "file_path": str(tmp_path / "cars.sas7bdat")},
                {**FAKE_FILE_RESULT, "file_path": str(tmp_path / "demog.sas7bdat"), "column_count": 10},
            ],
        }

        instance = MockAnalyzer.return_value
        instance.analyze_folder = AsyncMock(return_value=folder_result)

        exit_code, out, _ = _invoke_cli(["analyze", str(tmp_path)], capsys)

        assert exit_code == 0
        assert (tmp_path / "cars.json").exists()
        assert (tmp_path / "demog.json").exists()
        cars_data = json.loads((tmp_path / "cars.json").read_text())
        assert cars_data["success"] is True

    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_analyze_directory_prints_summary(self, MockAnalyzer, capsys, tmp_path):
        """analyze <dir> prints a summary line to stdout."""
        folder_result = {
            **FAKE_FOLDER_RESULT,
            "folder_path": str(tmp_path),
            "results": [],
        }
        instance = MockAnalyzer.return_value
        instance.analyze_folder = AsyncMock(return_value=folder_result)

        exit_code, out, _ = _invoke_cli(["analyze", str(tmp_path)], capsys)

        assert exit_code == 0
        # Summary must mention success/fail counts
        assert "2" in out or "success" in out.lower()

    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_analyze_respects_recursive_flag(self, MockAnalyzer, capsys, tmp_path):
        """--recursive is forwarded to analyze_folder."""
        folder_result = {**FAKE_FOLDER_RESULT, "folder_path": str(tmp_path), "results": []}
        instance = MockAnalyzer.return_value
        instance.analyze_folder = AsyncMock(return_value=folder_result)

        _invoke_cli(["analyze", str(tmp_path), "--recursive"], capsys)

        call_kwargs = instance.analyze_folder.call_args
        assert call_kwargs.kwargs.get("recursive") is True or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] is True
        )


# ---------------------------------------------------------------------------
# list sub-command
# ---------------------------------------------------------------------------

class TestListCommand:
    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_list_prints_json(self, MockAnalyzer, capsys, tmp_path):
        """list <dir> prints JSON with file listing."""
        instance = MockAnalyzer.return_value
        instance.list_sas_files = AsyncMock(return_value=FAKE_LIST_RESULT)

        exit_code, out, _ = _invoke_cli(["list", str(tmp_path)], capsys)

        assert exit_code == 0
        data = json.loads(out)
        assert data["files_found"] == 2

    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_list_failure_exits_1(self, MockAnalyzer, capsys, tmp_path):
        """list exits 1 when listing fails."""
        instance = MockAnalyzer.return_value
        instance.list_sas_files = AsyncMock(
            return_value={"success": False, "error": "No access"}
        )

        exit_code, _, _ = _invoke_cli(["list", str(tmp_path)], capsys)
        assert exit_code == 1


# ---------------------------------------------------------------------------
# --threshold and --max-files forwarding
# ---------------------------------------------------------------------------

class TestOptionForwarding:
    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_threshold_forwarded(self, MockAnalyzer, capsys, tmp_path):
        """--threshold is forwarded to SasSchemaAnalyzer constructor."""
        sas_file = tmp_path / "cars.sas7bdat"
        sas_file.touch()
        instance = MockAnalyzer.return_value
        instance.analyze_file = AsyncMock(return_value=FAKE_FILE_RESULT)

        _invoke_cli(["analyze", str(sas_file), "--threshold", "0.05"], capsys)

        MockAnalyzer.assert_called_once_with(code_list_threshold=pytest.approx(0.05), debug=False)

    @patch("sas_schema_analyzer.cli.SasSchemaAnalyzer")
    def test_max_files_forwarded(self, MockAnalyzer, capsys, tmp_path):
        """--max-files is forwarded to analyze_folder."""
        folder_result = {**FAKE_FOLDER_RESULT, "folder_path": str(tmp_path), "results": []}
        instance = MockAnalyzer.return_value
        instance.analyze_folder = AsyncMock(return_value=folder_result)

        _invoke_cli(["analyze", str(tmp_path), "--max-files", "5"], capsys)

        call_kwargs = instance.analyze_folder.call_args
        # max_files could be positional or keyword
        all_args = list(call_kwargs.args) + list(call_kwargs.kwargs.values())
        assert 5 in all_args or call_kwargs.kwargs.get("max_files") == 5
