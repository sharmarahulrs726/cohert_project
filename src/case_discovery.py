"""
Case discovery module — scans input directories and builds CaseManifest records.

Supports two modes:
- **Single mode**: all three required files (Form16, AIS, ITR_Extract) are
  placed directly in the input directory.
- **Batch mode**: each subfolder inside the input directory represents one
  case and must contain the three required files (with flexible naming).
"""

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional

from src.utils import sha256_file, now_iso


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------
@dataclass
class CaseManifest:
    """Describes a discovered case and its source files."""

    case_id: str
    case_name: str
    input_mode: str
    case_path: str
    files: Dict[str, str]                 # role -> file path
    template_path: str
    discovered_at: str
    file_hashes: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# File alias maps (flexible name matching)
# ---------------------------------------------------------------------------
FILE_ALIASES: Dict[str, List[str]] = {
    "form16": [
        "Form16.docx", "Form 16.docx", "form16.docx", "form_16.docx",
        "Form16.xlsx", "Form 16.xlsx", "form16.xlsx", "Form_16.xlsx", "form_16.xlsx",
    ],
    "ais": [
        "AIS.docx", "ais.docx",
        "AIS.xlsx", "ais.xlsx",
    ],
    "itr": [
        "ITR_Extract.docx", "ITR Extract.docx", "itr_extract.docx",
        "ITR.docx", "itr.docx",
        "ITR_Extract.xlsx", "ITR Extract.xlsx", "itr_extract.xlsx",
        "ITR.xlsx", "itr.xlsx",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_name(name: str) -> str:
    """Lower-case alphanumeric only — used for loose file matching."""
    return "".join(ch.lower() for ch in name if ch.isalnum())


def find_case_file(folder: Path, aliases: List[str]) -> Optional[Path]:
    """Locate a case file by alias list using case-insensitive + normalised lookup.

    Builds both lookup dicts in a single pass over the directory listing.
    """
    if not folder.exists():
        return None

    by_lower: dict[str, Path] = {}
    by_norm: dict[str, Path] = {}
    for p in folder.iterdir():
        if p.is_file():
            by_lower[p.name.lower()] = p
            by_norm[normalize_name(p.name)] = p

    for alias in aliases:
        if alias.lower() in by_lower:
            return by_lower[alias.lower()]
        if normalize_name(alias) in by_norm:
            return by_norm[normalize_name(alias)]

    return None


# ---------------------------------------------------------------------------
# Core discovery logic
# ---------------------------------------------------------------------------
def discover_cases(input_dir: Path, template_path: Optional[Path]) -> List[CaseManifest]:
    """
    Scan *input_dir* and return a list of :class:`CaseManifest` objects.

    *Single-case mode* — three required files in *input_dir* itself.
    *Batch mode* — one sub‑folder per case.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    subfolders = [
        p for p in input_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]

    manifests: List[CaseManifest] = []

    # single-case mode
    single_form16 = find_case_file(input_dir, FILE_ALIASES["form16"])
    single_ais = find_case_file(input_dir, FILE_ALIASES["ais"])
    single_itr = find_case_file(input_dir, FILE_ALIASES["itr"])

    has_single_case_files = all([single_form16, single_ais, single_itr])
    has_subfolders = len(subfolders) > 0

    if has_single_case_files and has_subfolders:
        raise ValueError(
            "Invalid input structure: do not mix direct input files and case subfolders."
        )

    if has_single_case_files:
        files = {
            "form16": str(single_form16),
            "ais": str(single_ais),
            "itr": str(single_itr),
        }
        file_hashes = {role: sha256_file(Path(path)) for role, path in files.items()}
        manifests.append(
            CaseManifest(
                case_id="CASE_001",
                case_name="CASE_001",
                input_mode="single",
                case_path=str(input_dir),
                files=files,
                template_path=str(template_path),
                discovered_at=now_iso(),
                file_hashes=file_hashes,
            )
        )
        return manifests

    # batch mode
    if has_subfolders:
        valid_idx = 1
        for folder in sorted(subfolders):
            form16_file = find_case_file(folder, FILE_ALIASES["form16"])
            ais_file = find_case_file(folder, FILE_ALIASES["ais"])
            itr_file = find_case_file(folder, FILE_ALIASES["itr"])

            missing = []
            if not form16_file:
                missing.append("Form16")
            if not ais_file:
                missing.append("AIS")
            if not itr_file:
                missing.append("ITR_Extract")

            if missing:
                print(f"Skipping {folder.name}; missing logical files: {missing}")
                print("Available files:", [p.name for p in folder.iterdir() if p.is_file()])
                continue

            files = {
                "form16": str(form16_file),
                "ais": str(ais_file),
                "itr": str(itr_file),
            }
            file_hashes = {role: sha256_file(Path(path)) for role, path in files.items()}

            manifests.append(
                CaseManifest(
                    case_id=f"CASE_{valid_idx:03d}",
                    case_name=folder.name,
                    input_mode="batch",
                    case_path=str(folder),
                    files=files,
                    template_path=str(template_path),
                    discovered_at=now_iso(),
                    file_hashes=file_hashes,
                )
            )
            valid_idx += 1

        if not manifests:
            raise ValueError(
                f"No valid cases found in {input_dir}. "
                f"Each case folder must contain logical equivalents of Form16, AIS, and ITR files."
            )

        return manifests

    raise ValueError(
        "No valid cases found. Provide either a single case directly in input_dir "
        "or one subfolder per case."
    )
