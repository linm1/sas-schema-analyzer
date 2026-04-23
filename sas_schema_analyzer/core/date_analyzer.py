"""
Date Format Analyzer for SAS Schema Extraction

This module provides robust date format detection and partial date analysis
for SAS7BDAT files, handling various date patterns and placeholder values.
"""

import re
import pandas as pd
from collections import Counter
from typing import Dict, List, Any, Optional


class DateFormatAnalyzer:
    """Class to handle robust date format detection and partial date analysis"""
    
    def __init__(self):
        self._date_label_pattern = re.compile(
            r'(?<!\w)(date|datetime|time|timestamp|dob|birth|dt|d/t)(?!\w)',
            re.IGNORECASE,
        )
        self._date_name_pattern = re.compile(
            r'(DTC$|DT$|DATE$|DATETIME$|TIME$|TM$|_DTC$|_DT$|_DATE$|_DATETIME$|_TIME$)',
            re.IGNORECASE,
        )

        # Define placeholder patterns
        self.year_placeholder_patterns = ['0000', 'YYYY', 'UNKNOWN', 'UNK', 'UK', '----', 'XXXX']
        self.month_placeholder_patterns = ['00', 'MM', 'UNKNOWN', 'UNK', 'UK', '--', 'XX', 'XXX']
        self.day_placeholder_patterns = ['00', 'DD', 'UNKNOWN', 'UNK', 'UK', 'UN', '--', 'XX']
        # Basic date components patterns
        self.year_pattern = r'(?P<year>\d{4}|YYYY|UNK|UK|UNKNOWN|XXXX)'
        self.month_numeric_pattern = r'(?P<month>\d{2}|MM|UNK|UK|UNKNOWN|XX)'
        self.month_text_pattern = r'(?P<month>[A-Za-z]{3}|MMM|UNK|UK|UNKNOWN|XXX)'
        self.day_pattern = r'(?P<day>\d{2}|DD|UNK|UK|UN|UNKNOWN|XX)'
        self.hour_pattern = r'(?P<hour>\d{2}|HH|UNK|XX)'
        self.minute_pattern = r'(?P<minute>\d{2}|MM|UNK|XX)'
        self.second_pattern = r'(?P<second>\d{2}|SS|UNK|XX)'
        
        # Pre-compiled patterns for has_date_pattern_evidence (avoids recompile per call)
        self._quick_date_patterns = [
            re.compile(r'\d{4}-\d{2}-\d{2}'),
            re.compile(r'\d{2}/\d{2}/\d{4}'),
            re.compile(r'\d{2}[A-Za-z]{3}\d{4}'),
            re.compile(r'\d{4}[A-Za-z]{3}\d{2}'),
            re.compile(r'\d{4}-[A-Za-z]{2,3}-\d{2}'),
            re.compile(r'\d{4}-\d{2}-[A-Za-z]{2}'),
            re.compile(r'\d{4}-[A-Za-z]{2,3}-[A-Za-z]{2}'),
        ]

        # Define base date format patterns with named capture groups
        self.base_patterns = [
            # ISO format with time: YYYY-MM-DDTHH:MM[:SS] (common in XML and ISO 8601)
            {
                'regex': re.compile(fr'^{self.year_pattern}-{self.month_numeric_pattern}-{self.day_pattern}T{self.hour_pattern}:{self.minute_pattern}(:{self.second_pattern})?$'),
                'format': 'YYYY-MM-DDTHH:MM[:SS]',
                'separator': '-',
                'has_time': True
            },
            # ISO format: YYYY-MM-DD and variations
            {
                'regex': re.compile(fr'^{self.year_pattern}-{self.month_numeric_pattern}-{self.day_pattern}$'),
                'format': 'YYYY-MM-DD',
                'separator': '-'
            },
            # Slash format: YYYY/MM/DD and variations
            {
                'regex': re.compile(fr'^{self.year_pattern}/{self.month_numeric_pattern}/{self.day_pattern}$'),
                'format': 'YYYY/MM/DD',
                'separator': '/'
            },
            # US format: MM/DD/YYYY and variations
            {
                'regex': re.compile(fr'^{self.month_numeric_pattern}/{self.day_pattern}/{self.year_pattern}$'),
                'format': 'MM/DD/YYYY',
                'separator': '/'
            },
            # European format: DD-MM-YYYY and variations
            {
                'regex': re.compile(fr'^{self.day_pattern}-{self.month_numeric_pattern}-{self.year_pattern}$'),
                'format': 'DD-MM-YYYY',
                'separator': '-'
            },
            # Compact format: YYYYMMDD and variations
            {
                'regex': re.compile(fr'^{self.year_pattern}{self.month_numeric_pattern}{self.day_pattern}$'),
                'format': 'YYYYMMDD',
                'separator': ''
            },
            # Compact European format: DDMMYYYY and variations
            {
                'regex': re.compile(fr'^{self.day_pattern}{self.month_numeric_pattern}{self.year_pattern}$'),
                'format': 'DDMMYYYY',
                'separator': ''
            },
            # Text month format: DDMMMYYYY and variations
            {
                'regex': re.compile(fr'^{self.day_pattern}{self.month_text_pattern}{self.year_pattern}$'),
                'format': 'DDMMMYYYY',
                'separator': ''
            },
            # Text month format: YYYYMMMDD and variations
            {
                'regex': re.compile(fr'^{self.year_pattern}{self.month_text_pattern}{self.day_pattern}$'),
                'format': 'YYYYMMMDD',
                'separator': ''
            },
            # Year-Month only: YYYY-MM and variations
            {
                'regex': re.compile(fr'^{self.year_pattern}-{self.month_numeric_pattern}$'),
                'format': 'YYYY-MM',
                'separator': '-',
                'partial': {'day': True}
            },
            # Year-Month only with slash: YYYY/MM and variations
            {
                'regex': re.compile(fr'^{self.year_pattern}/{self.month_numeric_pattern}$'),
                'format': 'YYYY/MM',
                'separator': '/',
                'partial': {'day': True}
            },
            # Year-Month text only: YYYYMMM and variations
            {
                'regex': re.compile(fr'^{self.year_pattern}{self.month_text_pattern}$'),
                'format': 'YYYYMMM',
                'separator': '',
                'partial': {'day': True}
            },
            # Month text-Year only: MMMYYYY and variations
            {
                'regex': re.compile(fr'^{self.month_text_pattern}{self.year_pattern}$'),
                'format': 'MMMYYYY',
                'separator': '',
                'partial': {'day': True}
            },
            # Year only: YYYY and variations
            {
                'regex': re.compile(fr'^{self.year_pattern}$'),
                'format': 'YYYY',
                'separator': '',
                'partial': {'month': True, 'day': True}
            }
        ]
        
    def is_placeholder(self, value: str, component_type: str) -> bool:
        """Check if a value is a placeholder for a given component type"""
        if value is None or value.strip() == '':
            return True
            
        value = value.upper()
        
        if component_type == 'year':
            return (value in self.year_placeholder_patterns or 
                    value == '0' * len(value) or 
                    value == '-' * len(value) or
                    value == 'X' * len(value))
        elif component_type == 'month':
            return (value in self.month_placeholder_patterns or 
                    value == '0' * len(value) or 
                    value == '-' * len(value) or
                    value == 'X' * len(value))
        elif component_type == 'day':
            return (value in self.day_placeholder_patterns or 
                    value == '0' * len(value) or 
                    value == '-' * len(value) or
                    value == 'X' * len(value))
        
        return False
    
    def analyze_date_string(self, date_str: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a date string to determine format and partial components.
        Returns a dict with format, components, and partial info.
        """
        if pd.isna(date_str) or date_str == '':
            return None
            
        date_str = str(date_str).strip()
        
        for pattern in self.base_patterns:
            match = pattern['regex'].match(date_str)
            if match:
                format_name = pattern['format']
                components = match.groupdict()
                
                # Check for partial date
                partial_components = {}
                
                # First, check if the format is inherently partial
                if 'partial' in pattern:
                    partial_components = pattern['partial'].copy()
                
                # Then check individual components for placeholders
                if 'year' in components and self.is_placeholder(components['year'], 'year'):
                    partial_components['year'] = True
                if 'month' in components and self.is_placeholder(components['month'], 'month'):
                    partial_components['month'] = True
                if 'day' in components and self.is_placeholder(components['day'], 'day'):
                    partial_components['day'] = True
                
                return {
                    'format': format_name,
                    'components': components,
                    'is_partial': bool(partial_components),
                    'partial_components': partial_components,
                    'separator': pattern['separator']
                }
        
        return None
    
    def analyze_date_series(self, values: pd.Series) -> Dict[str, Any]:
        """
        Analyze a series of date values to detect formats and partial dates.
        Samples up to 2000 unique non-null values for efficiency on large columns.
        """
        format_counter = Counter()
        formats_data = {}
        total_non_empty = 0

        non_null = values.dropna()
        unique_vals = non_null.unique()
        if len(unique_vals) > 2000:
            import numpy as np
            unique_vals = np.random.choice(unique_vals, 2000, replace=False)

        for val in unique_vals:
            if val == '':
                continue
                
            total_non_empty += 1
            val_str = str(val).strip()
            
            # Analyze this date string
            analysis = self.analyze_date_string(val_str)
            if analysis:
                format_name = analysis['format']
                format_counter[format_name] += 1
                
                # Initialize format data if not exists
                if format_name not in formats_data:
                    formats_data[format_name] = {
                        'partial_counts': {'year': 0, 'month': 0, 'day': 0},
                        'values_count': 0,
                        'separator': analysis['separator']
                    }
                
                # Update counts
                formats_data[format_name]['values_count'] += 1
                
                # Count partial components
                for component, is_partial in analysis.get('partial_components', {}).items():
                    if is_partial:
                        formats_data[format_name]['partial_counts'][component] += 1
        
        # O(1) lookup for pattern metadata (avoids linear scan per format)
        pattern_by_format = {p['format']: p for p in self.base_patterns}

        # Prepare final format information
        formats_info = []
        for format_name, count in format_counter.most_common():
            format_data = formats_data[format_name]
            
            # Calculate percentages for partial components
            partial_analysis = {}
            if format_data['values_count'] > 0:
                for component, partial_count in format_data['partial_counts'].items():
                    if partial_count > 0:
                        partial_analysis[f'missing_{component}_pct'] = round(
                            partial_count / format_data['values_count'] * 100, 2
                        )
            
            # Create format info object
            format_info = {
                'format': format_name,
                'match_count': count,
                'match_percentage': round(count / total_non_empty * 100, 2) if total_non_empty > 0 else 0,
                'separator': format_data['separator']
            }
            
            # Add time component info if present
            pattern = pattern_by_format.get(format_name)
            if pattern and pattern.get('has_time', False):
                format_info['has_time'] = True
            
            # Add partial date analysis if relevant
            if partial_analysis:
                format_info['partial_date_analysis'] = partial_analysis
                format_info['has_partial_dates'] = True
            
            formats_info.append(format_info)
        
        return {
            'formats': formats_info,
            'total_non_empty': total_non_empty,
            'is_date': len(formats_info) > 0 and formats_info[0]['match_percentage'] > 50
        }

    def has_date_pattern_evidence(self, col_name: str, values: pd.Series) -> bool:
        """Check if a column's values provide evidence it's a date field"""
        # Check name patterns
        date_name_evidence = bool(re.search(r'(DT$|DTC$|DATE$|_DT$|_DATE$)', col_name, re.IGNORECASE))
        
        # Check common date patterns in values (only examine a sample for efficiency)
        sample_values = values.dropna().astype(str).head(100)
        date_pattern_count = 0

        for val in sample_values:
            for pattern in self._quick_date_patterns:
                if pattern.match(val):
                    date_pattern_count += 1
                    break
        
        date_value_evidence = date_pattern_count / len(sample_values) > 0.5 if len(sample_values) > 0 else False
        
        return date_name_evidence or date_value_evidence

    def has_date_metadata_evidence(self, col_name: Optional[str], col_label: Optional[str]) -> bool:
        """Return True when column metadata indicates the field is date-related.

        Labels take precedence over names so a non-date label suppresses false
        positives from date-like numeric values such as year-style identifiers.
        """
        label_text = str(col_label).strip() if col_label is not None else ''
        if label_text:
            return bool(self._date_label_pattern.search(label_text))

        name_text = str(col_name).strip() if col_name is not None else ''
        return bool(self._date_name_pattern.search(name_text))
