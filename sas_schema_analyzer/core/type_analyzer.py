"""
Data Type Analyzer for SAS Schema Extraction

This module provides intelligent SAS data type detection using multiple
evidence sources to determine if columns are character or numeric.
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from .date_analyzer import DateFormatAnalyzer


class DataTypeAnalyzer:
    """Enhanced SAS data type detection using multiple evidence sources"""
    
    def __init__(self, date_analyzer: Optional[DateFormatAnalyzer] = None):
        self.date_analyzer = date_analyzer or DateFormatAnalyzer()
    
    def get_sas_data_type(self, col_name: str, df: pd.DataFrame, meta: Any, debug: bool = False) -> str:
        """
        Enhanced SAS data type detection that combines multiple evidence sources
        to determine if a column is character or numeric.
        """
        type_evidence = {}
        
        # 1. Check column name endings for common date patterns - these are usually character
        if re.search(r'(DTC$|DATE$)', col_name, re.IGNORECASE):
            type_evidence['name_pattern'] = 'character'
        
        # 2. Direct SAS metadata checks
        # Check meta.column_types (most direct evidence)
        if hasattr(meta, 'column_types') and isinstance(meta.column_types, dict):
            col_type = meta.column_types.get(col_name)
            if col_type:
                type_evidence['column_types'] = "character" if col_type == "string" else "numeric"
        
        # Check readstat_variable_types
        if hasattr(meta, 'readstat_variable_types') and isinstance(meta.readstat_variable_types, dict):
            var_type = meta.readstat_variable_types.get(col_name)
            if var_type:
                type_evidence['readstat_variable_types'] = "character" if var_type == "string" else "numeric"
        
        # 3. Format-based checks
        col_format = getattr(meta, 'formats', {}).get(col_name, "")
        if col_format:
            # Character formats start with $
            if col_format.startswith('$'):
                type_evidence['format'] = 'character'
            # Numeric/date formats often contain DATE/DATETIME keywords
            elif any(pattern in col_format.upper() for pattern in ['DATE', 'DATETIME', 'TIME']):
                # DATE formats are typically applied to numeric columns in SAS
                type_evidence['format'] = 'numeric'
            # Other common SAS numeric formats
            elif any(pattern in col_format.upper() for pattern in ['F', 'E', 'COMMA', 'DOLLAR', 'PERCENT']):
                type_evidence['format'] = 'numeric'
        
        # 4. Check variable_value_labels (usually for numeric columns)
        if hasattr(meta, 'variable_value_labels') and isinstance(meta.variable_value_labels, dict):
            if col_name in meta.variable_value_labels:
                type_evidence['variable_value_labels'] = "numeric"
        
        # 5. Check column data itself
        # If all values are numeric-castable, it's likely numeric
        # If values match date patterns and column has DTC/DATE in name, likely character date
        sample = df[col_name].dropna().head(20)
        
        if len(sample) > 0:
            # Check if all values can be cast to numeric
            try:
                sample.astype(float)
                type_evidence['data_numeric_castable'] = 'numeric'
            except:
                type_evidence['data_numeric_castable'] = 'character'
            
            # Check for date patterns in character data
            if self.date_analyzer.has_date_pattern_evidence(col_name, df[col_name]):
                type_evidence['date_patterns'] = 'character'
        
        # 6. Pandas dtype as additional evidence
        type_evidence['pandas_dtype'] = "numeric" if pd.api.types.is_numeric_dtype(df[col_name]) else "character"
        
        # Log the evidence if in debug mode
        if debug:
            print(f"Type evidence for {col_name}: {type_evidence}")
        
        # Make final decision based on evidence
        # Priority: SAS metadata > format > name patterns > data evidence > pandas dtype
        
        # Explicit SAS metadata has highest priority
        if 'column_types' in type_evidence:
            return type_evidence['column_types']
        
        if 'readstat_variable_types' in type_evidence:
            return type_evidence['readstat_variable_types']
        
        # Format is next most reliable
        if 'format' in type_evidence:
            return type_evidence['format']
        
        # DTC and DATE name endings strongly suggest character dates
        if 'name_pattern' in type_evidence and type_evidence['name_pattern'] == 'character':
            # For DATE/DTC columns, check the data before deciding
            if 'date_patterns' in type_evidence:
                return type_evidence['date_patterns']
            return 'character'
            
        # Date pattern evidence is strong
        if 'date_patterns' in type_evidence:
            return type_evidence['date_patterns']
        
        # For other cases, use pandas dtype as fallback
        return type_evidence['pandas_dtype']
    
    def is_id_like_column(self, col_name: str, values: pd.Series) -> bool:
        """Check if a column appears to be an ID field (entity identifier)"""
        # First, check for flag variable patterns - these are NOT IDs
        flag_name_patterns = [
            r'FL$',                # Flag variables ending with FL
            r'YN\d*$',             # YN variables like AEYN1, AEYN2
            r'(Y|N)NUL+$',         # YNULL patterns
            r'EXIST$', r'OCCUR$',  # Existence/occurrence flags
            r'CONF$', r'DONE$',    # Confirmation flags
            r'EVNT$', r'EVENT$',   # Event flags
            r'DCSN$', r'DETH$',    # Decision/Death flags
            r'FLAG$',              # Explicit flag variables
            r'IND$',               # Indicator variables
        ]
        
        # If the column matches flag patterns, it's not an ID
        if any(re.search(pattern, col_name, re.IGNORECASE) for pattern in flag_name_patterns):
            return False
        
        # Check for values that strongly indicate a flag variable - not an ID
        # Sample up to 100 non-null values
        non_null = values.dropna()
        sample = non_null.astype(str).sample(min(100, len(non_null))).tolist() if len(non_null) > 0 else []
        
        # If column has very few unique values and they're typical flag values, it's not an ID
        if len(sample) > 0:
            unique_values = set(str(x).strip().upper() for x in sample)
            
            # Check for common flag value patterns
            flag_value_patterns = [
                {'Y', 'N'}, {'YES', 'NO'}, 
                {'TRUE', 'FALSE'}, {'T', 'F'},
                {'0', '1'}, {'Y', 'N', 'U'}, 
                {'Y', 'N', ''}, {'Y', 'N', 'NA'},
            ]
            
            # If values match common flag patterns and there are very few unique values, it's not an ID
            if len(unique_values) <= 5:  # Flag variables typically have few values
                # Check if our values match any of the common flag value sets
                if any(unique_values.issubset(pattern) for pattern in flag_value_patterns):
                    return False
        
        # Now check for true ID patterns - these ARE IDs
        # Check name patterns common for TRUE ID fields (more specific than before)
        id_name_patterns = [
            r'ID$', r'_ID$',           # Explicit ID suffix
            r'^ID', r'^ID_',           # Explicit ID prefix
            r'NUM$', r'NUMBER$',       # Numbering variables 
            r'^SUBJ', r'^SUBJID',      # Subject identifiers
            r'^SITE', r'^SITEID',      # Site identifiers
            r'^PATIENT', r'^PAT_ID',   # Patient identifiers
            r'^VISIT', r'^VIS_',       # Visit identifiers
            r'^USUBJID$', r'^STUDYID$' # Standard CDISC identifiers
        ]
        
        if any(re.search(pattern, col_name, re.IGNORECASE) for pattern in id_name_patterns):
            return True
            
        # Check for strong ID value patterns (more stringent than before)
        if len(sample) > 5:  # Only check if we have enough samples
            # Check for high cardinality - IDs tend to have many unique values
            unique_ratio = len(set(sample)) / len(sample)
            
            # For large datasets, IDs often have very high cardinality (e.g., > 90% unique values)
            if unique_ratio > 0.9 and len(sample) > 10:
                # Further validate with pattern checks
                lengths = [len(str(x)) for x in sample]
                consistent_length = len(set(lengths)) <= 3  # Allow small variations
                
                # Check for patterns that are strongly indicative of IDs
                prefixed_number_pattern = re.compile(r'^[A-Z]{1,5}\d{3,}$')  # Like S001, PT002 with at least 3 digits
                segmented_pattern = re.compile(r'^[A-Z0-9]+-[A-Z0-9]+-\d{2,}$')  # Like ABC-123-456 with segments
                subject_id_pattern = re.compile(r'^(\d{3,}-\d{3,}|\d{3,})$')  # Common subject ID formats
                
                # Count matches for each pattern
                prefixed_number_ratio = sum(1 for x in sample if prefixed_number_pattern.search(str(x).upper())) / len(sample)
                segmented_ratio = sum(1 for x in sample if segmented_pattern.search(str(x).upper())) / len(sample)
                subject_id_ratio = sum(1 for x in sample if subject_id_pattern.search(str(x))) / len(sample)
                
                # If consistent length AND matches ID patterns, classify as ID
                if consistent_length and (prefixed_number_ratio > 0.5 or segmented_ratio > 0.5 or subject_id_ratio > 0.5):
                    return True
        
        return False
        
    def is_result_column(self, col_name: str, values: pd.Series) -> bool:
        """Check if a column appears to be a result or measurement value"""
        # Check name patterns common for result fields
        result_name_patterns = [
            r'RESULT$', r'VALUE$', r'MEASURE$', r'READING$', r'FINDING$',
            r'LBORRES', r'VSORRES', r'QSORRES', r'ECGORRES'  # Common in CDISC
        ]
        
        if any(re.search(pattern, col_name, re.IGNORECASE) for pattern in result_name_patterns):
            return True
            
        # Sample up to 100 non-null values
        non_null = values.dropna()
        sample = non_null.astype(str).sample(min(100, len(non_null))).tolist() if len(non_null) > 0 else []

        if len(sample) >= 5:
            # If it's a numeric column, check for very high cardinality (strongly indicates continuous data)
            if pd.api.types.is_numeric_dtype(values):
                unique_ratio = values.nunique() / len(non_null)
                # For numeric columns, a very high unique ratio (> 95%) strongly suggests continuous data
                # This is more stringent than before to avoid false positives with small datasets
                if unique_ratio > 0.95 and len(non_null) > 5:
                    return True

            # Check for measurement patterns requiring actual decimal points and/or units
            # e.g., "120.5", "15.3 kg", "98.6 F" - must have decimal points for measurements
            measurement_pattern = re.compile(r'^\s*\d+\.\d+\s*([a-zA-Z%/]+)?\s*$')  # Requires decimal point
            measurement_ratio = sum(1 for x in sample if measurement_pattern.match(str(x))) / len(sample)
            
            # Also check for numeric strings that could be converted to decimals
            numeric_decimal_pattern = re.compile(r'^\s*\d+\.\d+\s*$')  # Pure decimal numbers as strings
            numeric_decimal_ratio = sum(1 for x in sample if numeric_decimal_pattern.match(str(x))) / len(sample)
            
            # Check for common result text patterns
            result_text_pattern = re.compile(r'^(normal|abnormal|positive|negative|present|absent|detected|not detected|elevated|low|high|within normal limits)$', re.IGNORECASE)
            result_text_ratio = sum(1 for x in sample if result_text_pattern.match(str(x).strip())) / len(sample)
            
            # Check for distribution patterns that suggest continuous data
            if pd.api.types.is_numeric_dtype(values) and len(values.dropna()) > 10:
                # For numeric data, check if values are distributed across a range (not clustered in a few discrete values)
                numeric_values = pd.to_numeric(values.dropna(), errors='coerce').dropna()
                if len(numeric_values) > 10:
                    # Check if values span a reasonable range with decimals
                    has_decimals = any(float(x) != int(float(x)) for x in numeric_values.sample(min(20, len(numeric_values))))
                    value_range = numeric_values.max() - numeric_values.min()
                    # If we have decimal values and a reasonable range, likely continuous
                    if has_decimals and value_range > 10:
                        return True
            
            if measurement_ratio > 0.7 or numeric_decimal_ratio > 0.7 or result_text_ratio > 0.7:
                return True
        
        return False
