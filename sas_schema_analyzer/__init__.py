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

from importlib import import_module

__version__ = "1.1.0"
__author__ = "SAS Schema Analyzer Team"

def main() -> None:
    try:
        server_module = import_module(".server", __name__)
    except ModuleNotFoundError as exc:
        if exc.name == "fastmcp":
            raise SystemExit(
                "sas-schema-analyzer requires fastmcp and Python 3.10+. "
                "Use sas-schema on Python 3.8/3.9, or install the server on Python 3.10+."
            ) from exc
        raise

    server_module.main()

__all__ = ["main"]
