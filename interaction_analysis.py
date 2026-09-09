#!/usr/bin/env python3
"""
Interaction analysis for Configuration Intelligence.

Given model results (feature importances + lineage) and the original dataset,
discovers pairwise and 3-way feature combinations that are associated with
elevated failure rates.  Reports top risky combinations with empirical lift
metrics.

This script is application-agnostic: it reads column roles and feature
importances from the model_results.json produced by train_baseline.py.

Approach
--------
1. Select the top-K most important *parent* features from the model.
2. For each pairwise and 3-way combination of these features, compute:
   - The empirical failure rate within that subgroup.
   - The "lift" vs the overall baseline failure rate.
   - The support (number of rows in that subgroup).
3. Filter out low-support combinations (min 10 rows).
4. Rank by lift and report the top interactions.

Usage
-----
    python interaction_analysis.py [--input FILE] [--results FILE] [--top-k N]

Outputs:
    * Console report of top risky combinations
    * discovered_interactions.json
"""

import argparse
import itertools
import json
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


# =========================================================================
# Discretisation Helpers
# =========================================================================

def _discretise_column(
    series: pd.Series, n_bins: int = 3
) -> pd.Series:
    """Discretise a numeric column into labelled bins for interaction analysis.

    For integer columns with few unique values (<=n_bins), keep as-is.
    For continuous columns, use quantile-based binning.
    """
    if series.nunique() <= n_bins:
        return series.astype(str)

    try:
        binned = pd.qcut(series, q=n_bins, duplicates="drop")
        # Produce human-readable labels
        labels = []
        for interval in binned.cat.categories:
            labels.append(f"{series.name}[{interval.left:.1f}-{interval.right:.1f}]")
        mapping = dict(zip(binned.cat.categories, labels))
        return binned.map(mapping).astype(str)
    except (ValueError, TypeError):
        return series.astype(str)


# =========================================================================
# Interaction Discovery
# =========================================================================

def discover_interactions(
    csv_path: str,
    results_path: str,
    top_k: int = 5,
    min_support: int = 10,
    max_order: int = 3,
) -> List[Dict[str, Any]]:
    """Discover high-risk feature combinations from data.

    Returns a list of interaction dicts sorted by lift (descending).
    """
    # Load model results
    with open(results_path, "r") as fh:
        results = json.load(fh)

    importances = results["feature_importances"]
    roles = results["roles"]
    lineage = results["lineage"]

    # Get the top-K parent features by importance
    top_features = [
        entry["feature"] for entry in importances[:top_k]
    ]

    # Load the original dataset
    df = pd.read_csv(csv_path)

    # Identify target column and encode
    target_col = roles["target"][0]
    target_vals = df[target_col].astype(str).str.lower().str.strip()
    fail_labels = {"fail", "failed", "0", "false", "no", "error", "bad"}
    is_fail = target_vals.isin(fail_labels).astype(int)
    baseline_fail_rate = is_fail.mean()

    # Prepare feature columns for grouping
    # For categoricals: use raw values
    # For numerics: discretise into bins
    analysis_cols: Dict[str, pd.Series] = {}
    for feat in top_features:
        if feat not in df.columns:
            continue
        col = df[feat]
        if col.dtype == object:
            analysis_cols[feat] = col.astype(str)
        else:
            analysis_cols[feat] = _discretise_column(col, n_bins=3)

    # Enumerate pairwise and 3-way combinations
    interactions: List[Dict[str, Any]] = []
    feature_list = list(analysis_cols.keys())

    for order in range(2, min(max_order + 1, len(feature_list) + 1)):
        for combo in itertools.combinations(feature_list, order):
            # Build group keys
            group_df = pd.DataFrame({f: analysis_cols[f] for f in combo})
            group_df["_fail"] = is_fail.values

            # Group by combination and compute failure rates
            grouped = group_df.groupby(list(combo))["_fail"]
            stats = grouped.agg(["mean", "count"]).reset_index()
            stats.columns = list(combo) + ["fail_rate", "support"]

            # Filter by minimum support
            stats = stats[stats["support"] >= min_support]

            for _, row in stats.iterrows():
                fail_rate = row["fail_rate"]
                support = int(row["support"])
                lift = fail_rate / baseline_fail_rate if baseline_fail_rate > 0 else 0

                if lift <= 1.2:  # Only report meaningful elevations
                    continue

                # Build condition description
                conditions = []
                for f in combo:
                    conditions.append({
                        "feature": f,
                        "value": str(row[f]),
                    })

                interactions.append({
                    "features": list(combo),
                    "conditions": conditions,
                    "fail_rate": round(fail_rate, 4),
                    "baseline_fail_rate": round(baseline_fail_rate, 4),
                    "lift": round(lift, 2),
                    "support": support,
                    "order": order,
                })

    # Sort by lift descending, then support descending
    interactions.sort(key=lambda x: (-x["lift"], -x["support"]))

    return interactions


# =========================================================================
# Reporting (ASCII-only for Windows cp1252)
# =========================================================================

def _print_section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_interaction_report(
    interactions: List[Dict[str, Any]],
    n_display: int = 15,
) -> None:
    """Print top risky combinations to console."""
    _print_section("Top Risky Configuration Combinations")

    if not interactions:
        print("  No significant interactions found.")
        return

    # Summary by order
    pairwise = [i for i in interactions if i["order"] == 2]
    threeway = [i for i in interactions if i["order"] == 3]
    print(f"\n  Found {len(pairwise)} pairwise + {len(threeway)} 3-way "
          f"interactions above 1.2x lift threshold")
    print(f"  Baseline failure rate: {interactions[0]['baseline_fail_rate']:.1%}")

    # Top interactions table
    _print_section(f"Top {min(n_display, len(interactions))} Interactions (by lift)")
    print(f"\n  {'#':<4s} {'Conditions':<48s} {'Fail%':>7s} {'Lift':>6s} {'N':>6s}")
    print(f"  {'-' * 4} {'-' * 48} {'-' * 7} {'-' * 6} {'-' * 6}")

    for i, entry in enumerate(interactions[:n_display]):
        cond_str = " AND ".join(
            f"{c['feature']}={c['value']}" for c in entry["conditions"]
        )
        if len(cond_str) > 47:
            cond_str = cond_str[:44] + "..."
        print(
            f"  {i + 1:<4d} {cond_str:<48s} "
            f"{entry['fail_rate']:>6.1%} {entry['lift']:>5.1f}x "
            f"{entry['support']:>5d}"
        )

    # Feature frequency analysis
    _print_section("Feature Frequency in Top Interactions")
    feat_count: Dict[str, int] = {}
    for entry in interactions[:min(30, len(interactions))]:
        for f in entry["features"]:
            feat_count[f] = feat_count.get(f, 0) + 1
    sorted_feats = sorted(feat_count.items(), key=lambda x: -x[1])
    print(f"\n  {'Feature':<22s} {'Appearances':>12s}")
    print(f"  {'-' * 22} {'-' * 12}")
    for feat, count in sorted_feats:
        print(f"  {feat:<22s} {count:>12d}")


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover high-risk feature interactions."
    )
    parser.add_argument(
        "--input", default="synthetic_test_runs.csv",
        help="Input CSV path",
    )
    parser.add_argument(
        "--results", default="model_results.json",
        help="Model results JSON from train_baseline.py",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Number of top features to include in interaction search (default: 5)",
    )
    parser.add_argument(
        "--min-support", type=int, default=10,
        help="Minimum subgroup size (default: 10)",
    )
    parser.add_argument(
        "--max-order", type=int, default=3,
        help="Maximum interaction order (default: 3, i.e. up to 3-way)",
    )
    parser.add_argument(
        "--output", default="discovered_interactions.json",
        help="Output JSON for discovered interactions",
    )
    args = parser.parse_args()

    interactions = discover_interactions(
        csv_path=args.input,
        results_path=args.results,
        top_k=args.top_k,
        min_support=args.min_support,
        max_order=args.max_order,
    )

    print_interaction_report(interactions)

    # Export
    with open(args.output, "w") as fh:
        json.dump({"interactions": interactions}, fh, indent=2)
    print(f"\n  -> {args.output}  ({len(interactions)} interactions)")
    print("\nDone.")


if __name__ == "__main__":
    main()
