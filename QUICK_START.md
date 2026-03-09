# SAS Schema Analyzer -- Quick Start Guide

## Prerequisites

- Windows 11
- Python 3.11 or later -- verify with: `python --version`
- pip -- verify with: `pip --version`

---

## Installation

Open a Command Prompt in this folder, then run:

```cmd
pip install -e .
```

This installs the package and all dependencies (fastmcp, pyreadstat, pandas, numpy, psutil, openpyxl, xlrd).

---

## GitHub Copilot Integration (VS Code)

1. Find or create the MCP config file at:
   ```
   %APPDATA%\Code\User\mcp.json
   ```

2. Add the following to the `servers` section (replace the path with the actual location of this folder):

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

   > Replace `C:\\Users\\YourName\\Documents\\python\\sas_schema_analyzer` with the full path to this folder.

3. Restart VS Code completely.

4. The following tools will be available in GitHub Copilot Chat:
   - `analyze_sas_file` -- extract schema from a single SAS file
   - `analyze_sas_folder` -- batch process a folder of SAS files
   - `list_sas_files` -- discover SAS files in a directory
   - `get_memory_recommendations` -- memory analysis for large files
   - `analyze_sdtm_spec` -- read an SDTM specification Excel file (.xls/.xlsx)
   - `list_sdtm_domains` -- list all domains in an SDTM spec file

---

## Alternative: Run from Console

If you installed with `pip install -e .`, you can also run the server directly:

```cmd
sas-schema-analyzer
```

Or without installing:

```cmd
py -m sas_schema_analyzer.server
```

---

## CLI Tool

The `sas-schema` command extracts SAS file schema directly from the command line, without opening Copilot Chat or running the MCP server. It is installed automatically alongside the package.

### Commands

**`analyze`** -- analyze a single file or an entire folder:

```cmd
sas-schema analyze C:\data\demographics.sas7bdat
sas-schema analyze C:\data\demographics.sas7bdat --output schema.json
sas-schema analyze C:\clinical_data\
sas-schema analyze C:\clinical_data\ --recursive --max-files 100
```

**`list`** -- discover all SAS7BDAT files in a directory:

```cmd
sas-schema list C:\data\
sas-schema list C:\clinical_data\ --recursive
```

### Options

| Option | Command | Description |
|---|---|---|
| `--output FILE` | analyze (single file) | Write JSON to a file instead of stdout |
| `--recursive` | analyze, list | Recurse into subdirectories |
| `--max-files N` | analyze (folder) | Maximum files to process (default: 50) |
| `--threshold F` | analyze | Code list detection threshold 0.0--1.0 (default: 0.15) |
| `--debug` | analyze | Enable verbose logging |
| `--indent N` | both | JSON indent level (default: 2) |

### Output

Single-file mode prints JSON to stdout:

```cmd
sas-schema analyze demographics.sas7bdat
```
```json
{
  "success": true,
  "file_path": "C:/data/demographics.sas7bdat",
  "row_count": 1500,
  "column_count": 25,
  ...
}
```

Folder (batch) mode writes one `.json` file next to each `.sas7bdat` file and prints a summary to stdout.

---

## Verification

To confirm the server starts correctly, run:

```cmd
py -m sas_schema_analyzer.server
```

You should see output like:
```
SAS Schema Analyzer MCP Server Starting...
Features: SAS file analysis, SDTM spec reading, Memory management
...
Server running - ready for integration!
```

Press `Ctrl+C` to stop.

---

## Basic Usage in Copilot Chat

```
Analyze a single SAS file
analyze_sas_file("C:/data/demographics.sas7bdat")

Batch process a folder
analyze_sas_folder("C:/clinical_data/", recursive=True)

Find all SAS files first
list_sas_files("C:/data/", recursive=True)

List SDTM domains
list_sdtm_domains("C:/specs/SDTM_Spec.xls")

Read a specific domain
analyze_sdtm_spec("C:/specs/SDTM_Spec.xls", "DM")
```

---

## Troubleshooting

**Tools not showing in Copilot Chat**: Restart VS Code after editing mcp.json.

**`pip install -e .` fails**: Make sure you are running the command from inside this folder and that Python 3.11+ is installed.

**`py` not found**: Try `python` instead, or check that Python is on your system PATH.

**File path errors in tools**: Use forward slashes (`C:/data/file.sas7bdat`) or double backslashes (`C:\\data\\file.sas7bdat`).

**Large files run slowly**: Use `get_memory_recommendations` first to check if chunked processing is needed.
