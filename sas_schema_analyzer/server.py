"""
SAS Schema MCP Server

A FastMCP server for analyzing SAS7BDAT files and extracting comprehensive metadata.
Provides tools for single file analysis, batch folder processing, and file discovery.

Author: Claude Sonnet 4 + User Collaboration
Framework: FastMCP 2.0+
Dependencies: pyreadstat, pandas, numpy, psutil
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastmcp import FastMCP, Context
from .core import SasSchemaAnalyzer, MemoryManager, SDTMSpecAnalyzer


# Initialize the FastMCP server
mcp = FastMCP(
    name="SAS Schema Analyzer",
    instructions="""
    This server analyzes SAS7BDAT files and SDTM specification Excel files to extract comprehensive metadata and schema information.

    Available tools:
    - analyze_sas_file: Extract complete schema from a single SAS file
    - analyze_sas_folder: Batch process all SAS files in a directory
    - list_sas_files: Discover SAS files with basic information
    - get_memory_recommendations: Memory analysis for large files
    - analyze_sdtm_spec: Extract SDTM domain specification from Excel file
    - list_sdtm_domains: List all domains available in SDTM specification file

    Features:
    - Intelligent data type detection (character vs numeric)
    - Advanced date format analysis with partial date support
    - Smart code list detection for categorical variables
    - Memory-aware processing for large files (1GB+ fallback)
    - SDTM specification reader for clinical data mapping
    - Windows path handling and long path support
    - Comprehensive error handling and troubleshooting guidance

    Perfect for clinical data analysis, CDISC datasets, SAS file exploration, and SDTM mapping specifications.
    The SDTM tools enable LLM-friendly reading of clinical trial data specifications.
    """,
)

# Initialize the schema analyzers
analyzer = SasSchemaAnalyzer()
sdtm_analyzer = SDTMSpecAnalyzer()
memory_mgr = MemoryManager()


def _tool_error(e: Exception, suggestion: str, **context_keys) -> dict:
    """Build a standardized MCP tool error response."""
    return {
        "success": False,
        "error": str(e),
        "error_type": type(e).__name__,
        **context_keys,
        "troubleshooting": {"suggestion": suggestion},
    }


@mcp.tool
async def analyze_sas_file(
    ctx: Context,
    file_path: str,
    code_list_threshold: float = 0.15,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Extract comprehensive schema and metadata from a SAS7BDAT file.
    
    This tool analyzes a single SAS file and returns detailed information about:
    - File metadata (creation date, SAS version, encoding, etc.)
    - Column schemas with data types, formats, and lengths
    - Date format detection with partial date support
    - Code lists for categorical variables
    - Data quality metrics (unique values)
    - Memory usage and processing recommendations
    
    Args:
        file_path: Full path to the SAS7BDAT file to analyze
        code_list_threshold: Threshold for detecting categorical variables (0.0-1.0, default 0.15)
        debug: Enable detailed logging for troubleshooting (default False)
        
    Returns:
        Complete schema analysis with success status, file metadata, and column details
        
    Example:
        analyze_sas_file("C:/data/demographics.sas7bdat", code_list_threshold=0.1)
    """
    try:
        await ctx.info(f"Starting analysis of: {os.path.basename(file_path)}")
        
        # Update analyzer settings
        analyzer.code_list_threshold = code_list_threshold
        analyzer.debug = debug
        
        # Perform the analysis
        result = await analyzer.analyze_file(file_path, ctx)
        
        if result.get("success", False):
            await ctx.info(f"Successfully analyzed {result.get('column_count', 0)} columns")
        else:
            await ctx.error(f"Analysis failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Unexpected error during analysis: {str(e)}")
        return _tool_error(e, "Check file path and permissions, ensure file is not corrupted", file_path=file_path)


@mcp.tool
async def analyze_sas_folder(
    ctx: Context,
    folder_path: str,
    code_list_threshold: float = 0.15,
    recursive: bool = False,
    max_files: int = 50,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Analyze all SAS7BDAT files in a directory with batch processing and progress reporting.
    
    This tool processes multiple SAS files in a folder and provides:
    - Individual analysis results for each file
    - Aggregate statistics across all files
    - Success/failure rates and error summaries
    - Memory usage patterns and processing modes
    - Comprehensive folder-level insights
    
    Args:
        folder_path: Directory containing SAS7BDAT files
        code_list_threshold: Threshold for categorical variable detection (0.0-1.0, default 0.15)
        recursive: Include subdirectories in search (default False)
        max_files: Maximum number of files to process (safety limit, default 50)
        debug: Enable detailed logging for troubleshooting (default False)
        
    Returns:
        Batch analysis results with folder summary and individual file details
        
    Example:
        analyze_sas_folder("C:/clinical_data/", recursive=True, max_files=25)
    """
    try:
        await ctx.info(f"Starting folder analysis: {folder_path}")
        
        # Update analyzer settings
        analyzer.code_list_threshold = code_list_threshold
        analyzer.debug = debug
        
        # Perform folder analysis
        result = await analyzer.analyze_folder(
            folder_path=folder_path,
            recursive=recursive,
            max_files=max_files,
            ctx=ctx
        )
        
        if result.get("success", False):
            successful = result.get("successful_analyses", 0)
            failed = result.get("failed_analyses", 0)
            total_files = successful + failed
            await ctx.info(f"Folder analysis complete: {successful}/{total_files} files processed successfully")
        else:
            await ctx.error(f"Folder analysis failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Unexpected error during folder analysis: {str(e)}")
        return _tool_error(e, "Check folder path and permissions, ensure directory exists and is readable", folder_path=folder_path)


@mcp.tool
async def list_sas_files(
    ctx: Context,
    directory: str,
    recursive: bool = False
) -> Dict[str, Any]:
    """
    Discover SAS7BDAT files in a directory with basic file information.
    
    This tool scans a directory and provides:
    - List of all SAS7BDAT files found
    - File paths and names
    - Total directory file count statistics
    - File accessibility status
    
    Perfect for exploring data directories before running analysis.
    
    Args:
        directory: Directory to search for SAS files
        recursive: Include subdirectories in search (default False)
        
    Returns:
        File listing with basic metadata
        
    Example:
        list_sas_files("C:/data/", recursive=True)
    """
    try:
        await ctx.info(f"Discovering SAS files in: {directory}")
        
        # Perform file discovery
        result = await analyzer.list_sas_files(
            directory=directory,
            recursive=recursive,
            ctx=ctx
        )
        
        if result.get("success", False):
            files_found = result.get("files_found", 0)
            await ctx.info(f"Discovery complete: {files_found} SAS files found")
        else:
            await ctx.error(f"File discovery failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Unexpected error during file discovery: {str(e)}")
        return _tool_error(e, "Check directory path and permissions, ensure directory exists", directory=directory)


@mcp.tool
async def get_memory_recommendations(
    ctx: Context,
    file_path: str
) -> Dict[str, Any]:
    """
    Get memory usage recommendations for processing a specific SAS file.
    
    This tool analyzes a file without opening it and provides:
    - File size analysis and memory estimates
    - Processing mode recommendations (normal vs chunked)
    - System memory availability assessment
    - Performance optimization suggestions
    
    Useful for planning analysis of large datasets before processing.
    
    Args:
        file_path: Path to SAS7BDAT file to analyze
        
    Returns:
        Memory analysis and processing recommendations
        
    Example:
        get_memory_recommendations("C:/large_dataset.sas7bdat")
    """
    try:
        await ctx.info(f"Analyzing memory requirements for: {os.path.basename(file_path)}")
        
        # Get memory recommendations
        recommendations = memory_mgr.get_processing_recommendations(file_path)
        
        await ctx.info(f"Analysis complete - recommended mode: {recommendations['processing_mode']}")
        
        return {
            "success": True,
            "file_path": file_path,
            "recommendations": recommendations
        }
        
    except Exception as e:
        await ctx.error(f"Memory analysis failed: {str(e)}")
        return _tool_error(e, "Check file path exists and is accessible", file_path=file_path)


@mcp.tool
async def analyze_sdtm_spec(
    ctx: Context,
    file_path: str,
    domain: str,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Extract SDTM domain specification from Excel file in LLM-friendly JSON format.
    
    This tool reads SDTM specification Excel files and converts domain-specific information
    into a simplified JSON structure optimized for LLM consumption and SAS code generation.
    
    Key features:
    - Single domain focus for clarity
    - Consolidated mapping instructions (method + comment + value/note)
    - Simplified codelist terms (just the possible values)
    - Clean variable metadata (variable, label, data_type)
    - Source dataset traceability
    
    Args:
        file_path: Path to SDTM specification Excel file (.xlsx, .xlsm, .xls)
        domain: SDTM domain code (e.g., 'EX', 'DM', 'LB', 'AE')
        debug: Enable detailed logging for troubleshooting (default False)
        
    Returns:
        Domain specification with variables, codelists, and mapping instructions
        
    Example:
        analyze_sdtm_spec("C:/specs/SDTM_Spec_V0.6.xlsx", "EX")
    """
    try:
        await ctx.info(f"Analyzing SDTM spec for domain '{domain}': {os.path.basename(file_path)}")
        
        # Update analyzer settings
        sdtm_analyzer.debug = debug
        
        # Perform the analysis
        result = await sdtm_analyzer.analyze_sdtm_spec(file_path, domain, ctx)
        
        if result.get("success", False):
            var_count = result.get("variable_count", 0)
            await ctx.info(f"Successfully processed domain '{domain}' with {var_count} variables")
            
            # DEBUG: Log codelist counts right before return
            if debug:
                codelists = result.get("specification", {}).get("codelists", {})
                await ctx.info(f"DEBUG - About to return {len(codelists)} codelists")
                for cl_id, cl_terms in codelists.items():
                    await ctx.info(f"DEBUG - {cl_id}: {len(cl_terms)} terms")
        else:
            await ctx.error(f"SDTM analysis failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Unexpected error during SDTM analysis: {str(e)}")
        return _tool_error(e, "Check file path and domain name, ensure Excel file contains required SDTM sheets", file_path=file_path, domain=domain)


@mcp.tool
async def list_sdtm_domains(
    ctx: Context,
    file_path: str
) -> Dict[str, Any]:
    """
    List all available domains in an SDTM specification Excel file.
    
    This tool scans the Datasets sheet of an SDTM specification file and returns
    information about all available domains including their names, classes, and descriptions.
    
    Perfect for discovering what domains are available before running domain-specific analysis.
    
    Args:
        file_path: Path to SDTM specification Excel file (.xlsx, .xlsm, .xls)
        
    Returns:
        List of domains with metadata (domain code, name, class, description)
        
    Example:
        list_sdtm_domains("C:/specs/SDTM_Spec_V0.6.xlsx")
    """
    try:
        await ctx.info(f"Listing domains in SDTM spec: {os.path.basename(file_path)}")
        
        # Get domain list
        result = await sdtm_analyzer.list_domains(file_path, ctx)
        
        if result.get("success", False):
            domain_count = result.get("domain_count", 0)
            await ctx.info(f"Found {domain_count} domains in specification file")
        else:
            await ctx.error(f"Domain listing failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Unexpected error listing domains: {str(e)}")
        return _tool_error(e, "Check file path and ensure Excel file contains valid Datasets sheet", file_path=file_path)


# Add a resource for quick help
@mcp.resource("sas-analyzer://help/usage")
def get_usage_guide() -> str:
    """Provides usage guide and examples for the SAS Schema Analyzer."""
    return """
# SAS Schema Analyzer - Usage Guide

## Quick Start

1. **Analyze a single file:**
   ```
   analyze_sas_file("C:/data/demographics.sas7bdat")
   ```

2. **Batch process a folder:**
   ```
   analyze_sas_folder("C:/clinical_data/", recursive=True)
   ```

3. **Discover files first:**
   ```
   list_sas_files("C:/data/", recursive=True)
   ```

4. **Analyze SDTM specification:**
   ```
   list_sdtm_domains("C:/specs/SDTM_Spec_V0.6.xlsx")
   analyze_sdtm_spec("C:/specs/SDTM_Spec_V0.6.xlsx", "EX")
   ```

## Key Features

- **Smart Data Type Detection**: Distinguishes character vs numeric using multiple evidence sources
- **Date Format Analysis**: Detects 15+ date patterns including partial dates and ISO 8601
- **Code List Generation**: Automatically identifies categorical variables
- **Memory Management**: Handles large files (1GB+) with sampling fallback
- **SDTM Specification Reader**: Converts Excel specs to LLM-friendly JSON (NEW!)
- **Windows Support**: Full Windows path handling including long paths

## Tips for Best Results

- Use `debug=True` for troubleshooting file issues
- Adjust `code_list_threshold` (0.1-0.3) based on your data
- Check memory recommendations for large files first
- Use recursive search for complex directory structures

## Common Use Cases

- **Clinical Data**: CDISC SDTM/ADaM dataset analysis
- **SDTM Mapping**: Converting Excel specifications to LLM-friendly JSON
- **Data Discovery**: Understanding unknown SAS file structures  
- **Migration Planning**: Schema extraction for database conversions
- **Quality Assessment**: Data profiling and validation
    """


@mcp.resource("sas-analyzer://help/troubleshooting")  
def get_troubleshooting_guide() -> str:
    """Provides troubleshooting guide for common issues."""
    return """
# SAS Schema Analyzer - Troubleshooting Guide

## Common Issues and Solutions

### File Not Found Errors
- Check file path spelling and case sensitivity
- Ensure file extension is .sas7bdat
- Verify file permissions and access rights
- Try using absolute paths instead of relative paths

### Memory Issues with Large Files
- Use `get_memory_recommendations()` first
- Close other applications to free memory
- Consider processing files individually vs batch
- Large files automatically use sampling mode

### Analysis Errors
- Enable `debug=True` for detailed logging
- Check if file is corrupted or locked
- Ensure SAS file version compatibility
- Try with a smaller test file first

### Windows Path Issues
- Use forward slashes (/) or double backslashes (\\\\)
- For long paths, ensure Windows long path support is enabled
- Avoid special characters in file paths
- Use raw strings: r"C:\\path\\to\\file.sas7bdat"

### Performance Optimization
- Process files individually for better error handling
- Use appropriate `max_files` limits for batch processing
- Monitor system memory during large operations
- Consider recursive vs non-recursive folder scanning

## Getting Help

Include these details when reporting issues:
- File path and size
- Error message and type
- System memory available
- Windows version and Python version
    """


def main():
    """Main entry point - runs MCP server in STDIO mode for Claude Desktop integration."""
    print("SAS Schema Analyzer MCP Server Starting...")
    print("Features: SAS file analysis, SDTM spec reading, Memory management")
    print("Tools: analyze_sas_file, analyze_sas_folder, list_sas_files, get_memory_recommendations, analyze_sdtm_spec, list_sdtm_domains")
    print("Windows support with long path handling")
    print("\n" + "="*60)
    print("Server running - ready for Claude Desktop integration!")
    print("="*60 + "\n")
    mcp.run()


# Main execution block
if __name__ == "__main__":
    main()
