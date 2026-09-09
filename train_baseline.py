#!/usr/bin/env python3
"""
Baseline model training for Configuration Intelligence.

Trains a configurable classifier on preprocessed test-run data, evaluates on
a held-out test set, reports standard classification metrics, and computes
human-readable feature importances (aggregated from one-hot dummies back to
parent features via the lineage map).

Outputs:
  * Console report with all metrics and top feature importances
  * synthetic_test_runs_with_predictions.csv -- original data + failure_probability
  * model_results.json -- metrics + feature importances for downstream scripts

Usage
-----
    python train_baseline.py [--input FILE] [--model MODEL] [--seed N]

Supported models (via --model flag):
    random_forest       (default)  RandomForestClassifier
    gradient_boosting              HistGradientBoostingClassifier
    logistic_regression            LogisticRegression
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from preprocess import preprocess, PreprocessResult


# =========================================================================
# Model Factory
# =========================================================================

def _build_model(model_name: str, seed: int) -> Any:
    """Return a scikit-learn classifier by name."""
    models = {
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "gradient_boosting": lambda: HistGradientBoostingClassifier(
            max_iter=200,
            max_depth=8,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=seed,
        ),
        "logistic_regression": lambda: LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=seed,
        ),
    }
    if model_name not in models:
        raise ValueError(
            f"Unknown model '{model_name}'.  "
            f"Choose from: {', '.join(models.keys())}"
        )
    return models[model_name]()


# =========================================================================
# Feature Importance Aggregation (one-hot -> parent features)
# =========================================================================

def aggregate_importances(
    model: Any,
    feature_names: List[str],
    lineage: Dict[str, List[str]],
    model_name: str,
) -> List[Dict[str, Any]]:
    """Map per-dummy importances back to parent features, sum within groups.

    Returns a sorted list of {feature, importance, rank} dicts.
    """
    # Extract raw feature importances
    if hasattr(model, "feature_importances_"):
        raw = dict(zip(feature_names, model.feature_importances_))
    elif hasattr(model, "coef_"):
        # For logistic regression, use absolute coefficient values
        raw = dict(zip(feature_names, np.abs(model.coef_[0])))
    else:
        return []

    # Aggregate by parent feature
    parent_imp: Dict[str, float] = {}
    for parent, children in lineage.items():
        total = sum(raw.get(c, 0.0) for c in children)
        parent_imp[parent] = total

    # Sort descending by importance
    sorted_features = sorted(parent_imp.items(), key=lambda x: -x[1])

    # Normalize to sum to 1.0
    total_imp = sum(v for _, v in sorted_features)
    if total_imp > 0:
        sorted_features = [(f, v / total_imp) for f, v in sorted_features]

    return [
        {"feature": f, "importance": round(imp, 4), "rank": i + 1}
        for i, (f, imp) in enumerate(sorted_features)
    ]


# =========================================================================
# Evaluation
# =========================================================================

def evaluate(
    model: Any,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
) -> Dict[str, float]:
    """Compute full metric set on the test partition."""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision_fail": round(precision_score(y_test, y_pred, pos_label=1, zero_division=0), 4),
        "recall_fail": round(recall_score(y_test, y_pred, pos_label=1, zero_division=0), 4),
        "f1_fail": round(f1_score(y_test, y_pred, pos_label=1, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
        "pr_auc": round(average_precision_score(y_test, y_proba), 4),
    }
    return metrics


# =========================================================================
# Per-Row Failure Probability
# =========================================================================

def predict_failure_probabilities(
    model: Any,
    X_full: pd.DataFrame,
    original_df: pd.DataFrame,
    output_path: str,
) -> pd.DataFrame:
    """Add failure_probability column to original data and save CSV."""
    proba = model.predict_proba(X_full)[:, 1]
    enriched = original_df.copy()
    enriched["failure_probability"] = np.round(proba, 4)
    enriched.to_csv(output_path, index=False)
    return enriched


# =========================================================================
# Reporting (ASCII-only for Windows cp1252)
# =========================================================================

def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_report(
    model_name: str,
    metrics: Dict[str, float],
    importances: List[Dict[str, Any]],
    y_test: np.ndarray,
    y_pred: np.ndarray,
) -> None:
    """Print evaluation report to console."""
    _print_section(f"Model: {model_name}")
    print(f"\n  {'Metric':<22s} {'Value':>8s}")
    print(f"  {'-' * 22} {'-' * 8}")
    for k, v in metrics.items():
        print(f"  {k:<22s} {v:>8.4f}")

    _print_section("Classification Report (Fail=1, Pass=0)")
    report = classification_report(y_test, y_pred, target_names=["pass", "fail"])
    for line in report.split("\n"):
        print(f"  {line}")

    _print_section("Feature Importances (aggregated to parent features)")
    print(f"\n  {'Rank':<6s} {'Feature':<22s} {'Importance':>12s}")
    print(f"  {'-' * 6} {'-' * 22} {'-' * 12}")
    for entry in importances:
        bar = "#" * max(1, int(entry["importance"] * 50))
        print(f"  {entry['rank']:<6d} {entry['feature']:<22s} {entry['importance']:>12.4f}  {bar}")


# =========================================================================
# Main Training Pipeline
# =========================================================================

def train(
    csv_path: str,
    model_name: str = "random_forest",
    seed: int = 42,
    test_size: float = 0.20,
    output_predictions: str = "synthetic_test_runs_with_predictions.csv",
    output_results: str = "model_results.json",
) -> Tuple[Any, Dict]:
    """Full training pipeline: preprocess -> train -> evaluate -> export."""

    # 1. Preprocess
    result = preprocess(csv_path, test_size=test_size, seed=seed)
    _print_section("Preprocessing Complete")
    print(f"  Train: {len(result.X_train):,} rows  |  Test: {len(result.X_test):,} rows")
    print(f"  Features: {len(result.feature_names)} encoded columns")
    print(f"  Failure rate: {result.y_full.mean():.1%}")

    # 2. Train
    model = _build_model(model_name, seed)
    print(f"\n  Training {model_name} ...")
    model.fit(result.X_train, result.y_train)
    print("  Training complete.")

    # 3. Evaluate
    metrics = evaluate(model, result.X_test, result.y_test)
    y_pred = model.predict(result.X_test)

    # 4. Feature importances
    importances = aggregate_importances(
        model, result.feature_names, result.lineage, model_name
    )

    # 5. Print report
    print_report(model_name, metrics, importances, result.y_test, y_pred)

    # 6. Per-row predictions
    enriched = predict_failure_probabilities(
        model, result.X_full, result.original_df, output_predictions
    )
    _print_section("Per-Row Predictions")
    top_risk = enriched.nlargest(5, "failure_probability")
    print(f"\n  Top 5 highest-risk runs:")
    print(f"  {'run_id':<14s} {'pass_fail':<10s} {'failure_prob':>12s}")
    print(f"  {'-' * 14} {'-' * 10} {'-' * 12}")
    for _, row in top_risk.iterrows():
        rid = str(row.get("run_id", "N/A"))
        pf = str(row.get("pass_fail", "N/A"))
        fp = row["failure_probability"]
        print(f"  {rid:<14s} {pf:<10s} {fp:>12.4f}")
    print(f"\n  -> {output_predictions}  ({len(enriched):,} rows)")

    # 7. Export results JSON (for interaction_analysis.py and grading)
    results_payload = {
        "model": model_name,
        "seed": seed,
        "metrics": metrics,
        "feature_importances": importances,
        "lineage": result.lineage,
        "roles": result.roles,
        "n_train": len(result.X_train),
        "n_test": len(result.X_test),
    }
    with open(output_results, "w") as fh:
        json.dump(results_payload, fh, indent=2)
    print(f"  -> {output_results} written")

    print("\nDone.")
    return model, results_payload


# =========================================================================
# CLI
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a baseline classifier on test-run data."
    )
    parser.add_argument(
        "--input", default="synthetic_test_runs.csv",
        help="Input CSV (default: synthetic_test_runs.csv)",
    )
    parser.add_argument(
        "--model", default="random_forest",
        choices=["random_forest", "gradient_boosting", "logistic_regression"],
        help="Classifier to train (default: random_forest)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed (default: 42)",
    )
    parser.add_argument(
        "--test-size", type=float, default=0.20,
        help="Test split fraction (default: 0.20)",
    )
    parser.add_argument(
        "--output-predictions",
        default="synthetic_test_runs_with_predictions.csv",
        help="Output CSV with failure_probability column",
    )
    parser.add_argument(
        "--output-results", default="model_results.json",
        help="Output JSON with metrics and importances",
    )
    args = parser.parse_args()

    train(
        csv_path=args.input,
        model_name=args.model,
        seed=args.seed,
        test_size=args.test_size,
        output_predictions=args.output_predictions,
        output_results=args.output_results,
    )


if __name__ == "__main__":
    main()
