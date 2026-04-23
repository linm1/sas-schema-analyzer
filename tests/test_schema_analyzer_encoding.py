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


class TestLatin1Fallback:
    """When first call raises UnicodeDecodeError, retry with encoding='latin1'."""

    @patch("sas_schema_analyzer.core.schema_analyzer.pyreadstat.read_sas7bdat")
    @patch("sas_schema_analyzer.core.schema_analyzer.os.path.exists", return_value=True)
    def test_unicode_error_triggers_latin1_retry(self, _exists, mock_read, tmp_path):
        df = pd.DataFrame({"A": [1, 2]})

        def side_effect(path, **kwargs):
            if "encoding" not in kwargs:
                raise UnicodeDecodeError(
                    "utf-8", b"\xe4", 24, 25, "invalid continuation byte"
                )
            assert kwargs["encoding"] == "latin1"
            return (df, _fake_meta(["A"]))

        mock_read.side_effect = side_effect

        analyzer = SasSchemaAnalyzer()
        result = _run(analyzer.analyze_file(str(tmp_path / "bad.sas7bdat")))

        assert result["success"] is True, result
        assert mock_read.call_count == 2
        assert mock_read.call_args_list[1].kwargs.get("encoding") == "latin1"
        assert result.get("used_encoding") == "latin1"


class TestNonUnicodeErrorPassthrough:
    """Non-UnicodeDecodeError must NOT trigger retry — bubble up to the existing
    except block which converts it to the standard error response."""

    @patch("sas_schema_analyzer.core.schema_analyzer.pyreadstat.read_sas7bdat")
    @patch("sas_schema_analyzer.core.schema_analyzer.os.path.exists", return_value=True)
    def test_other_error_no_retry(self, _exists, mock_read, tmp_path):
        mock_read.side_effect = ValueError("corrupt header")

        analyzer = SasSchemaAnalyzer()
        result = _run(analyzer.analyze_file(str(tmp_path / "corrupt.sas7bdat")))

        assert result["success"] is False
        assert "corrupt header" in result["error"]
        assert mock_read.call_count == 1
