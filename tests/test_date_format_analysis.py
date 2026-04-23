"""Regression tests for date_format_analysis gating.

All pyreadstat calls are mocked. These tests verify that date format analysis
is only emitted for columns whose metadata indicates they are date-related.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd

from sas_schema_analyzer.core.schema_analyzer import SasSchemaAnalyzer


def _run(coro):
    return asyncio.run(coro)


def _fake_meta(labels):
    meta = MagicMock()
    meta.file_label = "TEST"
    meta.column_names_to_labels = labels
    return meta


def _column_by_name(result, name):
    return next(column for column in result["columns"] if column["name"] == name)


class TestDateFormatAnalysisGating:
    """Verify date analysis only appears for date-related columns."""

    @patch("sas_schema_analyzer.core.schema_analyzer.pyreadstat.read_sas7bdat")
    @patch("sas_schema_analyzer.core.schema_analyzer.os.path.exists", return_value=True)
    def test_non_date_label_suppresses_year_only_date_analysis(self, _exists, mock_read, tmp_path):
        df = pd.DataFrame({"SITEID": ["2022", "2023", "2024"]})
        mock_read.return_value = (df, _fake_meta({"SITEID": "Site Number"}))

        analyzer = SasSchemaAnalyzer()
        result = _run(analyzer.analyze_file(str(tmp_path / "siteid.sas7bdat")))

        assert result["success"] is True
        column = _column_by_name(result, "SITEID")
        assert "date_format_analysis" not in column

    @patch("sas_schema_analyzer.core.schema_analyzer.pyreadstat.read_sas7bdat")
    @patch("sas_schema_analyzer.core.schema_analyzer.os.path.exists", return_value=True)
    def test_date_label_allows_year_only_date_analysis(self, _exists, mock_read, tmp_path):
        df = pd.DataFrame({"CMSTDTY": ["2022", "2023", "2024"]})
        mock_read.return_value = (
            df,
            _fake_meta({"CMSTDTY": "Start Date of Medication-Year"}),
        )

        analyzer = SasSchemaAnalyzer()
        result = _run(analyzer.analyze_file(str(tmp_path / "cmstdty.sas7bdat")))

        assert result["success"] is True
        column = _column_by_name(result, "CMSTDTY")
        assert column["date_format_analysis"]["formats"][0]["format"] == "YYYY"

    @patch("sas_schema_analyzer.core.schema_analyzer.pyreadstat.read_sas7bdat")
    @patch("sas_schema_analyzer.core.schema_analyzer.os.path.exists", return_value=True)
    def test_non_date_label_overrides_date_like_name(self, _exists, mock_read, tmp_path):
        df = pd.DataFrame({"AESTDTC": ["2024-01-02", "2024-02-03", "2024-03-04"]})
        mock_read.return_value = (df, _fake_meta({"AESTDTC": "Visit Day"}))

        analyzer = SasSchemaAnalyzer()
        result = _run(analyzer.analyze_file(str(tmp_path / "aestdtc_non_date_label.sas7bdat")))

        assert result["success"] is True
        column = _column_by_name(result, "AESTDTC")
        assert "date_format_analysis" not in column

    @patch("sas_schema_analyzer.core.schema_analyzer.pyreadstat.read_sas7bdat")
    @patch("sas_schema_analyzer.core.schema_analyzer.os.path.exists", return_value=True)
    def test_abbreviated_date_label_allows_date_analysis(self, _exists, mock_read, tmp_path):
        df = pd.DataFrame({"AESTDTC": ["2024-01-02", "2024-02-03", "2024-03-04"]})
        mock_read.return_value = (df, _fake_meta({"AESTDTC": "Start Dt"}))

        analyzer = SasSchemaAnalyzer()
        result = _run(analyzer.analyze_file(str(tmp_path / "aestdtc_abbrev_label.sas7bdat")))

        assert result["success"] is True
        column = _column_by_name(result, "AESTDTC")
        assert column["date_format_analysis"]["formats"][0]["format"] == "YYYY-MM-DD"

    @patch("sas_schema_analyzer.core.schema_analyzer.pyreadstat.read_sas7bdat")
    @patch("sas_schema_analyzer.core.schema_analyzer.os.path.exists", return_value=True)
    def test_date_name_without_label_still_allows_date_analysis(self, _exists, mock_read, tmp_path):
        df = pd.DataFrame({"AESTDTC": ["2024-01-02", "2024-02-03", "2024-03-04"]})
        mock_read.return_value = (df, _fake_meta({"AESTDTC": None}))

        analyzer = SasSchemaAnalyzer()
        result = _run(analyzer.analyze_file(str(tmp_path / "aestdtc.sas7bdat")))

        assert result["success"] is True
        column = _column_by_name(result, "AESTDTC")
        assert column["date_format_analysis"]["formats"][0]["format"] == "YYYY-MM-DD"