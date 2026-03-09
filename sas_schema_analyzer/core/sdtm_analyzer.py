"""
SDTM Specification Analyzer

Reads SDTM specification Excel files and converts domain-specific information
into LLM-friendly JSON format optimized for clinical data mapping workflows.

Features:
- Excel file reading (.xlsx, .xlsm, .xls)
- Multi-sheet processing (Variables, Datasets, Codelists, Methods, Comments)
- Domain-specific extraction with reference resolution
- UTF-8 transmission safety for FastMCP STDIO
- Instruction consolidation (Method + Comment + Value/Note)
- Simplified codelist terms for LLM consumption

Author: Claude Sonnet 4 + User Collaboration
Framework: FastMCP 2.0+ with openpyxl
"""

import os
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional

import pandas as pd


class SDTMSpecAnalyzer:
    """
    Analyzes SDTM specification Excel files and extracts domain-specific
    information in LLM-friendly JSON format.
    """
    
    def __init__(self):
        self.debug = False
        self.required_sheets = ['Variables', 'Datasets', 'Codelists', 'Methods', 'Comments']
        
    async def analyze_sdtm_spec(
        self, 
        file_path: str, 
        domain: str, 
        ctx: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Extract SDTM domain specification from Excel file in LLM-friendly JSON format.
        
        Args:
            file_path: Path to SDTM specification Excel file
            domain: SDTM domain code (e.g., 'EX', 'DM', 'LB', 'AE')
            ctx: FastMCP context for progress reporting
            
        Returns:
            Domain specification with variables, codelists, and mapping instructions
        """
        try:
            if ctx:
                await ctx.info(f"Starting SDTM analysis for domain '{domain}'")
            
            # Validate file exists
            if not os.path.exists(file_path):
                return self._create_error_response(
                    f"File not found: {file_path}",
                    "FileNotFoundError",
                    file_path,
                    domain,
                    ["Verify file path is correct", "Check file permissions"]
                )
            
            # Read Excel sheets
            if ctx:
                await ctx.info("Reading Excel sheets...")
            sheets = await self._read_excel_sheets(file_path)
            
            if not sheets:
                return self._create_error_response(
                    "Failed to read Excel file or file is corrupted",
                    "ExcelReadError", 
                    file_path,
                    domain,
                    ["Check if file is password-protected", "Verify Excel file is not corrupted", "Ensure file is not open in another application"]
                )
            
            # Validate required sheets
            missing_sheets = [sheet for sheet in self.required_sheets if sheet not in sheets]
            if missing_sheets:
                return self._create_error_response(
                    f"Missing required sheets: {missing_sheets}",
                    "MissingSheetError",
                    file_path,
                    domain,
                    [f"Ensure Excel file contains sheets: {', '.join(missing_sheets)}", "Check if sheet names are spelled correctly"]
                )
            
            # Extract domain information
            if ctx:
                await ctx.info(f"Extracting domain '{domain}' specification...")
            
            result = await self._extract_domain_spec(domain, sheets, ctx)
            
            if ctx:
                var_count = len(result.get("specification", {}).get("variables", []))
                await ctx.info(f"Successfully extracted {var_count} variables for domain '{domain}'")
            
            return result
            
        except Exception as e:
            if ctx:
                await ctx.error(f"SDTM analysis failed: {str(e)}")
            
            if self.debug:
                error_details = traceback.format_exc()
                print(f"SDTM Analysis Error Details:\n{error_details}")
            
            return self._create_error_response(
                str(e),
                type(e).__name__,
                file_path,
                domain,
                ["Enable debug mode for detailed error information", "Check file format and structure"]
            )
    
    async def list_domains(self, file_path: str, ctx: Optional[Any] = None) -> Dict[str, Any]:
        """
        List all available domains in an SDTM specification Excel file.
        
        Args:
            file_path: Path to SDTM specification Excel file
            ctx: FastMCP context for progress reporting
            
        Returns:
            List of domains with metadata (domain code, name, class, description)
        """
        try:
            if ctx:
                await ctx.info("Reading SDTM specification file...")
            
            # Validate file exists
            if not os.path.exists(file_path):
                return self._create_error_response(
                    f"File not found: {file_path}",
                    "FileNotFoundError",
                    file_path,
                    None,
                    ["Verify file path is correct", "Check file permissions"]
                )
            
            # Read Excel sheets
            sheets = await self._read_excel_sheets(file_path)
            
            if not sheets or 'Datasets' not in sheets:
                return self._create_error_response(
                    "Failed to read Excel file or missing Datasets sheet",
                    "ExcelReadError",
                    file_path, 
                    None,
                    ["Check if file contains 'Datasets' sheet", "Verify Excel file is not corrupted"]
                )
            
            # Extract domains from Datasets sheet
            if ctx:
                await ctx.info("Extracting domain information...")
                
            datasets_df = sheets['Datasets']
            domains = []
            
            for _, row in datasets_df.iterrows():
                domain_code = self._safe_string(row.get('Dataset', ''))
                if domain_code:
                    domains.append({
                        "domain": domain_code,
                        "name": self._safe_string(row.get('Dataset Name', '')),
                        "class": self._safe_string(row.get('Class', '')),
                        "description": self._safe_string(row.get('Description', ''))
                    })
            
            if ctx:
                await ctx.info(f"Found {len(domains)} domains")
            
            return {
                "success": True,
                "file_path": file_path,
                "domain_count": len(domains),
                "domains": domains
            }
            
        except Exception as e:
            if ctx:
                await ctx.error(f"Domain listing failed: {str(e)}")
            
            return self._create_error_response(
                str(e),
                type(e).__name__,
                file_path,
                None,
                ["Check file format and structure", "Ensure Datasets sheet exists"]
            )
    
    async def _read_excel_sheets(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """Read all sheets from Excel file."""
        try:
            sheets = {}
            
            # Use openpyxl engine for broader compatibility
            with pd.ExcelFile(file_path, engine='openpyxl') as xls:
                for sheet_name in xls.sheet_names:
                    if sheet_name in self.required_sheets + ['ValueLevel']:
                        try:
                            df = pd.read_excel(xls, sheet_name=sheet_name, engine='openpyxl')
                            # Clean column names
                            df.columns = [self._clean_column_name(col) for col in df.columns]
                            sheets[sheet_name] = df
                        except Exception as e:
                            if self.debug:
                                print(f"Warning: Could not read sheet '{sheet_name}': {e}")
                            continue
            
            return sheets
            
        except Exception as e:
            if self.debug:
                print(f"Excel reading error: {e}")
            return {}
    
    async def _extract_domain_spec(
        self, 
        domain: str, 
        sheets: Dict[str, pd.DataFrame],
        ctx: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Extract domain-specific specification with codelist resolution."""
        
        # Get domain variables
        variables_df = sheets.get('Variables')
        if variables_df is None:
            return self._create_error_response(
                "Variables sheet not found",
                "MissingSheetError",
                None,
                domain,
                ["Ensure Excel file contains Variables sheet"]
            )
        
        # Filter variables for this domain
        domain_vars = variables_df[
            variables_df['Dataset'].str.upper() == domain.upper()
        ].copy() if 'Dataset' in variables_df.columns else pd.DataFrame()
        
        if domain_vars.empty:
            return self._create_error_response(
                f"No variables found for domain '{domain}'",
                "DomainNotFoundError",
                None,
                domain,
                [f"Check if domain '{domain}' exists in Variables sheet", "Verify domain name spelling"]
            )
        
        # Extract domain description
        datasets_df = sheets.get('Datasets')
        domain_description = ""
        if datasets_df is not None:
            domain_row = datasets_df[datasets_df['Dataset'].str.upper() == domain.upper()]
            if not domain_row.empty:
                domain_description = self._safe_string(domain_row.iloc[0].get('Description', ''))
        
        # Extract variables with instruction consolidation
        variables = {}  # Changed to dict with variable names as keys
        codelists = {}
        
        for _, var_row in domain_vars.iterrows():
            var_name = self._safe_string(var_row.get('Variable', ''))
            if not var_name:
                continue  # Skip rows without variable names
            
            # Extract basic variable info (using expected field names from user output)
            var_info = {
                "label": self._safe_string(var_row.get('Label', '')),
                "type": self._safe_string(var_row.get('Data Type', ''))  # Changed from data_type to type
            }
            
            # Build consolidated instruction
            instruction = await self._build_instruction(var_row, sheets)
            if instruction:
                var_info["instruction"] = instruction
            
            # Add source info if present
            source_dataset = self._safe_string(var_row.get('Source Dataset', ''))
            source_variable = self._safe_string(var_row.get('Source Variable', ''))
            if source_dataset:
                var_info["source_datasets"] = source_dataset
            if source_variable:
                var_info["source_variables"] = source_variable
            
            # Extract codelist if present
            codelist_id = self._safe_string(var_row.get('Codelist', ''))
            if codelist_id:
                codelist_terms = await self._extract_codelist_terms(codelist_id, sheets.get('Codelists'))
                var_info["codelist"] = codelist_id  # Always add codelist reference
                # Add terms to codelists dict even if empty (to match expected format)
                if codelist_terms:
                    # Apply transmission safety for codelists
                    codelists[codelist_id] = await self._make_transmission_safe(codelist_terms, ctx)
                else:
                    codelists[codelist_id] = []  # Empty array for missing codelists
            
            variables[var_name] = var_info  # Use variable name as key
        
        # Create final specification
        specification = {
            "domain": domain.upper(),
            "domain_description": domain_description,
            "variables": variables,
            "codelists": codelists
        }
        
        # DEBUG: Print codelists before returning (for verification)
        if self.debug:
            print(f"\n=== DEBUG: Final codelists before return ===")
            for cl_id, cl_terms in codelists.items():
                print(f"{cl_id}: {len(cl_terms)} terms -> {cl_terms[:3] if cl_terms else 'EMPTY'}...")
        
        return {
            "success": True,
            "file_path": None,
            "domain": domain.upper(),
            "variable_count": len(variables),
            "specification": specification
        }
    
    async def _build_instruction(self, var_row: pd.Series, sheets: Dict[str, pd.DataFrame]) -> str:
        """Build consolidated mapping instruction from Method + Comment + Value/Note."""
        instructions = []
        
        # Method description
        method_id = self._safe_string(var_row.get('Method', ''))
        if method_id:
            method_desc = await self._get_method_description(method_id, sheets.get('Methods'))
            if method_desc:
                instructions.append(method_desc)
        
        # Comment description
        comment_id = self._safe_string(var_row.get('Comment', ''))
        if comment_id:
            comment_desc = await self._get_comment_description(comment_id, sheets.get('Comments'))
            if comment_desc:
                instructions.append(comment_desc)
        
        # Direct value/note
        value_note = self._safe_string(var_row.get('Value/Note', ''))
        if value_note:
            instructions.append(value_note)
        
        return '\n'.join(instructions) if instructions else ""
    
    def _lookup_description(self, ref_id: str, df: Optional[pd.DataFrame], sheet_name: str) -> str:
        """Look up a Description value by ID in a reference DataFrame."""
        if df is None or not ref_id:
            return ""
        try:
            row = df[df['ID'] == ref_id]
            if not row.empty:
                return self._safe_string(row.iloc[0].get('Description', ''))
        except Exception as e:
            if self.debug:
                print(f"{sheet_name} lookup error for '{ref_id}': {e}")
        return ""

    async def _get_method_description(self, method_id: str, methods_df: Optional[pd.DataFrame]) -> str:
        return self._lookup_description(method_id, methods_df, "Method")

    async def _get_comment_description(self, comment_id: str, comments_df: Optional[pd.DataFrame]) -> str:
        return self._lookup_description(comment_id, comments_df, "Comment")
    
    async def _extract_codelist_terms(self, codelist_id: str, codelists_df: Optional[pd.DataFrame]) -> List[str]:
        """Extract simplified codelist terms, preferring English decoded values."""
        if codelists_df is None or not codelist_id:
            return []
        
        try:
            # Handle different codelist ID formats
            # Variables sheet may reference "(DSCAT)" but Codelists sheet has "DSCAT"
            search_id = codelist_id.strip('()')  # Remove parentheses
            
            # Skip special cases
            if search_id in ['*', '']:
                return []
            
            # Filter codelist entries by ID (try both with and without parentheses)
            codelist_entries = codelists_df[codelists_df['ID'] == search_id]
            if codelist_entries.empty:
                # Try with original ID in case it has parentheses
                codelist_entries = codelists_df[codelists_df['ID'] == codelist_id]
            
            if codelist_entries.empty:
                if self.debug:
                    print(f"No codelist entries found for ID '{codelist_id}' (searched as '{search_id}')")
                return []
            
            terms = []
            for _, row in codelist_entries.iterrows():
                # FORCE RELOAD: Always use TERM column as requested (Updated 2025-08-26)
                term = self._safe_string(row.get('Term', ''))
                
                if term:
                    # Handle Chinese encoding issues by ensuring proper UTF-8 encoding
                    try:
                        # Ensure the term is properly encoded as UTF-8
                        if isinstance(term, str):
                            # Re-encode to handle any encoding issues
                            term_bytes = term.encode('utf-8', errors='replace')
                            clean_term = term_bytes.decode('utf-8')
                            terms.append(clean_term)
                        else:
                            terms.append(str(term))
                    except (UnicodeEncodeError, UnicodeDecodeError) as e:
                        if self.debug:
                            print(f"Encoding error for term '{term}': {e}")
                        # Fallback: use ASCII-safe representation
                        safe_term = str(term).encode('ascii', errors='replace').decode('ascii')
                        terms.append(safe_term)
            
            # Remove duplicates preserving insertion order — O(n) with seen set
            seen: set = set()
            unique_terms = []
            for term in terms:
                if term and term not in seen:
                    seen.add(term)
                    unique_terms.append(term)
            
            if self.debug:
                print(f"Extracted {len(unique_terms)} terms for codelist '{codelist_id}': {unique_terms[:3]}...")
            
            return unique_terms
            
        except Exception as e:
            if self.debug:
                print(f"Codelist extraction error for '{codelist_id}': {e}")
            return []
    
    async def _make_transmission_safe(self, terms: List[str], ctx: Optional[Any] = None) -> List[str]:
        """
        Ensure codelist terms transmit safely through FastMCP STDIO JSON.
        
        SIMPLIFIED: Just pass through all terms as-is, let FastMCP handle encoding.
        """
        if self.debug:
            print(f"\n=== TRANSMISSION SAFETY: PASS-THROUGH MODE ===")
            print(f"Input: {len(terms)} terms -> {terms[:3] if terms else 'EMPTY'}...")
        
        # Filter out empty terms and return the rest as-is
        safe_terms = [term for term in terms if term and term.strip()]
        
        if self.debug:
            print(f"Output: {len(safe_terms)} terms -> {safe_terms[:3] if safe_terms else 'EMPTY'}...")
            if ctx:
                await ctx.info(f"Transmission safety: {len(safe_terms)}/{len(terms)} terms passed through")
        
        return safe_terms
    
    def _safe_string(self, value: Any) -> str:
        """Safely convert any value to string, handling NaN and None."""
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()
    
    def _clean_column_name(self, col_name: str) -> str:
        """Clean column names from Excel sheets."""
        if pd.isna(col_name):
            return "Unknown"
        return str(col_name).strip()
    
    def _create_error_response(
        self, 
        error: str, 
        error_type: str, 
        file_path: Optional[str], 
        domain: Optional[str],
        troubleshooting: List[str]
    ) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            "success": False,
            "error": error,
            "error_type": error_type,
            "file_path": file_path,
            "domain": domain,
            "troubleshooting": {
                "common_causes": [
                    "File path incorrect or file doesn't exist",
                    "Excel file is password-protected or corrupted", 
                    "Required SDTM sheets are missing or misnamed",
                    "Domain name doesn't exist in specification"
                ],
                "next_steps": troubleshooting
            }
        }