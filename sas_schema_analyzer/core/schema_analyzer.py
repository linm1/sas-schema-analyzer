"""
SAS Schema Analyzer - Simplified Core Engine

This is a simplified version to get the MCP server working quickly.
It maintains the core functionality from your extract_sas_schema.py
"""

import os
import pandas as pd
import pyreadstat
from typing import Dict, Any, Optional
from pathlib import Path
from .date_analyzer import DateFormatAnalyzer
from .type_analyzer import DataTypeAnalyzer


_SAS_FILE_GLOB = "*.sas7bdat"
_SAS_FILE_EXT = ".sas7bdat"

# Encodings tried in order when pyreadstat's default UTF-8 decode of the
# sas7bdat header/metadata raises UnicodeDecodeError. 'latin1' maps every byte
# 0x00-0xFF to a Unicode codepoint, so it can never raise — this guarantees the
# read completes without inspecting any datalines.
_ENCODING_FALLBACKS: tuple = ("latin1",)


def _read_sas7bdat_with_fallback(file_path: str):
    """Read a sas7bdat file, retrying with byte-safe encodings on UnicodeDecodeError.

    Returns (df, meta, used_encoding). `used_encoding` is None when the library
    default succeeded, otherwise the fallback name that worked. Non-UnicodeDecodeError
    exceptions propagate unchanged so the caller's standard error handler reports them.
    """
    try:
        df, meta = pyreadstat.read_sas7bdat(file_path)
        return df, meta, None
    except UnicodeDecodeError:
        last_error = None
        for enc in _ENCODING_FALLBACKS:
            try:
                df, meta = pyreadstat.read_sas7bdat(file_path, encoding=enc)
                return df, meta, enc
            except UnicodeDecodeError as e:
                last_error = e
                continue
        raise last_error


class SasSchemaAnalyzer:
    """Simplified SAS schema analysis engine"""

    def __init__(self, code_list_threshold: float = 0.15, debug: bool = False):
        self.code_list_threshold = code_list_threshold
        self.debug = debug
        self.date_analyzer = DateFormatAnalyzer()
        self.type_analyzer = DataTypeAnalyzer(self.date_analyzer)

    @staticmethod
    def _find_sas_files(root: str, recursive: bool, max_files: int = 0) -> list:
        """Return .sas7bdat paths under root. max_files=0 means no limit."""
        found = []
        if recursive:
            for p in Path(root).rglob(_SAS_FILE_GLOB):
                found.append(str(p))
                if max_files and len(found) >= max_files:
                    break
        else:
            for name in os.listdir(root):
                if name.lower().endswith(_SAS_FILE_EXT):
                    found.append(os.path.join(root, name))
                    if max_files and len(found) >= max_files:
                        break
        return found
    
    async def analyze_file(self, file_path: str, ctx: Any = None) -> Dict[str, Any]:
        """Analyze a single SAS file"""
        try:
            # Normalize path for Windows
            file_path = os.path.normpath(file_path)
            
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": "File not found",
                    "file_path": file_path
                }
            
            if ctx:
                await ctx.info(f"Reading SAS file: {os.path.basename(file_path)}")
                await ctx.report_progress(10, 100, "Reading file...")
            
            # Read the SAS file (with encoding fallback for non-UTF-8 metadata)
            df, meta, used_encoding = _read_sas7bdat_with_fallback(file_path)
            
            if ctx:
                await ctx.report_progress(50, 100, "Analyzing schema...")
            
            row_count = len(df)
            # Compute unique counts in a single vectorized pass
            nunique_counts = df.nunique()

            # Build schema
            schema = {
                "success": True,
                "file_path": file_path,
                "row_count": row_count,
                "column_count": len(df.columns),
                "file_label": getattr(meta, 'file_label', None),
                "used_encoding": used_encoding,
                "columns": []
            }

            # Analyze each column
            for col_name in df.columns:
                unique_count = int(nunique_counts[col_name])
                col_info = {
                    "name": col_name,
                    "label": meta.column_names_to_labels.get(col_name, None),
                    "unique_count": unique_count,
                }

                # Determine SAS data type using the enhanced analyzer
                col_info["sas_data_type"] = self.type_analyzer.get_sas_data_type(col_name, df, meta, self.debug)

                # Date analysis
                date_analysis = self.date_analyzer.analyze_date_series(df[col_name])
                if date_analysis.get("is_date", False):
                    col_info["date_format_analysis"] = date_analysis

                # Code list detection (for both character and numeric)
                # Only consider if not an ID-like column and unique count is low
                if (unique_count <= 20 and
                    ((unique_count / row_count < self.code_list_threshold) or (row_count <= 20)) and
                    not self.type_analyzer.is_id_like_column(col_name, df[col_name]) and
                    not self.type_analyzer.is_result_column(col_name, df[col_name])):
                    
                    value_counts = df[col_name].value_counts(dropna=False).to_dict()
                    col_info["code_list"] = {str(k): int(v) for k, v in value_counts.items()}
                
                schema["columns"].append(col_info)
            
            if ctx:
                await ctx.report_progress(100, 100, "Analysis complete")
            
            return schema
            
        except Exception as e:
            if ctx:
                await ctx.error(f"Analysis failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    async def analyze_folder(self, folder_path: str, recursive: bool = False, 
                           max_files: int = 50, ctx: Any = None) -> Dict[str, Any]:
        """Analyze all SAS files in a folder"""
        try:
            folder_path = os.path.normpath(folder_path)
            
            if not os.path.exists(folder_path):
                return {
                    "success": False,
                    "error": "Directory not found",
                    "folder_path": folder_path
                }
            
            # Find SAS files
            sas_files = self._find_sas_files(folder_path, recursive, max_files)
            
            if ctx:
                await ctx.info(f"Found {len(sas_files)} SAS files to process")
            
            results = []
            successful = 0
            failed = 0
            
            for i, file_path in enumerate(sas_files):
                if ctx:
                    progress = (i / len(sas_files)) * 100
                    await ctx.report_progress(progress, 100, f"Processing {i+1}/{len(sas_files)}")
                
                try:
                    result = await self.analyze_file(file_path, ctx)
                    if result.get("success"):
                        successful += 1
                    else:
                        failed += 1
                    
                    results.append(result)
                except Exception as e:
                    failed += 1
                    results.append({
                        "success": False,
                        "error": str(e),
                        "file_path": file_path
                    })
            
            return {
                "success": True,
                "folder_path": folder_path,
                "successful_analyses": successful,
                "failed_analyses": failed,
                "results": results
            }
            
        except Exception as e:
            if ctx:
                await ctx.error(f"Folder analysis failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "folder_path": folder_path
            }
    
    async def list_sas_files(self, directory: str, recursive: bool = False, 
                           ctx: Any = None) -> Dict[str, Any]:
        """List SAS files in a directory"""
        try:
            directory = os.path.normpath(directory)
            
            if not os.path.exists(directory):
                return {
                    "success": False,
                    "error": "Directory not found",
                    "directory": directory
                }
            
            sas_files = self._find_sas_files(directory, recursive)
            
            file_info = []
            for file_path in sas_files:
                try:
                    stat = os.stat(file_path)
                    file_info.append({
                        "file_path": file_path,
                        "size_bytes": stat.st_size,
                    })
                except OSError:
                    file_info.append({
                        "file_path": file_path,
                        "error": "Could not access file"
                    })
            
            return {
                "success": True,
                "directory": directory,
                "files_found": len(file_info),
                "files": file_info
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "directory": directory
            }
