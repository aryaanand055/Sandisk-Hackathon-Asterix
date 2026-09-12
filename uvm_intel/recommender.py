#!/usr/bin/env python3
"""
Phase 3 - configuration recommender (Q6).

Bayesian optimisation (Optuna/TPE) over two surrogate models:

  * the failure-risk classifier from risk_model.py
  * a throughput regressor fitted on PASSING runs only, so the objective is
    "throughput you get when it works", not throughput averaged with the
    degraded numbers that failures produce

The search maximises predicted throughput subject to predicted failure
probability staying under a hard ceiling (default 2%).
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

PENALTY = 1.0e6


def _search_space(runs: pd.DataFrame, features: List[str]) -> Dict[str, Dict]:
    """Derive the searchable domain of each feature from observed data."""
    space: Dict[str, Dict] = {}
    for f in features:
        col = runs[f]
        if pd.api.types.is_numeric_dtype(col) and col.nunique() > 8:
            lo, hi = float(col.min()), float(col.max())
            is_int = bool(pd.api.types.is_integer_dtype(col))
            space[f] = {"kind": "int" if is_int else "float",
                        "low": int(lo) if is_int else lo,
                        "high": int(hi) if is_int else hi}
        else:
            vals = sorted(col.unique().tolist(), key=str)
            space[f] = {"kind": "categorical", "choices": vals}
    return space


def _fit_throughput_model(runs: pd.DataFrame, features: List[str],
                          X: pd.DataFrame, seed: int):
    """Regressor for throughput on passing runs with sklearn fallback."""
    mask = (runs["pass_fail"] == "pass").to_numpy()
    if mask.sum() < 50:
        mask = np.ones(len(runs), dtype=bool)

    y_tp = runs.loc[mask, "throughput_mbps"].to_numpy(dtype=float)
    X_pass = X[mask]

    try:
        import lightgbm as lgb
        model = lgb.LGBMRegressor(
            n_estimators=350, learning_rate=0.05, num_leaves=48,
            min_child_samples=25, random_state=seed, n_jobs=-1, verbose=-1)
        model.fit(X_pass, y_tp)
        return model
    except (ImportError, Exception):
        from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
        # Encode categoricals for sklearn
        X_pass_enc = X_pass.copy()
        for col in features:
            if X_pass_enc[col].dtype == "category" or str(X_pass_enc[col].dtype) in ("object", "str"):
                cats = {v: i for i, v in enumerate(X[col].astype(str).unique())}
                X_pass_enc[col] = X_pass_enc[col].astype(str).map(cats).fillna(-1).astype(int)

        try:
            model = HistGradientBoostingRegressor(max_iter=150, random_state=seed)
            model.fit(X_pass_enc, y_tp)
        except Exception:
            model = RandomForestRegressor(n_estimators=100, random_state=seed, n_jobs=-1)
            model.fit(X_pass_enc, y_tp)
        return model


def recommend(
    runs: pd.DataFrame,
    features: List[str],
    X: pd.DataFrame,
    risk_model: Any,
    max_risk: float = 0.02,
    n_trials: int = 150,
    seed: int = 42,
    top_n: int = 10,
) -> Dict[str, Any]:
    """Search for high-throughput, low-risk configurations with Optuna or Random/Grid fallback."""
    space = _search_space(runs, features)
    tp_model = _fit_throughput_model(runs, features, X, seed)
    dtypes = {c: X[c].dtype for c in X.columns}

    # Map categories to numeric codes if using sklearn surrogate models
    cat_maps = {}
    for col in features:
        if str(X[col].dtype) == "category" or str(X[col].dtype) in ("object", "str"):
            cat_maps[col] = {v: i for i, v in enumerate(X[col].astype(str).unique())}

    def to_frame(cfg: Dict[str, Any]) -> pd.DataFrame:
        row = pd.DataFrame([cfg], columns=features)
        for c, dt in dtypes.items():
            if str(dt) == "category":
                row[c] = pd.Categorical(row[c].astype(str),
                                        categories=dt.categories)
            else:
                row[c] = row[c].astype(dt)
        return row

    def to_encoded_frame(cfg: Dict[str, Any]) -> pd.DataFrame:
        row = pd.DataFrame([cfg], columns=features)
        for c in features:
            if c in cat_maps:
                row[c] = row[c].astype(str).map(cat_maps[c]).fillna(-1).astype(int)
            else:
                row[c] = pd.to_numeric(row[c], errors="coerce").fillna(0)
        return row

    def predict_risk_tp(cfg: Dict[str, Any]):
        # Try both raw categorical frame and encoded frame
        try:
            fr = to_frame(cfg)
            risk = float(risk_model.predict_proba(fr)[0, 1])
        except Exception:
            fr_enc = to_encoded_frame(cfg)
            risk = float(risk_model.predict_proba(fr_enc)[0, 1])

        try:
            fr = to_frame(cfg)
            tp = float(tp_model.predict(fr)[0])
        except Exception:
            fr_enc = to_encoded_frame(cfg)
            tp = float(tp_model.predict(fr_enc)[0])
        return risk, tp

    evaluated: List[Dict[str, Any]] = []

    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial: "optuna.Trial") -> float:
            cfg: Dict[str, Any] = {}
            for f, spec in space.items():
                if spec["kind"] == "categorical":
                    cfg[f] = trial.suggest_categorical(f, spec["choices"])
                elif spec["kind"] == "int":
                    cfg[f] = trial.suggest_int(f, spec["low"], spec["high"])
                else:
                    cfg[f] = trial.suggest_float(f, spec["low"], spec["high"])

            risk, tp = predict_risk_tp(cfg)
            evaluated.append({"config": cfg, "predicted_risk": round(risk, 5),
                              "predicted_throughput_mbps": round(tp, 2),
                              "feasible": risk <= max_risk})
            return tp - PENALTY * max(0.0, risk - max_risk)

        sampler = optuna.samplers.TPESampler(seed=seed)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
        history = [{
            "trial": i,
            "value": round(float(t.value), 2) if t.value is not None else None,
        } for i, t in enumerate(study.trials) if t.value is not None
            and t.value > -PENALTY / 2]

    except (ImportError, Exception):
        # Fallback Random Search over the derived configuration space
        rng = np.random.default_rng(seed)
        history = []
        for i in range(n_trials):
            cfg: Dict[str, Any] = {}
            for f, spec in space.items():
                if spec["kind"] == "categorical":
                    cfg[f] = rng.choice(spec["choices"])
                elif spec["kind"] == "int":
                    cfg[f] = int(rng.integers(spec["low"], spec["high"] + 1))
                else:
                    cfg[f] = float(rng.uniform(spec["low"], spec["high"]))

            risk, tp = predict_risk_tp(cfg)
            is_feasible = risk <= max_risk
            evaluated.append({
                "config": cfg, "predicted_risk": round(risk, 5),
                "predicted_throughput_mbps": round(tp, 2),
                "feasible": is_feasible
            })
            val = tp - PENALTY * max(0.0, risk - max_risk)
            if val > -PENALTY / 2:
                history.append({"trial": i, "value": round(float(val), 2)})

    feasible = [e for e in evaluated if e["feasible"]]
    best = feasible[:top_n]
    min_risk = min((e["predicted_risk"] for e in evaluated), default=None)
    fallback = []
    if not feasible:
        fallback = sorted(evaluated, key=lambda e: (
            e["predicted_risk"], -e["predicted_throughput_mbps"]))[:top_n]

    obs_tp = float(runs.loc[runs["pass_fail"] == "pass",
                            "throughput_mbps"].mean()) if "throughput_mbps" in runs.columns else 50.0
    uplift = (round((best[0]["predicted_throughput_mbps"] / obs_tp - 1) * 100, 1)
              if best and obs_tp else None)

    def _clean_cfg(cfg_dict):
        return {k: (v.item() if hasattr(v, "item") else (int(v) if isinstance(v, (np.integer,)) else (float(v) if isinstance(v, (np.floating,)) else str(v) if not isinstance(v, (int, float, str, bool)) else v)))
                for k, v in cfg_dict.items()}

    for item in best:
        item["config"] = _clean_cfg(item["config"])
    for item in fallback:
        item["config"] = _clean_cfg(item["config"])

    return {
        "max_risk": max_risk,
        "n_trials": n_trials,
        "n_feasible": len(feasible),
        "feasible_rate": round(len(feasible) / max(len(evaluated), 1), 4),
        "constraint_satisfiable": bool(feasible),
        "min_achievable_risk": round(min_risk, 5) if min_risk is not None else None,
        "recommendations": best,
        "fallback_recommendations": fallback,
        "baseline_mean_throughput_mbps": round(obs_tp, 2),
        "throughput_uplift_pct": uplift,
        "search_space": {k: v for k, v in space.items()},
        "history": history[:400],
    }
