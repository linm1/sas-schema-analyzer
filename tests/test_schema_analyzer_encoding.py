"""Tests for encoding fallback in SasSchemaAnalyzer.analyze_file.

All pyreadstat calls are mocked — no real .sas7bdat files are read.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd

from sas_schema_analyzer.core.schema_analyzer import SasSchemaAnalyzer


def _fake_meta(columns):
    meta = MagicMock()
    meta.file_label = "TEST"
    meta.column_names_to_labels = {c: c.upper() for c in columns}
    return meta


def _run(coro):
    return asyncio.run(coro)


class TestDefaultEncodingSuccess:
    """When pyreadstat succeeds on first call, no fallback occurs."""

    @patch("sas_schema_analyzer.core.schema_analyzer.pyreadstat.read_sas7bdat")
    @patch("sas_schema_analyzer.core.schema_analyzer.os.path.exists", return_value=True)
    def test_first_call_succeeds_no_fallback(self, _exists, mock_read, tmp_path):
        df = pd.DataFrame({"A": [1, 2, 3]})
        mock_read.return_value = (df, _fake_meta(["A"]))

        analyzer = SasSchemaAnalyzer()
        result = _run(analyzer.analyze_file(str(tmp_path / "ok.sas7bdat")))

        assert result["success"] is True
        assert mock_read.call_count == 1
        assert "encoding" not in mock_read.call_args.kwargs
        assert result.get("used_encoding") in (None, "default")
