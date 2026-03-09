# SAS Schema Analyzer

A FastMCP server for analyzing SAS7BDAT files and extracting comprehensive metadata. Built with advanced SAS analysis logic and enhanced with modern MCP integration, memory management, and Windows support.

## Features

- **Comprehensive Schema Analysis**: Extract complete metadata from SAS7BDAT files
- **Advanced Date Detection**: Supports 15+ date formats including partial dates and ISO 8601
- **Smart Code List Generation**: Automatically identifies categorical variables
- **Memory-Aware Processing**: Handles large files (1GB+) with intelligent sampling
- **Windows Optimized**: Full Windows path support including long paths
- **Batch Processing**: Analyze entire folders with progress reporting
- **Robust Error Handling**: Comprehensive troubleshooting guidance
- **CLI Tool**: Run schema extraction directly from the command line

## Quick Start

### Installation

```cmd
pip install -e .
```

This installs all dependencies and registers two commands:
- `sas-schema` -- CLI tool for direct schema extraction
- `sas-schema-analyzer` -- MCP server entry point

### CLI Usage

The `sas-schema` command is installed alongside the package and requires no MCP server or AI assistant. It is the fastest way to extract schema from a SAS file.

**Analyze a single file** (JSON to stdout):
```cmd
sas-schema analyze C:\data\demographics.sas7bdat
```

**Write output to a file:**
```cmd
sas-schema analyze C:\data\demographics.sas7bdat --output schema.json
```

**Batch process a folder** (writes one `.json` per file):
```cmd
sas-schema analyze C:\clinical_data\ --recursive --max-files 100
```

**Discover SAS files in a directory:**
```cmd
sas-schema list C:\data\
sas-schema list C:\clinical_data\ --recursive
```

**Key options:**

| Option | Description |
|---|---|
| `--output FILE` | Write JSON to a file (single-file mode only) |
| `--recursive` | Recurse into subdirectories |
| `--max-files N` | Max files for batch mode (default: 50) |
| `--threshold F` | Code list detection threshold 0.0--1.0 (default: 0.15) |
| `--debug` | Enable verbose logging |

See [QUICK_START.md](QUICK_START.md) for full setup instructions.

---

## GitHub Copilot Integration (VS Code)

The MCP server integrates with GitHub Copilot via `mcp.json`.

### Setup

1. Edit or create `%APPDATA%\Code\User\mcp.json`:

   ```json
   {
     "servers": {
       "sas-schema-analyzer": {
         "type": "stdio",
         "command": "py",
         "args": ["-m", "sas_schema_analyzer.server"],
         "cwd": "C:\\Users\\YourName\\Documents\\python\\sas_schema_analyzer"
       }
     },
     "inputs": []
   }
   ```

   Replace the `cwd` value with the actual path to this folder.

2. Restart VS Code completely.

3. The MCP tools will be available in GitHub Copilot Chat.

### Alternative: uvx

If you have `uv` installed, you can run the server without a local install:

```json
{
  "servers": {
    "sas-schema-analyzer": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "C:\\Users\\YourName\\Documents\\python\\sas_schema_analyzer", "sas-schema-analyzer"]
    }
  },
  "inputs": []
}
```

### Verification

Run the server manually to confirm it starts:

```cmd
py -m sas_schema_analyzer.server
```

Expected output:
```
SAS Schema Analyzer MCP Server Starting...
Features: SAS file analysis, SDTM spec reading, Memory management
...
Server running - ready for integration!
```

### Troubleshooting

**Tools not showing in Copilot Chat**
- Check the `mcp.json` path: `%APPDATA%\Code\User\mcp.json`
- Verify JSON syntax (no trailing commas)
- Confirm the `cwd` path matches this folder's actual location
- Restart VS Code completely

**Permission Issues**
- Run Command Prompt as Administrator if needed
- Verify `py` or `python` is on the system PATH

**Dependencies Missing**
```cmd
pip install fastmcp pyreadstat pandas numpy psutil
```

---

## Available Tools

### `analyze_sas_file`
Extract comprehensive schema from a single SAS7BDAT file.

**Parameters:**
- `file_path` (str): Path to SAS7BDAT file
- `code_list_threshold` (float): Threshold for categorical detection (0.0-1.0, default 0.15)
- `debug` (bool): Enable detailed logging (default False)

**Returns:**
- Complete file metadata and column schema
- Data type analysis (character vs numeric with evidence)
- Date format detection with partial date support
- Code lists for categorical variables
- Data quality metrics and statistics

### `analyze_sas_folder`
Batch process all SAS7BDAT files in a directory.

**Parameters:**
- `folder_path` (str): Directory containing SAS files
- `code_list_threshold` (float): Categorical detection threshold (default 0.15)
- `recursive` (bool): Include subdirectories (default False)
- `max_files` (int): Safety limit for processing (default 50)
- `debug` (bool): Enable detailed logging (default False)

**Returns:**
- Individual analysis results for each file
- Aggregate statistics and success rates
- Memory usage patterns and processing modes

### `list_sas_files`
Discover SAS7BDAT files in a directory with metadata.

**Parameters:**
- `directory` (str): Directory to search
- `recursive` (bool): Include subdirectories (default False)

**Returns:**
- List of all SAS files with sizes and dates
- Memory processing recommendations
- Total directory statistics

### `get_memory_recommendations`
Analyze memory requirements for processing a file.

**Parameters:**
- `file_path` (str): Path to SAS file

**Returns:**
- File size analysis and memory estimates
- Processing mode recommendations
- System memory assessment

### `analyze_sdtm_spec`
Read an SDTM specification Excel file and extract domain metadata.

**Parameters:**
- `file_path` (str): Path to .xls or .xlsx spec file
- `domain` (str): Domain name to extract (e.g., "DM", "AE")

### `list_sdtm_domains`
List all domains found in an SDTM specification Excel file.

**Parameters:**
- `file_path` (str): Path to .xls or .xlsx spec file

---

## Analysis Features

### Data Type Detection
Uses multiple evidence sources to determine character vs numeric:
- SAS metadata inspection (`column_types`, `readstat_variable_types`)
- Format analysis (`$` prefix, date formats)
- Column naming patterns (DTC, DATE suffixes)
- Data content analysis and casting tests
- Pandas dtype confirmation

### Date Format Analysis
Detects and analyzes 15+ date patterns:
- ISO 8601: `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS`
- US Format: `MM/DD/YYYY`
- European: `DD-MM-YYYY`
- Compact: `YYYYMMDD`, `DDMMYYYY`
- Text months: `DDMMMYYYY`, `YYYYMMMDD`
- Partial dates: `YYYY-MM`, `YYYY`
- Placeholder detection: `UNK`, `UK`, `UNKNOWN`, etc.

### Code List Generation
Intelligently identifies categorical variables while excluding:
- ID fields (high cardinality with patterns)
- Result/measurement columns
- Flag variables (Y/N, True/False patterns)
- Columns with >50 unique values

### Memory Management
Handles large files with smart fallback:
- File size estimation vs available memory
- Automatic sampling mode for 1GB+ files
- Progress reporting for long operations
- Memory usage monitoring and recommendations

---

## Project Structure

```
sas_schema_analyzer/           -- project root
├── pyproject.toml
├── requirements.txt
├── QUICK_START.md
├── sas_schema_analyzer/       -- package
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                 -- sas-schema CLI entry point
│   ├── server.py              -- FastMCP server
│   └── core/
│       ├── schema_analyzer.py -- main analysis engine
│       ├── date_analyzer.py   -- date format detection
│       ├── type_analyzer.py   -- data type analysis
│       ├── memory_manager_simple.py
│       └── sdtm_analyzer.py
└── tests/
```

---

## Use Cases

### Clinical Data Analysis
Designed for CDISC SDTM/ADaM datasets:
- Demographics (DM) table analysis
- Adverse Events (AE) with date patterns
- Laboratory data (LB) with result values
- Exposure (EX) with dosing information

### Data Discovery
Explore unknown SAS file structures:
- Quick schema overview
- Data type distribution
- Quality assessment metrics
- Code list identification

### Migration Planning
Schema extraction for database conversions:
- Complete metadata export
- Data type mapping guidance
- Format preservation information

---

## Configuration

### Code List Threshold
Adjust categorical variable detection:
- `0.05`: Very strict (5% unique values)
- `0.15`: Default balanced setting
- `0.30`: Permissive (30% unique values)

### Memory Settings
Default memory management:
- Threshold: 50% of available RAM
- Sample size: 10,000 rows for large files
- Automatic fallback for 1GB+ files

### Debug Mode
Enable for troubleshooting:
```cmd
sas-schema analyze file.sas7bdat --debug
```
Or in MCP tool calls: `debug=True`

---

## Troubleshooting

**File Not Found**
```cmd
sas-schema analyze "C:\full\path\to\file.sas7bdat"
```

**Memory Issues**
```cmd
# Check requirements before analyzing
sas-schema analyze large_file.sas7bdat
# Large files automatically use sampling
```

**Windows Path Issues**
Use forward slashes or raw strings:
```
C:/data/file.sas7bdat
C:\\data\\file.sas7bdat
```

---

## Example Output

```json
{
  "success": true,
  "file_path": "C:/data/demographics.sas7bdat",
  "row_count": 1500,
  "column_count": 25,
  "file_label": "Demographics Dataset",
  "columns": [
    {
      "name": "USUBJID",
      "label": "Unique Subject Identifier",
      "sas_data_type": "character",
      "unique_count": 1500
    },
    {
      "name": "BIRTHDT",
      "label": "Date of Birth",
      "sas_data_type": "character",
      "unique_count": 1200,
      "date_format_analysis": {
        "formats": [{"format": "YYYY-MM-DD", "match_percentage": 98.5}],
        "is_date": true
      }
    },
    {
      "name": "GENDER",
      "label": "Gender",
      "sas_data_type": "character",
      "unique_count": 2,
      "code_list": {"M": 750, "F": 750}
    }
  ]
}
```

---

## Dependencies

- [fastmcp](https://github.com/jlowin/fastmcp) -- MCP framework
- [pyreadstat](https://github.com/Roche/pyreadstat) -- SAS file reading
- [pandas](https://pandas.pydata.org/) -- data manipulation
- [numpy](https://numpy.org/) -- numerical operations
- [psutil](https://github.com/giampaolo/psutil) -- memory management
