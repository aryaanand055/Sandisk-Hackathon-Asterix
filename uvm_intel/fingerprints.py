#!/usr/bin/env python3
"""
Phase 2 - failure fingerprinting and clustering (Q4, Q5).

Groups failing runs by the *shape* of their UVM error trace so that a
deterministic RTL bug is separated from random seed noise.

Method
------
1. Every error message is masked to a seed-invariant template by
   log_format.fingerprint() - hex addresses become <ADDR>, numbers <N>.
2. TF-IDF is fitted over the DISTINCT templates, not over every run. A 50k-run
   corpus collapses to a few dozen templates, which keeps DBSCAN's pairwise
   cosine work trivial instead of quadratic in the number of runs.
3. Each run inherits the cluster of its trace template. min_samples defaults
   to 1 because every distinct template is already a real failure mode worth
   reporting - a template seen once is a rare bug, not noise to discard. eps
   still merges templates that are only wording variants of each other.
4. Per cluster we compute a determinism score:

       determinism = 1 - (distinct raw traces / runs in cluster)

   A cluster whose raw text is byte-identical across many different seeds
   scores near 1.0 and is flagged as a deterministic RTL bug. A cluster whose
   text varies with every seed scores near 0.0 and is seed noise.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

DETERMINISTIC_THRESHOLD = 0.80
CLEAN = "CLEAN"


def cluster_failures(
    runs: pd.DataFrame,
    eps: float = 0.35,
    min_samples: int = 1,
    max_features: int = 3000,
) -> Dict[str, Any]:
    """Cluster failing runs by error-trace template."""
    df = runs.copy()
    if "trace_fingerprint" not in df.columns:
        df["trace_fingerprint"] = df["primary_error_tag"].fillna("ERR_UNKNOWN") if "primary_error_tag" in df.columns else "ERR_UNKNOWN"
    if "error_trace" not in df.columns:
        df["error_trace"] = df["primary_error_tag"].fillna("") if "primary_error_tag" in df.columns else ""
    if "seed" not in df.columns:
        df["seed"] = 0

    failing = df[(df["pass_fail"] == "fail") & (df["trace_fingerprint"] != CLEAN)].copy()

    if failing.empty:
        return {"n_failing": 0, "clusters": [], "scatter": [],
                "n_clusters": 0, "n_noise": 0, "params": {
                    "eps": eps, "min_samples": min_samples}}

    # --- 1. Distinct templates -------------------------------------------
    templates = failing["trace_fingerprint"].astype(str)
    uniq = pd.Index(templates.unique())

    # --- 2. TF-IDF over templates ----------------------------------------
    vec = TfidfVectorizer(
        max_features=max_features, ngram_range=(1, 2),
        token_pattern=r"[A-Za-z_<>][A-Za-z0-9_<>]+", lowercase=True,
    )
    M = vec.fit_transform(uniq.tolist())

    # --- 3. DBSCAN on cosine distance ------------------------------------
    n_uniq = M.shape[0]
    if n_uniq == 1:
        labels = np.zeros(1, dtype=int)
    else:
        labels = DBSCAN(eps=eps, min_samples=min(min_samples, n_uniq),
                        metric="cosine").fit_predict(M)

    # --- 4. 2D projection for the scatter plot ---------------------------
    if n_uniq >= 3:
        comps = TruncatedSVD(n_components=2, random_state=42).fit_transform(M)
    else:
        comps = np.zeros((n_uniq, 2))

    tmpl_cluster = dict(zip(uniq, labels))
    tmpl_xy = {t: (float(comps[i, 0]), float(comps[i, 1]))
               for i, t in enumerate(uniq)}
    failing["cluster"] = templates.map(tmpl_cluster).to_numpy()

    # --- 5. Per-cluster statistics ---------------------------------------
    clusters: List[Dict[str, Any]] = []
    for cid, grp in failing.groupby("cluster"):
        raw = grp["error_trace"].astype(str)
        n = len(grp)
        distinct_raw = int(raw.nunique())
        determinism = round(1.0 - (distinct_raw / n), 4) if n else 0.0
        distinct_seeds = int(grp["seed"].nunique()) if "seed" in grp else 0

        tag_counts = grp["primary_error_tag"].value_counts()
        rep = grp["trace_fingerprint"].value_counts().idxmax()

        clusters.append({
            "cluster_id": int(cid),
            "is_noise_cluster": bool(cid == -1),
            "size": n,
            "share_of_failures": round(n / len(failing), 4),
            "dominant_tag": str(tag_counts.idxmax()),
            "tag_breakdown": {str(k): int(v) for k, v in tag_counts.items()},
            "distinct_raw_traces": distinct_raw,
            "distinct_seeds": distinct_seeds,
            "determinism": determinism,
            "classification": ("deterministic RTL bug"
                               if determinism >= DETERMINISTIC_THRESHOLD
                               else "seed-dependent / random"),
            "n_templates": int(grp["trace_fingerprint"].nunique()),
            "representative_template": str(rep),
            "example_trace": str(raw.iloc[0])[:400],
            "example_run_ids": grp["run_id"].head(5).astype(str).tolist(),
            "mean_execution_time_ms": round(float(grp["execution_time_ms"].mean()), 2)
            if "execution_time_ms" in grp else None,
        })

    clusters.sort(key=lambda c: -c["size"])

    # --- 6. Scatter points (one per template, sized by run count) --------
    tmpl_counts = templates.value_counts()
    scatter = [{
        "x": round(tmpl_xy[t][0], 4),
        "y": round(tmpl_xy[t][1], 4),
        "cluster": int(tmpl_cluster[t]),
        "count": int(tmpl_counts[t]),
        "template": str(t)[:160],
    } for t in uniq]

    real = [c for c in clusters if not c["is_noise_cluster"]]
    return {
        "n_failing": int(len(failing)),
        "n_templates": int(n_uniq),
        "n_clusters": len(real),
        "n_noise": int((labels == -1).sum()),
        "deterministic_clusters": [c["cluster_id"] for c in real
                                   if c["determinism"] >= DETERMINISTIC_THRESHOLD],
        "clusters": clusters,
        "scatter": scatter,
        "params": {"eps": eps, "min_samples": min_samples,
                   "determinism_threshold": DETERMINISTIC_THRESHOLD},
    }
