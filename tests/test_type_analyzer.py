"""
TDD tests for DataTypeAnalyzer — pandas 3.x StringDtype compatibility.

Bug: np.issubdtype(df[col].dtype, np.number) raises TypeError when the column
has pandas StringDtype (the new default in pandas 3.x for string columns).

Fix: Replace with pd.api.types.is_numeric_dtype(df[col]) which handles all
pandas ExtensionDtypes including StringDtype, Float64Dtype, Int64Dtype, etc.

RED phase: tests fail before the fix.
GREEN phase: tests pass after replacing np.issubdtype on type_analyzer.py:82.
"""

import pandas as pd
import numpy as np
import pytest

from sas_schema_analyzer.core.type_analyzer import DataTypeAnalyzer


class FakeMeta:
    """Minimal metadata stub that satisfies DataTypeAnalyzer.get_sas_data_type."""
    column_names_to_labels = {}
    column_names_to_types = {}
    readstat_variable_types = {}
    original_variable_types = {}
    variable_value_labels = {}
    column_formats = {}


class TestStringDtypeCompatibility:
    """Verify get_sas_data_type handles pandas 3.x StringDtype columns."""

    def setup_method(self):
        self.analyzer = DataTypeAnalyzer()
        self.meta = FakeMeta()

    def _df_with_string_dtype(self, col_name: str, values: list) -> pd.DataFrame:
        """Build a DataFrame whose column has pandas StringDtype (not object)."""
        series = pd.array(values, dtype="string")
        return pd.DataFrame({col_name: series})

    def test_string_dtype_column_returns_character(self):
        """StringDtype column must be classified as 'character', not raise TypeError."""
        df = self._df_with_string_dtype("SUBJID", ["001", "002", "003"])
        result = self.analyzer.get_sas_data_type("SUBJID", df, self.meta)
        assert result == "character", f"Expected 'character', got {result!r}"

    def test_string_dtype_does_not_raise(self):
        """Calling get_sas_data_type on a StringDtype column must not raise any exception."""
        df = self._df_with_string_dtype("VISIT", ["V1", "V2", "V3"])
        try:
            self.analyzer.get_sas_data_type("VISIT", df, self.meta)
        except TypeError as exc:
            pytest.fail(
                f"get_sas_data_type raised TypeError for StringDtype column: {exc}\n"
                "Fix: replace np.issubdtype with pd.api.types.is_numeric_dtype in type_analyzer.py:82"
            )

    def test_numpy_float_dtype_still_numeric(self):
        """Classic numpy float64 columns must still be classified as 'numeric'."""
        df = pd.DataFrame({"AGE": pd.array([25.0, 30.0, 45.0], dtype="float64")})
        result = self.analyzer.get_sas_data_type("AGE", df, self.meta)
        assert result == "numeric", f"Expected 'numeric', got {result!r}"

    def test_nullable_int_dtype_numeric(self):
        """Pandas nullable Int64 columns must be classified as 'numeric'."""
        df = pd.DataFrame({"COUNT": pd.array([1, 2, 3], dtype="Int64")})
        result = self.analyzer.get_sas_data_type("COUNT", df, self.meta)
        assert result == "numeric", f"Expected 'numeric', got {result!r}"
