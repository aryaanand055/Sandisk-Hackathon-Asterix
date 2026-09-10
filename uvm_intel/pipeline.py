#!/usr/bin/env python3
"""
Analysis orchestrator.

Runs the whole chain - parse -> risk model + SHAP -> fingerprint clustering ->
Pareto -> config diff -> recommender - and returns one JSON-serialisable
payload for the dashboard.

Every stage is wrapped: if an optional stage fails, the rest of the report is
still delivered with an ``error`` field on that stage rather than a dead job.
"""

import time
import traceback
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from .config_diff import aggregate_delta, nearest_twin_diff
from .fingerprints import cluster_failures
from .log_parser import parse_files, parse_text
from .pareto import pareto_frontier
from .recommender import recommend
from .risk_model import risk_meter, select_features, train_risk_model


def _stage(name: str, fn: Callable, log: List[Dict]) -> Any:
    """Run one stage, timing it and capturing failures."""
    t0 = time.time()
    try:
        out = fn()
        log.append({"stage": name, "status": "ok",
                    "seconds": round(time.time() - t0, 2)})
        return out
    except Exception as exc:                       # noqa: BLE001
        log.append({"stage": name, "status": "failed",
                    "seconds": round(time.time() - t0, 2),
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=3)})
        return {"error": f"{type(exc).__name__}: {exc}"}


def summarize(runs: pd.DataFrame, errors: pd.DataFrame,
              parse_stats: Dict[str, int]) -> Dict[str, Any]:
    """Executive-summary block."""
    n = len(runs)
    n_fail = int((runs["pass_fail"] == "fail").sum())
    tags = runs.loc[runs["pass_fail"] == "fail", "primary_error_tag"]

    numeric_cols = [c for c in ("execution_time_ms", "throughput_mbps", "cycles")
                    if c in runs.columns]
    stats = {c: {
        "mean": round(float(runs[c].mean()), 2),
        "median": round(float(runs[c].median()), 2),
        "p95": round(float(runs[c].quantile(0.95)), 2),
        "min": round(float(runs[c].min()), 2),
        "max": round(float(runs[c].max()), 2),
    } for c in numeric_cols}

    by_tag_time = {}
    if "execution_time_ms" in runs.columns:
        g = runs.groupby("primary_error_tag")["execution_time_ms"].agg(
            ["count", "mean"])
        by_tag_time = {str(k): {"count": int(v["count"]),
                                "mean_execution_time_ms": round(float(v["mean"]), 2)}
                       for k, v in g.iterrows()}

    return {
        "n_runs": n,
        "n_pass": n - n_fail,
        "n_fail": n_fail,
        "fail_rate": round(n_fail / n, 4) if n else 0.0,
        "n_error_lines": int(len(errors)),
        "error_tag_distribution": {str(k): int(v)
                                   for k, v in tags.value_counts().items()},
        "severity_distribution": ({str(k): int(v) for k, v in
                                   errors["severity"].value_counts().items()}
                                  if not errors.empty else {}),
        "metric_stats": stats,
        "by_error_tag": by_tag_time,
        "parse_stats": parse_stats,
        "columns": list(runs.columns),
    }


def failure_rate_by_field(runs: pd.DataFrame, features: List[str],
                          max_levels: int = 12) -> List[Dict[str, Any]]:
    """Observed failure rate per level of each configuration field."""
    overall = float((runs["pass_fail"] == "fail").mean())
    out = []
    for f in features:
        col = runs[f]
        if pd.api.types.is_numeric_dtype(col) and col.nunique() > max_levels:
            try:
                binned = pd.qcut(col, q=5, duplicates="drop")
                keys = binned.astype(str)
            except ValueError:
                continue
        else:
            keys = col.astype(str)
        g = runs.groupby(keys, observed=True)["pass_fail"].agg(
            n="size", fails=lambda s: int((s == "fail").sum()))
        levels = [{
            "level": str(k),
            "n": int(r["n"]),
            "fail_rate": round(float(r["fails"] / r["n"]), 4),
            "lift": round(float((r["fails"] / r["n"]) / overall), 3)
            if overall else None,
        } for k, r in g.iterrows()]
        levels.sort(key=lambda d: -d["fail_rate"])
        spread = (levels[0]["fail_rate"] - levels[-1]["fail_rate"]) if levels else 0
        out.append({"field": f, "levels": levels, "spread": round(spread, 4)})
    out.sort(key=lambda d: -d["spread"])
    return out


def run_analysis(
    runs: pd.DataFrame,
    errors: pd.DataFrame,
    parse_stats: Dict[str, int],
    *,
    max_risk: float = 0.02,
    n_trials: int = 150,
    dbscan_eps: float = 0.35,
    dbscan_min_samples: int = 1,
    seed: int = 42,
    enable_recommender: bool = True,
    progress: Optional[Callable[[str, int], None]] = None,
) -> Dict[str, Any]:
    """Full analysis. Returns the dashboard payload."""
    log: List[Dict] = []
    t0 = time.time()

    def tick(msg: str, pct: int) -> None:
        if progress:
            progress(msg, pct)

    tick("Summarising corpus", 10)
    summary = _stage("summary", lambda: summarize(runs, errors, parse_stats), log)

    tick("Training risk model", 25)
    risk = _stage("risk_model",
                  lambda: train_risk_model(runs, seed=seed), log)

    features = risk.get("features") if isinstance(risk, dict) else None
    if not features:
        features = select_features(runs)

    proba = risk.get("_proba") if isinstance(risk, dict) else None
    if proba is None:
        proba = np.full(len(runs), float((runs["pass_fail"] == "fail").mean()))

    tick("Scoring per-run risk", 40)
    meter = _stage("risk_meter", lambda: risk_meter(risk, runs), log)

    tick("Clustering failure fingerprints", 55)
    fp = _stage("fingerprints",
                lambda: cluster_failures(runs, eps=dbscan_eps,
                                         min_samples=dbscan_min_samples), log)

    tick("Building Pareto frontier", 68)
    # Group Pareto points over the settings SHAP says matter most, so each
    # point has enough runs behind it for the observed rate to be meaningful.
    importance_order = [e["feature"] for e in risk.get("shap_importance", [])] \
        if isinstance(risk, dict) else None
    pf = _stage("pareto",
                lambda: pareto_frontier(runs, features, proba,
                                        importance_order=importance_order), log)

    tick("Diffing configurations", 78)
    delta = _stage("aggregate_delta",
                   lambda: aggregate_delta(runs, features), log)
    twins = _stage("nearest_twin_diff",
                   lambda: nearest_twin_diff(runs, features, seed=seed), log)

    tick("Computing failure rates by field", 85)
    by_field = _stage("failure_rate_by_field",
                      lambda: failure_rate_by_field(runs, features), log)

    rec: Any = {"skipped": True}
    if enable_recommender and isinstance(risk, dict) and "_model" in risk:
        tick("Optimising configurations", 92)
        rec = _stage("recommender",
                     lambda: recommend(runs, features, risk["_X"],
                                       risk["_model"], max_risk=max_risk,
                                       n_trials=n_trials, seed=seed), log)

    tick("Finalising", 99)
    clean_risk = {k: v for k, v in risk.items()
                  if not k.startswith("_")} if isinstance(risk, dict) else risk

    return {
        "summary": summary,
        "risk_model": clean_risk,
        "risk_meter": meter,
        "fingerprints": fp,
        "pareto": pf,
        "config_diff": {"aggregate": delta, "nearest_twin": twins},
        "failure_by_field": by_field,
        "recommendations": rec,
        "stage_log": log,
        "total_seconds": round(time.time() - t0, 2),
    }


def analyze_files(paths: List[str], **kw) -> Dict[str, Any]:
    runs, errors, stats = parse_files(paths)
    return run_analysis(runs, errors, stats.as_dict(), **kw)


def analyze_text(text: str, **kw) -> Dict[str, Any]:
    runs, errors, stats = parse_text(text)
    return run_analysis(runs, errors, stats.as_dict(), **kw)
