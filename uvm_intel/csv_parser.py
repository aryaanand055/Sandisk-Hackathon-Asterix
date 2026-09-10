#!/usr/bin/env python3
"""
CSV file parser for multi-file verification datasets.

Detects file categories by filename and column patterns, normalizes column
names, and returns typed DataFrames for each category.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ── Column-name aliases ────────────────────────────────────────────────────
# Maps common variations to canonical internal names.

_ID_ALIASES = {
    "run_id", "runid", "run_id", "simulation_id", "sim_id", "test_id",
    "testid", "id",
}

_OUTCOME_ALIASES = {
    "status": "pass_fail",
    "result": "pass_fail",
    "outcome": "pass_fail",
    "pass_fail": "pass_fail",
    "passfail": "pass_fail",
    "pass/fail": "pass_fail",
    "verdict": "pass_fail",
}

_PASS_VALUES = {"pass", "passed", "ok", "success", "1", "true", "yes"}
_FAIL_VALUES = {"fail", "failed", "error", "failure", "0", "false", "no"}


def _normalise_col(name: str) -> str:
    """Lowercase, strip whitespace, replace spaces/hyphens with underscores."""
    return re.sub(r"[\s\-]+", "_", name.strip().lower())


def _find_id_col(cols: List[str]) -> Optional[str]:
    """Find the best candidate for a run-identifier column."""
    normed = {_normalise_col(c): c for c in cols}
    for alias in ("run_id", "runid", "simulation_id", "sim_id", "test_id", "testid"):
        if alias in normed:
            return normed[alias]
    # Fallback: first column containing "id"
    for n, orig in normed.items():
        if "id" in n and n != "id":
            return orig
    if "id" in normed:
        return normed["id"]
    return None


def _normalise_outcome(series: pd.Series) -> pd.Series:
    """Map various pass/fail representations to canonical 'pass'/'fail'."""
    def _map(v):
        s = str(v).strip().lower()
        if s in _PASS_VALUES:
            return "pass"
        if s in _FAIL_VALUES:
            return "fail"
        return s
    return series.map(_map)


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names while preserving originals for custom fields."""
    rename = {}
    for col in df.columns:
        normed = _normalise_col(col)
        if normed in _ID_ALIASES:
            rename[col] = "run_id"
        elif normed in _OUTCOME_ALIASES:
            rename[col] = _OUTCOME_ALIASES[normed]
        elif normed != col:
            rename[col] = normed
    df = df.rename(columns=rename)
    # Deduplicate: if multiple columns mapped to the same name, keep first
    df = df.loc[:, ~df.columns.duplicated()]
    return df


# ── File-category detection ────────────────────────────────────────────────

# Canonical names → typical filename patterns
_CATEGORY_PATTERNS = {
    "config":        re.compile(r"config", re.I),
    "randomization": re.compile(r"random", re.I),
    "transactions":  re.compile(r"transact", re.I),
    "telemetry":     re.compile(r"telemetr", re.I),
    "outcomes":      re.compile(r"outcome|result", re.I),
    "registers":     re.compile(r"register", re.I),
}


def classify_csv(path: str) -> str:
    """Guess the category of a CSV file from its filename."""
    base = os.path.basename(path).lower()
    for cat, pat in _CATEGORY_PATTERNS.items():
        if pat.search(base):
            return cat
    return "unknown"


def read_csv_safe(path: str) -> pd.DataFrame:
    """Read a CSV with reasonable defaults, handling encoding issues."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, encoding=enc, low_memory=False)
            return _normalise_columns(df)
        except UnicodeDecodeError:
            continue
    # Last resort
    df = pd.read_csv(path, encoding="utf-8", errors="replace", low_memory=False)
    return _normalise_columns(df)


# ── Per-category parsers ───────────────────────────────────────────────────

def parse_config(path: str) -> pd.DataFrame:
    """Parse configuration CSV → one row per run."""
    df = read_csv_safe(path)
    if "run_id" not in df.columns:
        id_col = _find_id_col(list(df.columns))
        if id_col:
            df = df.rename(columns={id_col: "run_id"})
    return df


def parse_randomization(path: str) -> pd.DataFrame:
    """Parse randomization CSV → one row per run."""
    df = read_csv_safe(path)
    if "run_id" not in df.columns:
        id_col = _find_id_col(list(df.columns))
        if id_col:
            df = df.rename(columns={id_col: "run_id"})
    return df


def parse_transactions(path: str) -> pd.DataFrame:
    """Parse transactions CSV → many rows per run; aggregate per run."""
    df = read_csv_safe(path)
    if "run_id" not in df.columns:
        id_col = _find_id_col(list(df.columns))
        if id_col:
            df = df.rename(columns={id_col: "run_id"})

    if "run_id" not in df.columns:
        return pd.DataFrame()

    # Aggregate transaction-level data to run-level summaries
    agg = {"run_id": "first"}
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    numeric_cols = [c for c in numeric_cols if c != "run_id"]

    for c in numeric_cols:
        # Generate meaningful per-run aggregates
        agg[c] = "mean"

    grouped = df.groupby("run_id", as_index=False).agg(
        n_transactions=("run_id", "size"),
        **{f"txn_{c}_mean": (c, "mean") for c in numeric_cols},
        **{f"txn_{c}_max": (c, "max") for c in numeric_cols[:5]},  # limit columns
    ).reset_index(drop=True) if numeric_cols else df.groupby("run_id", as_index=False).agg(
        n_transactions=("run_id", "size"),
    ).reset_index(drop=True)

    return grouped


def parse_telemetry(path: str) -> pd.DataFrame:
    """Parse telemetry CSV → one row per run or aggregate if multiple."""
    df = read_csv_safe(path)
    if "run_id" not in df.columns:
        id_col = _find_id_col(list(df.columns))
        if id_col:
            df = df.rename(columns={id_col: "run_id"})

    if "run_id" not in df.columns:
        return pd.DataFrame()

    # If already one row per run, return as-is
    if df["run_id"].nunique() == len(df):
        return df

    # Otherwise aggregate
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    numeric_cols = [c for c in numeric_cols if c != "run_id"]
    if numeric_cols:
        agg_dict = {c: "mean" for c in numeric_cols}
        return df.groupby("run_id", as_index=False).agg(**{
            c: ("run_id" if c == "run_id" else c, fn)
            for c, fn in agg_dict.items()
        })
    return df.drop_duplicates("run_id")


def parse_outcomes(path: str) -> pd.DataFrame:
    """Parse outcomes CSV → one row per run with pass/fail status."""
    df = read_csv_safe(path)
    if "run_id" not in df.columns:
        id_col = _find_id_col(list(df.columns))
        if id_col:
            df = df.rename(columns={id_col: "run_id"})

    # Normalise pass/fail column
    if "pass_fail" in df.columns:
        df["pass_fail"] = _normalise_outcome(df["pass_fail"])
    elif "verdict" in df.columns:
        df["pass_fail"] = _normalise_outcome(df["verdict"])

    return df


def parse_registers(path: str) -> pd.DataFrame:
    """Parse register/memory CSV → aggregate per run."""
    df = read_csv_safe(path)
    if "run_id" not in df.columns:
        id_col = _find_id_col(list(df.columns))
        if id_col:
            df = df.rename(columns={id_col: "run_id"})

    if "run_id" not in df.columns:
        return pd.DataFrame()

    # Aggregate register accesses per run
    grouped = df.groupby("run_id", as_index=False).agg(
        n_register_accesses=("run_id", "size"),
    )
    return grouped


# ── Public API ─────────────────────────────────────────────────────────────

PARSERS = {
    "config": parse_config,
    "randomization": parse_randomization,
    "transactions": parse_transactions,
    "telemetry": parse_telemetry,
    "outcomes": parse_outcomes,
    "registers": parse_registers,
}


def parse_csvs(paths: List[str]) -> Dict[str, pd.DataFrame]:
    """Parse a set of CSV files, auto-classifying each by filename.

    Returns a dict of category → DataFrame.
    """
    results: Dict[str, pd.DataFrame] = {}
    for path in paths:
        cat = classify_csv(path)
        if cat in PARSERS:
            try:
                df = PARSERS[cat](path)
                if not df.empty:
                    results[cat] = df
            except Exception as exc:
                results[f"{cat}_error"] = str(exc)
        else:
            # Unknown CSV - try generic read
            try:
                df = read_csv_safe(path)
                if "run_id" not in df.columns:
                    id_col = _find_id_col(list(df.columns))
                    if id_col:
                        df = df.rename(columns={id_col: "run_id"})
                results[f"custom_{os.path.basename(path)}"] = df
            except Exception:
                pass
    return results
