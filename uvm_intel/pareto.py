#!/usr/bin/env python3
"""
Phase 2 - Pareto tradeoff analysis (Q2).

Builds the throughput / risk frontier over distinct configurations. A config is
Pareto-optimal when no other config delivers both higher throughput and lower
predicted failure probability, so the frontier is exactly the set of choices
worth arguing about.
"""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _signature(df: pd.DataFrame, features: List[str]) -> pd.Series:
    """Stable string key for a configuration."""
    return df[features].astype(str).agg("|".join, axis=1)


def group_features(
    runs: pd.DataFrame,
    features: List[str],
    importance_order: Optional[List[str]] = None,
    max_levels: int = 12,
    n_group_features: int = 4,
) -> List[str]:
    """Pick the settings a Pareto point should be defined over.

    Continuous environment readings (voltage, temperature) are unique per run,
    so including them would make every run its own "configuration" and the
    frontier would compare 10,000 singletons with a meaningless observed
    failure rate. We keep only low-cardinality, genuinely settable knobs, and
    among those the ones the model says matter most - which yields groups with
    enough repeats for the observed rate to mean something.
    """
    discrete = [f for f in features if runs[f].nunique() <= max_levels]
    if importance_order:
        rank = {f: i for i, f in enumerate(importance_order)}
        discrete.sort(key=lambda f: rank.get(f, 10**6))
    return discrete[:n_group_features] or features[:n_group_features]


def pareto_frontier(
    runs: pd.DataFrame,
    features: List[str],
    predicted_risk: np.ndarray,
    min_runs: int = 3,
    max_points: int = 4000,
    importance_order: Optional[List[str]] = None,
    n_group_features: int = 4,
) -> Dict[str, Any]:
    """Aggregate runs by configuration and extract the frontier."""
    df = runs.copy()
    if "throughput_mbps" not in df.columns:
        df["throughput_mbps"] = 1.0
    if "execution_time_ms" not in df.columns:
        df["execution_time_ms"] = 0.0
    df["_risk"] = predicted_risk
    features = group_features(df, features, importance_order,
                              n_group_features=n_group_features)
    df["_sig"] = _signature(df, features)

    agg = df.groupby("_sig").agg(
        throughput=("throughput_mbps", "mean"),
        risk=("_risk", "mean"),
        exec_ms=("execution_time_ms", "mean"),
        observed_fail_rate=("pass_fail", lambda s: float((s == "fail").mean())),
        n_runs=("run_id", "size"),
    ).reset_index()
    agg = agg[agg["n_runs"] >= min_runs]

    if agg.empty:
        return {"points": [], "frontier": [], "n_configs": 0}

    # --- Frontier sweep: sort by throughput desc, keep strictly lower risk ---
    ordered = agg.sort_values(
        ["throughput", "risk"], ascending=[False, True]).reset_index(drop=True)
    best_risk = np.inf
    on_front = np.zeros(len(ordered), dtype=bool)
    for i, r in enumerate(ordered["risk"].to_numpy()):
        if r < best_risk:
            on_front[i] = True
            best_risk = r
    ordered["is_pareto"] = on_front

    # Attach a representative config for every frontier point.
    first_of_sig = df.drop_duplicates("_sig").set_index("_sig")

    def _cfg(sig: str) -> Dict[str, Any]:
        row = first_of_sig.loc[sig]
        return {f: _safe(row[f]) for f in features}

    frontier = [{
        "signature": r["_sig"],
        "throughput_mbps": round(float(r["throughput"]), 2),
        "predicted_risk": round(float(r["risk"]), 4),
        "observed_fail_rate": round(float(r["observed_fail_rate"]), 4),
        "execution_time_ms": round(float(r["exec_ms"]), 2),
        "n_runs": int(r["n_runs"]),
        "config": _cfg(r["_sig"]),
    } for _, r in ordered[ordered["is_pareto"]].iterrows()]
    frontier.sort(key=lambda p: -p["throughput_mbps"])

    # Downsample the cloud so the scatter stays responsive.
    cloud = ordered[~ordered["is_pareto"]]
    if len(cloud) > max_points:
        cloud = cloud.sample(max_points, random_state=42)
    points = [{
        "throughput_mbps": round(float(r["throughput"]), 2),
        "predicted_risk": round(float(r["risk"]), 4),
        "n_runs": int(r["n_runs"]),
        "is_pareto": False,
    } for _, r in cloud.iterrows()]

    # A few named operating points for the summary strip.
    safe = [p for p in frontier if p["predicted_risk"] <= 0.02]
    knee = _knee(frontier)
    return {
        "group_features": features,
        "min_runs_per_config": min_runs,
        "n_configs": int(len(agg)),
        "n_frontier": len(frontier),
        "points": points,
        "frontier": frontier,
        "max_throughput_config": frontier[0] if frontier else None,
        "lowest_risk_config": min(
            frontier, key=lambda p: p["predicted_risk"]) if frontier else None,
        "best_safe_config": (max(safe, key=lambda p: p["throughput_mbps"])
                             if safe else None),
        "knee_config": knee,
    }


def _knee(frontier: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Point on the frontier furthest from the line joining its endpoints."""
    if len(frontier) < 3:
        return frontier[0] if frontier else None
    x = np.array([p["predicted_risk"] for p in frontier], dtype=float)
    y = np.array([p["throughput_mbps"] for p in frontier], dtype=float)
    xs = (x - x.min()) / (np.ptp(x) or 1.0)
    ys = (y - y.min()) / (np.ptp(y) or 1.0)
    x1, y1, x2, y2 = xs[0], ys[0], xs[-1], ys[-1]
    denom = np.hypot(x2 - x1, y2 - y1) or 1.0
    dist = np.abs((y2 - y1) * xs - (x2 - x1) * ys + x2 * y1 - y2 * x1) / denom
    return frontier[int(np.argmax(dist))]


def _safe(v: Any) -> Any:
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
