# CLAUDE.md — sas_schema_analyzer

Project-specific guide for Claude. Read before touching code.

## What this is

FastMCP server + standalone CLI that extracts schema/metadata from SAS7BDAT files
and SDTM specification Excel workbooks. Targets clinical data (CDISC SDTM/ADaM).
Python ≥3.11. Windows-first (long paths, normpath, py launcher).

Two entry points (`pyproject.toml`):
- `sas-schema` → [sas_schema_analyzer/cli.py](sas_schema_analyzer/cli.py) — argparse CLI, stdio JSON.
- `sas-schema-analyzer` → [sas_schema_analyzer/server.py](sas_schema_analyzer/server.py) — FastMCP stdio server.

Both wrap the same core: `SasSchemaAnalyzer`, `SDTMSpecAnalyzer`, `MemoryManager`.

## Architecture (real, not aspirational)

```
sas_schema_analyzer/
├── __init__.py          re-exports server.main
├── __main__.py          python -m entry
├── cli.py               argparse → asyncio.run(analyzer.*)
├── server.py            FastMCP tools wrap analyzer.* + ctx logging
└── core/
    ├── __init__.py      public surface (5 classes)
    ├── schema_analyzer.py   SasSchemaAnalyzer — orchestrator, pyreadstat read, folder walk
    ├── date_analyzer.py     DateFormatAnalyzer — 15+ format regex detection
    ├── type_analyzer.py     DataTypeAnalyzer — multi-evidence char/numeric inference
    ├── memory_manager_simple.py  MemoryManager — psutil-based size/mode recommendations
    └── sdtm_analyzer.py     SDTMSpecAnalyzer — Excel (openpyxl/xlrd) → domain JSON
tests/                   pytest, mock-heavy, no real .sas7bdat needed
isdb/                    real SAS data — DO NOT scan, large binary
```

Composition: `SasSchemaAnalyzer` owns `DateFormatAnalyzer` → injected into `DataTypeAnalyzer`.
Server module instantiates singletons (`analyzer`, `sdtm_analyzer`, `memory_mgr`) at import.

Key behavior: pyreadstat default UTF-8; on `UnicodeDecodeError` retries with `latin1`
([schema_analyzer.py:27-46](sas_schema_analyzer/core/schema_analyzer.py#L27-L46)). This is
load-bearing — don't remove without replacement.

Tool response shape: `{success: bool, ...payload, error?, error_type?, troubleshooting?}`.
Server uses `_tool_error()` helper to keep this consistent — reuse it.

## Working principles

### Think before coding
- Read `core/__init__.py` first to see public surface.
- For any analyzer change, read the test file alongside (`tests/test_*.py`) — tests
  document expected contracts more clearly than docstrings.
- pyreadstat / pandas behaviors differ across versions — verify with a quick repl
  read before assuming dtypes/metadata fields exist.

### Simplicity first
- No new abstraction layers. Five core classes is the limit until proven otherwise.
- No new files unless adding a genuinely new analyzer (peer of `date_analyzer`).
- Don't add config/DI frameworks. Constructors take primitives + optional injected analyzer.
- Don't introduce async where not needed — `analyze_file` is async only because MCP `ctx` is.
  Sync helpers stay sync.
- Don't add fallbacks or validators for cases that can't happen. Trust pyreadstat output past
  the encoding retry.

### Surgical changes
- Bug fix = touch the bug. No drive-by refactors, no docstring rewrites, no rename sweeps.
- One change per commit. Tests + impl in same commit (TDD pairs).
- If a change spans `cli.py` + `server.py` + `core/`, stop and reconsider — likely the core
  signature is wrong and only that should change; CLI/server should be thin.
- Preserve existing JSON keys in tool output. Downstream consumers (Copilot, scripts) depend on shape.

### Goal-driven execution
- The goal is correct schema JSON for clinical SAS files. Not a framework, not a library.
- "Does this help extract better schema?" gates every change.
- If user asks for X feature, ask whether the existing flag/threshold already covers it
  (`--threshold`, `code_list_threshold`, `recursive`, `max_files`, `debug`).

## Conventions in this repo

- **Path handling**: always `os.path.normpath` for inputs; `pathlib.Path` for new code.
  Windows long paths supported — don't strip `\\?\` prefixes.
- **Errors in tools**: never raise out of `@mcp.tool` — catch, return `_tool_error(...)`.
- **CLI exit codes**: `0` success, `1` failure. Batch returns `1` if any file failed.
- **JSON dump**: `json.dumps(..., default=str)` — handles datetime/Path. Keep it.
- **Logging**: MCP path uses `await ctx.info/error`. CLI prints to stderr for status,
  stdout for JSON payload. Don't mix.
- **Imports**: relative within package (`from .core import ...`). Absolute in tests.
- **Type hints**: required on public functions (PEP 8). `Dict[str, Any]` is the established
  return type for analyzer methods — match it.

## Workflow

### Setup
```cmd
pip install -e .
pytest
```

### Run locally
```cmd
sas-schema analyze C:\path\to\file.sas7bdat
sas-schema list C:\data\ --recursive
py -m sas_schema_analyzer.server     # MCP stdio server
```

### Tests
- pytest, mock-based. No real SAS files committed.
- TDD: failing test → impl → green. See [tests/test_cli.py](tests/test_cli.py) header for the pattern.
- Run: `pytest -v` or `pytest tests/test_type_analyzer.py::TestX -v`.
- Coverage target 80%+.

### Verify before claiming done
1. `pytest` green.
2. CLI smoke: `sas-schema analyze <small.sas7bdat>` returns valid JSON with `success: true`.
3. If touched server.py: `py -m sas_schema_analyzer.server` boots without import error.

## Off-limits (for Claude)

- **`isdb/`** — real clinical data, large binaries. Do not Read/Grep/Glob into it.
  Use it only as test target via CLI when the user explicitly says so.
- **`isdb_metadata.zip`** — same.
- `__pycache__/`, `.pytest_cache/`, `.git/` — ignore.

## Common pitfalls

- pyreadstat returns `meta.column_types` as `{name: "string"|"double"}` — NOT pandas dtypes.
  `type_analyzer` already handles this; don't duplicate logic.
- Date detection runs on **string** columns; numeric SAS dates are rare in DTC fields.
  See `DataTypeAnalyzer.get_sas_data_type` name-pattern branch (`DTC$|DATE$` → character).
- Code list threshold is a **ratio** (unique/total), not a count. Default 0.15.
- `analyze_folder` ignores files past `max_files` silently — bump explicitly when needed.
- FastMCP `Context` is required by tool signatures but `None` from CLI path; analyzer
  methods must tolerate `ctx=None`.

## When extending

New analyzer? → new file under `core/`, export from `core/__init__.py`, inject via
constructor. Don't add module-level singletons in `core/`.

New MCP tool? → add to `server.py`, wrap analyzer call in try/except, use `_tool_error`,
mirror in `cli.py` if it makes sense as a CLI subcommand.

New date format? → extend `DateFormatAnalyzer` patterns + add a test case. Don't touch
`type_analyzer`.
