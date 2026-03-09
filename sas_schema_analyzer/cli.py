"""
sas-schema CLI — standalone command-line tool for SAS schema extraction.

Usage:
  sas-schema analyze <path>              # single file → JSON to stdout
  sas-schema analyze <path> --output F  # single file → write to F
  sas-schema analyze <dir>              # batch → one .json per file, same dir
  sas-schema analyze <dir> --recursive  # batch with subdirectories
  sas-schema list <dir>                 # discover SAS files
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .core import SasSchemaAnalyzer


def _write_json(data: dict, output_path: Path, indent: int) -> None:
    output_path.write_text(json.dumps(data, indent=indent, default=str), encoding="utf-8")


def _print_json(data: dict, indent: int) -> None:
    print(json.dumps(data, indent=indent, default=str))


async def _analyze_single(args) -> int:
    analyzer = SasSchemaAnalyzer(code_list_threshold=args.threshold, debug=args.debug)
    result = await analyzer.analyze_file(args.path, None)

    if args.output:
        _write_json(result, Path(args.output), args.indent)
        print(f"Schema written to: {args.output}", file=sys.stderr)
    else:
        _print_json(result, args.indent)

    return 0 if result.get("success") else 1


async def _analyze_batch(args) -> int:
    analyzer = SasSchemaAnalyzer(code_list_threshold=args.threshold, debug=args.debug)
    result = await analyzer.analyze_folder(
        folder_path=args.path,
        recursive=args.recursive,
        max_files=args.max_files,
        ctx=None,
    )

    if not result.get("success"):
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1

    written = 0
    for file_result in result.get("results", []):
        file_path = Path(file_result.get("file_path", ""))
        if not file_path.name:
            continue
        out_path = file_path.with_suffix(".json")
        _write_json(file_result, out_path, args.indent)
        written += 1

    successful = result.get("successful_analyses", 0)
    failed = result.get("failed_analyses", 0)
    print(
        f"Batch complete: {successful} succeeded, {failed} failed. "
        f"{written} JSON files written.",
        file=sys.stderr,
    )
    # Print summary to stdout as JSON
    summary = {
        "success": True,
        "folder_path": result.get("folder_path"),
        "successful_analyses": successful,
        "failed_analyses": failed,
        "json_files_written": written,
    }
    _print_json(summary, args.indent)

    return 0 if failed == 0 else 1


def _cmd_analyze(args) -> int:
    path = Path(args.path)
    if path.is_dir() or args.batch:
        return asyncio.run(_analyze_batch(args))
    return asyncio.run(_analyze_single(args))


async def _list_files(args) -> int:
    analyzer = SasSchemaAnalyzer()
    result = await analyzer.list_sas_files(
        directory=args.directory,
        recursive=args.recursive,
        ctx=None,
    )
    _print_json(result, args.indent)
    return 0 if result.get("success") else 1


def _cmd_list(args) -> int:
    return asyncio.run(_list_files(args))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sas-schema",
        description="Extract SAS7BDAT schema as JSON",
    )
    parser.add_argument(
        "--indent", type=int, default=2, metavar="N",
        help="JSON indent level (default: 2)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- analyze ---
    p_analyze = sub.add_parser("analyze", help="Analyze one SAS file or a folder of SAS files")
    p_analyze.add_argument("path", help="Path to a .sas7bdat file or a directory")
    p_analyze.add_argument("--batch", action="store_true",
                           help="Treat path as a folder even if it has a .sas7bdat extension")
    p_analyze.add_argument("--recursive", action="store_true",
                           help="Recurse into subdirectories (batch mode only)")
    p_analyze.add_argument("--max-files", type=int, default=50, metavar="N",
                           help="Max files to process in batch mode (default: 50)")
    p_analyze.add_argument("--threshold", type=float, default=0.15, metavar="F",
                           help="Code list detection threshold 0.0-1.0 (default: 0.15)")
    p_analyze.add_argument("--output", metavar="FILE",
                           help="Single-file mode: write JSON to this file instead of stdout")
    p_analyze.add_argument("--debug", action="store_true", help="Enable verbose logging")
    p_analyze.set_defaults(func=_cmd_analyze)

    # --- list ---
    p_list = sub.add_parser("list", help="Discover SAS7BDAT files in a directory")
    p_list.add_argument("directory", help="Directory to search")
    p_list.add_argument("--recursive", action="store_true",
                        help="Recurse into subdirectories")
    p_list.set_defaults(func=_cmd_list, indent=2)
    p_list.add_argument("--indent", type=int, default=2, metavar="N",
                        help="JSON indent level (default: 2)")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))
