"""
SAS Schema Analyzer - FastMCP Server Package

A production-ready FastMCP server for analyzing SAS7BDAT files and extracting 
comprehensive metadata. Perfect for clinical data analysis, CDISC datasets, 
and general SAS file exploration.

Features:
- Intelligent data type detection (character vs numeric)
- Advanced date format analysis with partial date support  
- Smart code list detection for categorical variables
- Memory-aware processing for large files (1GB+ fallback)
- Windows path handling and long path support
- Comprehensive error handling and troubleshooting guidance

Usage:
    # Run as MCP server
    uvx sas-schema-analyzer
    
    # Or import in Python
    from sas_schema_analyzer.core import SasSchemaAnalyzer
"""

__version__ = "1.1.0"
__author__ = "SAS Schema Analyzer Team"

# Import main function for console script entry point
from .server import main

__all__ = ["main"]
