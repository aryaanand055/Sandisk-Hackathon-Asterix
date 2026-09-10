#!/usr/bin/env python3
"""
Phase 3 - configuration diff engine (Q8).

Answers "what actually differs between the runs that passed and the runs that
failed?" two ways, both scoped to identical test sequences so the comparison is
apples to apples:

1. Aggregate delta - for every config field, how the distribution shifts
   between passing and failing runs of the same test.
2. Nearest-twin diff - for each failing run, find the most similar PASSING run
   of the same test and record exactly which fields differ. Aggregating those
   diffs surfaces the settings that flip an otherwise-identical run.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEQUENCE_FIELD = "test_name"


def _split_kinds(runs: pd.DataFrame, features: List[str]):
    num = [f for f in features
           if pd.api.types.is_numeric_dtype(runs[f]) and runs[f].nunique() > 2]
    cat = [f for f in features if f not in num]
    return num, cat


def aggregate_delta(runs: pd.DataFrame, features: List[str]) -> List[Dict[str, Any]]:
    """Per-sequence, per-field distribution shift between pass and fail."""
    num, cat = _split_kinds(runs, features)
    out: List[Dict[str, Any]] = []

    seq_field = SEQUENCE_FIELD if SEQUENCE_FIELD in runs.columns else None
    groups = runs.groupby(seq_field) if seq_field else [("ALL", runs)]

    for seq, grp in groups:
        f = grp[grp["pass_fail"] == "fail"]
        p = grp[grp["pass_fail"] == "pass"]
        if len(f) < 5 or len(p) < 5:
            continue
        entries = []
        for feat in features:
            if feat == seq_field:
                continue
            if feat in num:
                mf, mp = float(f[feat].mean()), float(p[feat].mean())
                sd = float(grp[feat].std()) or 1.0
                entries.append({
                    "field": feat, "kind": "numeric",
                    "fail_value": round(mf, 4), "pass_value": round(mp, 4),
                    "delta": round(mf - mp, 4),
                    "effect_size": round((mf - mp) / sd, 4),
                })
            else:
                fs = f[feat].astype(str).value_counts(normalize=True)
                ps = p[feat].astype(str).value_counts(normalize=True)
                keys = set(fs.index) | set(ps.index)
                best, best_d = None, 0.0
                for k in keys:
                    d = float(fs.get(k, 0.0) - ps.get(k, 0.0))
                    if abs(d) > abs(best_d):
                        best, best_d = k, d
                entries.append({
                    "field": feat, "kind": "categorical",
                    "value": best,
                    "fail_share": round(float(fs.get(best, 0.0)), 4),
                    "pass_share": round(float(ps.get(best, 0.0)), 4),
                    "delta": round(best_d, 4),
                    "effect_size": round(best_d, 4),
                })
        entries.sort(key=lambda e: -abs(e["effect_size"]))
        out.append({
            "sequence": str(seq),
            "n_fail": int(len(f)), "n_pass": int(len(p)),
            "fail_rate": round(float(len(f) / len(grp)), 4),
            "fields": entries,
        })
    out.sort(key=lambda g: -g["fail_rate"])
    return out


def nearest_twin_diff(
    runs: pd.DataFrame,
    features: List[str],
    max_pairs_per_sequence: int = 200,
    seed: int = 42,
) -> Dict[str, Any]:
    """Pair each failing run with its closest passing run of the same test."""
    num, cat = _split_kinds(runs, features)
    feats = [f for f in features if f != SEQUENCE_FIELD]
    num = [f for f in num if f != SEQUENCE_FIELD]
    cat = [f for f in cat if f != SEQUENCE_FIELD]

    rng = np.random.default_rng(seed)
    field_hits: Dict[str, int] = {f: 0 for f in feats}
    pairs: List[Dict[str, Any]] = []
    total_pairs = 0

    # Continuous fields differ between almost any two runs, so an exact
    # comparison would rank them at ~100% and bury the settings that matter.
    # Only count a numeric field as changed when it moves by at least half a
    # standard deviation.
    tol = {f: 0.5 * float(runs[f].std() or 0.0) for f in num}

    seq_field = SEQUENCE_FIELD if SEQUENCE_FIELD in runs.columns else None
    groups = runs.groupby(seq_field) if seq_field else [("ALL", runs)]

    for seq, grp in groups:
        f = grp[grp["pass_fail"] == "fail"]
        p = grp[grp["pass_fail"] == "pass"]
        if len(f) < 2 or len(p) < 2:
            continue

        parts_f, parts_p = [], []
        if num:
            sc = StandardScaler().fit(grp[num].to_numpy(dtype=float))
            parts_f.append(sc.transform(f[num].to_numpy(dtype=float)))
            parts_p.append(sc.transform(p[num].to_numpy(dtype=float)))
        if cat:
            enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
            enc.fit(grp[cat].astype(str))
            parts_f.append(enc.transform(f[cat].astype(str)))
            parts_p.append(enc.transform(p[cat].astype(str)))
        if not parts_f:
            continue

        Xf = np.hstack(parts_f)
        Xp = np.hstack(parts_p)
        nn = NearestNeighbors(n_neighbors=1).fit(Xp)

        k = min(max_pairs_per_sequence, len(f))
        idx = rng.choice(len(f), size=k, replace=False)
        dist, nbr = nn.kneighbors(Xf[idx])

        for j, (row_i, nb_i, d) in enumerate(zip(idx, nbr[:, 0], dist[:, 0])):
            fr, pr = f.iloc[row_i], p.iloc[nb_i]
            diffs = []
            for feat in feats:
                a, b = fr[feat], pr[feat]
                if feat in num:
                    same = abs(float(a) - float(b)) <= tol[feat]
                else:
                    same = str(a) == str(b)
                if not same:
                    diffs.append({"field": feat,
                                  "failing_value": _safe(a),
                                  "passing_value": _safe(b)})
                    field_hits[feat] += 1
            total_pairs += 1
            if len(pairs) < 60 and diffs:
                pairs.append({
                    "sequence": str(seq),
                    "failing_run": str(fr["run_id"]),
                    "passing_run": str(pr["run_id"]),
                    "distance": round(float(d), 4),
                    "error_tag": str(fr.get("primary_error_tag", "")),
                    "n_differences": len(diffs),
                    "differences": diffs,
                })

    ranking = sorted(
        ({"field": k, "diff_count": v,
          "diff_rate": round(v / total_pairs, 4) if total_pairs else 0.0}
         for k, v in field_hits.items()),
        key=lambda d: -d["diff_count"])
    pairs.sort(key=lambda p: (p["n_differences"], p["distance"]))
    return {"total_pairs": total_pairs, "field_ranking": ranking,
            "example_pairs": pairs[:40]}


def diff_two_runs(runs: pd.DataFrame, run_a: str, run_b: str,
                  features: List[str]) -> Dict[str, Any]:
    """Field-by-field diff of two named runs - drives the log-diff viewer."""
    ra = runs.loc[runs["run_id"] == run_a]
    rb = runs.loc[runs["run_id"] == run_b]
    if ra.empty or rb.empty:
        raise KeyError(f"Unknown run_id: {run_a if ra.empty else run_b}")
    ra, rb = ra.iloc[0], rb.iloc[0]

    rows = []
    for feat in features:
        a, b = ra[feat], rb[feat]
        same = str(a) == str(b)
        rows.append({"field": feat, "a": _safe(a), "b": _safe(b),
                     "changed": not same})
    return {
        "run_a": {"run_id": run_a, "pass_fail": str(ra["pass_fail"]),
                  "error_tag": str(ra.get("primary_error_tag", "")),
                  "trace": str(ra.get("error_trace", ""))[:2000]},
        "run_b": {"run_id": run_b, "pass_fail": str(rb["pass_fail"]),
                  "error_tag": str(rb.get("primary_error_tag", "")),
                  "trace": str(rb.get("error_trace", ""))[:2000]},
        "fields": rows,
        "n_changed": sum(1 for r in rows if r["changed"]),
    }


def _safe(v: Any) -> Any:
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return round(float(v), 4)
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
