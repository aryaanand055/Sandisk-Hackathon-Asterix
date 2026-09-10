#!/usr/bin/env python3
"""
Stub handler for waveform / database files (VCD, FSDB, WLF).

Full waveform parsing is complex and out of scope for this iteration.
This module detects waveform files, reports availability, and extracts
basic metadata (format, size, associated run IDs from filenames).
"""

import os
import re
from typing import Any, Dict, List

# Supported waveform extensions
WAVEFORM_EXTENSIONS = {".vcd", ".fsdb", ".wlf", ".shm", ".vpd", ".trn"}


def is_waveform(path: str) -> bool:
    """Check if a file is a waveform/database file by extension."""
    _, ext = os.path.splitext(path.lower())
    return ext in WAVEFORM_EXTENSIONS


def classify_waveforms(paths: List[str]) -> Dict[str, Any]:
    """Classify waveform files and extract metadata.

    Returns a summary dict with format, count, and associated run IDs.
    """
    waveforms = [p for p in paths if is_waveform(p)]
    if not waveforms:
        return {
            "available": False,
            "message": "No waveform/database files provided.",
            "files": [],
        }

    files_info = []
    run_ids = []
    formats = set()

    for wf in waveforms:
        base = os.path.basename(wf)
        _, ext = os.path.splitext(base)
        fmt = ext.lstrip(".").upper()
        formats.add(fmt)
        size = os.path.getsize(wf) if os.path.exists(wf) else 0

        # Try to extract run_id from filename (e.g. RUN-000001.vcd)
        m = re.match(r"(RUN[_-]\d+)", base, re.I)
        rid = m.group(1) if m else None
        if rid:
            run_ids.append(rid)

        files_info.append({
            "path": base,
            "format": fmt,
            "size_bytes": size,
            "run_id": rid,
        })

    return {
        "available": True,
        "message": (
            f"{len(waveforms)} waveform file(s) detected ({', '.join(sorted(formats))} format). "
            f"Internal RTL signal analysis from waveforms is available for inspection."
        ),
        "n_files": len(waveforms),
        "formats": sorted(formats),
        "run_ids": run_ids,
        "files": files_info,
        "note": (
            "Full waveform parsing (signal extraction, FSM analysis) is not yet "
            "implemented. The dashboard shows that waveform data is available. "
            "Signal-level analysis can be added in a future iteration."
        ),
    }
