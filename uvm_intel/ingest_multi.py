#!/usr/bin/env python3
"""
Unified multi-file ingestion orchestrator.

Classifies uploaded files by extension and name, routes them to appropriate
parsers (UVM log parser for .log, CSV parsers for .csv, waveform stub for
VCD/FSDB/WLF), and merges all sources into a canonical DataFrame with the
same schema the analytics pipeline expects.

The key contract:
    parse_upload(paths) → (runs_df, errors_df, stats_dict)

This matches the signature of log_parser.parse_files() so the backend can
call either one interchangeably.
"""

import os
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from .csv_parser import classify_csv, parse_csvs, _normalise_outcome
from .log_parser import ParseStats, parse_files as parse_log_files
from .waveform_stub import classify_waveforms, is_waveform


def _classify_files(paths: List[str]) -> Dict[str, List[str]]:
    """Group uploaded files by type."""
    groups: Dict[str, List[str]] = {
        "log": [],
        "csv": [],
        "waveform": [],
        "other": [],
    }
    for p in paths:
        ext = os.path.splitext(p.lower())[1]
        if ext == ".log":
            groups["log"].append(p)
        elif ext == ".csv":
            groups["csv"].append(p)
        elif is_waveform(p):
            groups["waveform"].append(p)
        else:
            groups["other"].append(p)
    return groups


def _detect_mode(groups: Dict[str, List[str]]) -> str:
    """Detect input mode: 'legacy' (log only) or 'multi' (CSV files present)."""
    if groups["csv"]:
        return "multi"
    return "legacy"


def _merge_csv_tables(csv_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge per-category CSV DataFrames into a single run-level DataFrame.

    Uses 'run_id' as the join key. Each category adds its columns via
    left join so missing categories simply leave those columns absent.
    """
    # Start with outcomes or config as the base table
    base = None
    priority = ["outcomes", "config", "randomization", "telemetry",
                "transactions", "registers"]

    for cat in priority:
        if cat in csv_data and isinstance(csv_data[cat], pd.DataFrame):
            df = csv_data[cat]
            if "run_id" in df.columns and not df.empty:
                base = df
                break

    if base is None:
        # Try any available table with run_id
        for cat, df in csv_data.items():
            if isinstance(df, pd.DataFrame) and "run_id" in df.columns and not df.empty:
                base = df
                break

    if base is None:
        return pd.DataFrame()

    # Merge remaining tables
    for cat in priority:
        if cat in csv_data and isinstance(csv_data[cat], pd.DataFrame):
            df = csv_data[cat]
            if "run_id" in df.columns and not df.empty and not df.equals(base):
                # Avoid duplicate columns
                overlap = set(base.columns) & set(df.columns) - {"run_id"}
                if overlap:
                    df = df.drop(columns=list(overlap))
                base = base.merge(df, on="run_id", how="left")

    # Also merge any custom/unknown CSVs
    for cat, df in csv_data.items():
        if cat in priority or not isinstance(df, pd.DataFrame):
            continue
        if cat.startswith("custom_") and "run_id" in df.columns and not df.empty:
            overlap = set(base.columns) & set(df.columns) - {"run_id"}
            if overlap:
                df = df.drop(columns=list(overlap))
            base = base.merge(df, on="run_id", how="left")

    return base


def _ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the canonical columns the pipeline expects exist.

    The pipeline requires at minimum: run_id, pass_fail.
    Other columns are optional and the pipeline handles their absence.
    """
    if "run_id" not in df.columns:
        df["run_id"] = [f"RUN-{i:06d}" for i in range(1, len(df) + 1)]

    if "pass_fail" not in df.columns:
        # Check for verdict or status columns
        for col in df.columns:
            if col.lower() in ("verdict", "status", "result", "outcome"):
                df["pass_fail"] = _normalise_outcome(df[col])
                break
        else:
            df["pass_fail"] = "pass"  # Default if no outcome info

    # Ensure pass_fail is normalised
    df["pass_fail"] = df["pass_fail"].fillna("pass").astype(str).str.lower()
    df["pass_fail"] = df["pass_fail"].map(
        lambda v: "fail" if v in ("fail", "failed", "error", "failure", "0", "false")
        else "pass"
    )

    # Fill common expected columns with defaults if missing
    if "test_name" not in df.columns:
        df["test_name"] = "unknown_test"

    if "primary_error_tag" not in df.columns:
        df["primary_error_tag"] = df["pass_fail"].map(
            lambda v: "NONE" if v == "pass" else "UNKNOWN_ERROR"
        )

    if "trace_fingerprint" not in df.columns:
        df["trace_fingerprint"] = df["pass_fail"].map(
            lambda v: "CLEAN" if v == "pass" else "UNKNOWN"
        )

    if "error_trace" not in df.columns:
        df["error_trace"] = ""

    if "distinct_error_tags" not in df.columns:
        df["distinct_error_tags"] = (df["primary_error_tag"] != "NONE").astype(int)

    if "verdict" not in df.columns:
        df["verdict"] = df["pass_fail"].map(
            lambda v: "FAILED" if v == "fail" else "PASSED"
        )

    return df


def _build_errors_from_log(
    log_errors: pd.DataFrame, csv_runs: pd.DataFrame
) -> pd.DataFrame:
    """Filter log errors to only include runs present in the CSV dataset."""
    if log_errors.empty or csv_runs.empty:
        return log_errors
    if "run_id" in log_errors.columns and "run_id" in csv_runs.columns:
        shared_ids = set(csv_runs["run_id"]) & set(log_errors["run_id"])
        if shared_ids:
            return log_errors[log_errors["run_id"].isin(shared_ids)]
    return log_errors


def _build_stats(
    groups: Dict[str, List[str]],
    csv_data: Dict[str, pd.DataFrame],
    waveform_info: Dict[str, Any],
    n_runs: int,
    mode: str,
) -> Dict[str, Any]:
    """Build comprehensive parse statistics."""
    stats: Dict[str, Any] = {
        "mode": mode,
        "files": sum(len(v) for v in groups.values()),
        "runs": n_runs,
        "log_files": len(groups["log"]),
        "csv_files": len(groups["csv"]),
        "waveform_files": len(groups["waveform"]),
        "data_sources": {},
    }

    # Track which data categories are available
    categories = {
        "configuration": "config" in csv_data,
        "randomization": "randomization" in csv_data,
        "transactions": "transactions" in csv_data,
        "telemetry": "telemetry" in csv_data,
        "outcomes": "outcomes" in csv_data,
        "registers": "registers" in csv_data,
        "uvm_log": len(groups["log"]) > 0,
        "waveforms": waveform_info.get("available", False),
    }
    stats["data_sources"] = categories

    # Error info for failed CSV parses
    errors = {k: v for k, v in csv_data.items() if isinstance(v, str)}
    if errors:
        stats["parse_errors"] = errors

    return stats


def parse_files_multi(
    paths: List[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
    """Alias for parse_upload that returns (runs, errors, stats, meta)."""
    runs_df, errors_df, stats = parse_upload(paths)
    meta = {
        "file_count": len(paths),
        "mode": stats.get("mode", "legacy"),
        "data_sources": stats.get("data_sources", {}),
    }
    return runs_df, errors_df, stats, meta


def parse_upload(
    paths: List[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Unified entry point: parse any combination of uploaded files.

    Returns (runs_df, errors_df, stats_dict) matching the parse_files()
    signature so the backend can use either interchangeably.
    """
    groups = _classify_files(paths)
    mode = _detect_mode(groups)
    waveform_info = classify_waveforms(groups["waveform"])

    if mode == "legacy":
        # Pure UVM log mode — use existing parser
        runs_df, errors_df, parse_stats = parse_log_files(groups["log"])
        stats = parse_stats.as_dict()
        stats["mode"] = "legacy"
        stats["data_sources"] = {
            "configuration": True,  # extracted from log
            "randomization": False,
            "transactions": False,
            "telemetry": False,
            "outcomes": True,  # extracted from log
            "registers": False,
            "uvm_log": True,
            "waveforms": waveform_info.get("available", False),
        }
        if waveform_info.get("available"):
            stats["waveform_info"] = waveform_info
        return runs_df, errors_df, stats

    # Multi-file mode
    csv_data = parse_csvs(groups["csv"])

    # Parse UVM logs if present (for error traces, assertions, etc.)
    log_runs = pd.DataFrame()
    log_errors = pd.DataFrame(
        columns=["run_id", "severity", "time_ns", "component", "tag",
                 "message", "fingerprint"]
    )
    log_stats = ParseStats()

    if groups["log"]:
        log_runs, log_errors, log_stats = parse_log_files(groups["log"])

    # Merge CSV data into a single run-level DataFrame
    csv_merged = _merge_csv_tables(csv_data)

    if csv_merged.empty and not log_runs.empty:
        # Only UVM log data available despite multi mode
        runs_df = log_runs
    elif not csv_merged.empty and log_runs.empty:
        # Only CSV data
        runs_df = csv_merged
    elif not csv_merged.empty and not log_runs.empty:
        # Both CSV and log data — merge them
        # The CSV data is the primary source; enrich with log data
        # Get log-derived columns that aren't already in CSV
        log_only_cols = [c for c in log_runs.columns
                         if c not in csv_merged.columns and c != "run_id"]
        if log_only_cols and "run_id" in log_runs.columns:
            log_extra = log_runs[["run_id"] + log_only_cols]
            runs_df = csv_merged.merge(log_extra, on="run_id", how="left")
        else:
            runs_df = csv_merged

        # Update error data with log-derived info
        if not log_errors.empty:
            log_errors = _build_errors_from_log(log_errors, runs_df)
            # Enrich runs with log-derived error info where available
            if "primary_error_tag" in log_runs.columns:
                log_etag = log_runs[["run_id", "primary_error_tag",
                                     "trace_fingerprint", "error_trace",
                                     "distinct_error_tags"]].copy()
                # Only fill where CSV doesn't already have this info
                for col in ["primary_error_tag", "trace_fingerprint",
                            "error_trace", "distinct_error_tags"]:
                    if col not in runs_df.columns:
                        if col in log_etag.columns:
                            runs_df = runs_df.merge(
                                log_etag[["run_id", col]],
                                on="run_id", how="left"
                            )
    else:
        runs_df = pd.DataFrame()

    if runs_df.empty:
        return runs_df, log_errors, _build_stats(
            groups, csv_data, waveform_info, 0, mode)

    # Ensure required columns exist
    runs_df = _ensure_required_columns(runs_df)

    # Build stats
    stats = _build_stats(
        groups, csv_data, waveform_info, len(runs_df), mode)
    stats.update({
        "lines": log_stats.lines,
        "error_lines": log_stats.error_lines,
        "malformed_blocks": log_stats.malformed_blocks,
        "unparsed_lines": log_stats.unparsed_lines,
    })
    if waveform_info.get("available"):
        stats["waveform_info"] = waveform_info

    return runs_df, log_errors, stats
