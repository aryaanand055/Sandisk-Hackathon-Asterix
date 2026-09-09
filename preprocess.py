#!/usr/bin/env python3
"""
Application-agnostic preprocessing for Configuration Intelligence.

Auto-detects column roles (identifier, outcome, categorical, numeric) from
a raw CSV.  Produces one-hot encoded feature matrices, train/test splits,
and a lineage map that lets downstream code reverse dummy columns back to
their original parent features.

No column names are hardcoded -- the pipeline works on any CSV with the
same shape convention:
  * exactly one binary pass/fail-style column (target)
  * zero or more identifier columns (near-100% unique values)
  * the rest are predictors

Usage
-----
    python preprocess.py [--input FILE] [--test-size FRAC] [--seed N]

Library mode
------------
    from preprocess import preprocess
    result = preprocess("synthetic_test_runs.csv")
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


# =========================================================================
# Column-Role Detection (fully generic)
# =========================================================================

# Patterns that suggest identifier columns
_ID_PATTERNS = re.compile(
    r"^(run_id|id|uuid|guid|test_id|sample_id|row_id|index)$",
    re.IGNORECASE,
)


def _is_identifier(series: pd.Series) -> bool:
    """Heuristic: column is an identifier if nearly all values are unique
    or the name matches common ID patterns."""
    name = str(series.name).lower()
    if _ID_PATTERNS.match(name):
        return True
    # >95% unique values in a string/object column is a strong signal
    if series.dtype == object and series.nunique() / max(len(series), 1) > 0.95:
        return True
    return False


def _is_binary_target(series: pd.Series) -> bool:
    """Heuristic: column is a pass/fail-style binary target if it has
    exactly 2 unique values and one of them maps to a 'fail' concept."""
    if series.nunique() != 2:
        return False
    vals = set(str(v).lower().strip() for v in series.unique())
    # Common binary-target value sets
    fail_signals = {"fail", "failed", "0", "false", "no", "error", "bad"}
    return bool(vals & fail_signals)


def _is_outcome_column(name: str, target_name: str) -> bool:
    """Heuristic: columns that are outcomes (derived from the test result)
    rather than input predictors.  These must be excluded from features
    to avoid target leakage."""
    n = name.lower()
    # The target itself
    if n == target_name.lower():
        return True
    # Common outcome/result columns
    outcome_keywords = [
        "execution_time", "exec_time", "runtime", "duration",
        "throughput", "bandwidth", "latency", "iops",
        "error_type", "error_code", "error_msg", "exit_code",
        "result", "status", "score", "metric",
    ]
    return any(kw in n for kw in outcome_keywords)


def detect_column_roles(
    df: pd.DataFrame,
) -> Dict[str, List[str]]:
    """Classify every column into a role.

    Returns dict with keys:
        identifier  -- columns to drop (IDs)
        target      -- the single binary target column
        outcome     -- other outcome columns to drop (leakage prevention)
        categorical -- categorical predictor columns
        numeric     -- numeric predictor columns
    """
    roles: Dict[str, List[str]] = {
        "identifier": [],
        "target": [],
        "outcome": [],
        "categorical": [],
        "numeric": [],
    }

    # Pass 1: find identifiers
    for col in df.columns:
        if _is_identifier(df[col]):
            roles["identifier"].append(col)

    # Pass 2: find the binary target
    candidates = [
        c for c in df.columns if c not in roles["identifier"]
    ]
    target_found = None
    for col in candidates:
        if _is_binary_target(df[col]):
            target_found = col
            roles["target"].append(col)
            break  # take the first match
    if target_found is None:
        raise ValueError(
            "Could not auto-detect a binary target column.  "
            "Ensure one column has exactly 2 unique values with "
            "one representing 'fail'."
        )

    # Pass 3: classify remaining columns
    for col in candidates:
        if col == target_found:
            continue
        if _is_outcome_column(col, target_found):
            roles["outcome"].append(col)
            continue
        # Predictor: categorical vs numeric
        if df[col].dtype == object or df[col].dtype.name == "category":
            roles["categorical"].append(col)
        elif df[col].nunique() <= 10 and df[col].dtype in ("int64", "int32"):
            # Low-cardinality integers treated as categorical (e.g. memory_size)
            # Only if they look like discrete levels, not a range
            roles["categorical"].append(col)
        else:
            roles["numeric"].append(col)

    return roles


# =========================================================================
# Encoding + Lineage Tracking
# =========================================================================

def encode_features(
    df: pd.DataFrame,
    roles: Dict[str, List[str]],
) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    """One-hot encode categoricals, keep numerics, build lineage map.

    Returns:
        features  -- DataFrame of encoded predictor columns
        lineage   -- {parent_feature: [encoded_col_1, ...]}
    """
    lineage: Dict[str, List[str]] = {}
    parts: List[pd.DataFrame] = []

    # Numeric predictors pass through unchanged
    for col in roles["numeric"]:
        parts.append(df[[col]].copy())
        lineage[col] = [col]

    # Categorical predictors get one-hot dummies
    for col in roles["categorical"]:
        dummies = pd.get_dummies(df[col], prefix=col, dtype=float)
        parts.append(dummies)
        lineage[col] = list(dummies.columns)

    features = pd.concat(parts, axis=1) if parts else pd.DataFrame()
    return features, lineage


def encode_target(
    series: pd.Series,
) -> Tuple[np.ndarray, Dict[str, int]]:
    """Encode binary target: 'fail'->1, 'pass'->0 (generic)."""
    vals = sorted(series.unique(), key=str)
    # Identify which value is the 'positive' (failure) class
    mapping = {}
    for v in vals:
        s = str(v).lower().strip()
        if s in ("fail", "failed", "0", "false", "no", "error", "bad"):
            mapping[v] = 1
        else:
            mapping[v] = 0
    encoded = series.map(mapping).values.astype(int)
    return encoded, mapping


# =========================================================================
# Main Preprocessing Pipeline
# =========================================================================

class PreprocessResult:
    """Container for preprocessing outputs."""
    def __init__(
        self,
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: np.ndarray,
        y_test: np.ndarray,
        lineage: Dict[str, List[str]],
        roles: Dict[str, List[str]],
        target_mapping: Dict[str, int],
        feature_names: List[str],
        original_df: pd.DataFrame,
        X_full: pd.DataFrame,
        y_full: np.ndarray,
    ):
        self.X_train = X_train
        self.X_test = X_test
        self.y_train = y_train
        self.y_test = y_test
        self.lineage = lineage
        self.roles = roles
        self.target_mapping = target_mapping
        self.feature_names = feature_names
        self.original_df = original_df
        self.X_full = X_full
        self.y_full = y_full


def preprocess(
    csv_path: str,
    test_size: float = 0.20,
    seed: int = 42,
) -> PreprocessResult:
    """Full preprocessing pipeline.

    1. Load CSV
    2. Auto-detect column roles
    3. Encode features (one-hot) + target (binary)
    4. Stratified train/test split
    """
    df = pd.read_csv(csv_path)
    roles = detect_column_roles(df)

    # Encode
    X, lineage = encode_features(df, roles)
    y, target_map = encode_target(df[roles["target"][0]])

    # Stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=seed,
        stratify=y,
    )

    return PreprocessResult(
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        lineage=lineage,
        roles=roles,
        target_mapping=target_map,
        feature_names=list(X.columns),
        original_df=df,
        X_full=X,
        y_full=y,
    )


# =========================================================================
# CLI
# =========================================================================

def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-detect columns and preprocess test-run CSV."
    )
    parser.add_argument(
        "--input", default="synthetic_test_runs.csv",
        help="Input CSV path (default: synthetic_test_runs.csv)",
    )
    parser.add_argument(
        "--test-size", type=float, default=0.20,
        help="Test split fraction (default: 0.20)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed (default: 42)",
    )
    parser.add_argument(
        "--output-lineage", default="feature_lineage.json",
        help="Output path for lineage map JSON (default: feature_lineage.json)",
    )
    args = parser.parse_args()

    result = preprocess(args.input, args.test_size, args.seed)

    # ── Report ────────────────────────────────────────────────────────────
    _print_section("Column Role Detection")
    for role, cols in result.roles.items():
        print(f"  {role:14s}: {', '.join(cols) if cols else '(none)'}")

    _print_section("Feature Encoding")
    n_cat = sum(1 for c in result.roles["categorical"])
    n_num = len(result.roles["numeric"])
    n_enc = len(result.feature_names)
    print(f"  Categorical features : {n_cat}")
    print(f"  Numeric features     : {n_num}")
    print(f"  Encoded features     : {n_enc} (after one-hot)")

    _print_section("Target Encoding")
    for val, code in result.target_mapping.items():
        print(f"  '{val}' -> {code}")
    print(f"  Class distribution   : "
          f"fail={result.y_full.sum()} / pass={len(result.y_full) - result.y_full.sum()} "
          f"({result.y_full.mean():.1%} failure rate)")

    _print_section("Train / Test Split")
    print(f"  Train size : {len(result.X_train):,} rows")
    print(f"  Test size  : {len(result.X_test):,} rows")
    print(f"  Train fail%: {result.y_train.mean():.1%}")
    print(f"  Test fail% : {result.y_test.mean():.1%}")

    _print_section("Feature Lineage (parent -> encoded columns)")
    for parent, children in result.lineage.items():
        if len(children) == 1 and children[0] == parent:
            print(f"  {parent} (numeric, passthrough)")
        else:
            print(f"  {parent} -> {', '.join(children)}")

    # Write lineage JSON
    with open(args.output_lineage, "w") as fh:
        json.dump(result.lineage, fh, indent=2)
    print(f"\n  -> {args.output_lineage} written")

    print("\nDone.")


if __name__ == "__main__":
    main()
