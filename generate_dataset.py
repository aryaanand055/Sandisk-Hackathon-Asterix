#!/usr/bin/env python3
"""
Synthetic dataset generator for Configuration Intelligence.

Generates test-run data from the schema in data_model.py, injects hidden
rules that bias outcomes, and writes CSV + ground truth JSON.

Architecture
------------
* Sampling is fully vectorised with numpy — no pure-Python row loops.
* Non-outcome fields are sampled generically from the SCHEMA definition;
  adding a new field there requires zero changes here.
* Rules are data-driven dicts with condition/effect pairs, easily extensible.

Usage
-----
    python generate_dataset.py [--n-runs N] [--seed S] [--output FILE]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from data_model import SCHEMA, FieldSpec, get_field, get_fields_by_category


# ═══════════════════════════════════════════════════════════════════════════
# Rule Definitions
# ═══════════════════════════════════════════════════════════════════════════
#
# Each rule is a plain dict — directly serialisable to JSON.
#
#   phase = "sampling"  →  modifies input columns after initial sampling
#   phase = "outcome"   →  modifies pass_fail / execution_time
#
# Effect types:
#   failure_multiplier     — multiplies base failure probability
#   exec_time_multiplier   — multiplies base execution time
#   throughput_multiplier  — multiplies derived throughput
#   value_bias             — overrides a column value with given probability
#
# error_type_bias (optional): when a row fails AND this rule had the
# highest failure multiplier among matching rules, assign this error type.

RULES: List[Dict] = [
    # ── Rule 1: 3-way config × randomization → queue starvation ──────────
    {
        "id": "rule_1",
        "description": (
            "Deep queues under high concurrency on the static scheduler "
            "starve the dispatcher and time out"
        ),
        "conditions": [
            {"field": "queue_depth",  "op": ">=", "value": 64},
            {"field": "concurrency",  "op": ">=", "value": 16},
            {"field": "scheduler",    "op": "==", "value": "static"},
        ],
        "effect": {
            "type": "failure_multiplier",
            "target": "pass_fail",
            "value": 3.5,
        },
        "error_type_bias": "timeout",
        "phase": "outcome",
    },

    # ── Rule 2: 3-way config × randomization → codec corruption ──────────
    {
        "id": "rule_2",
        "description": (
            "zstd compression on high-entropy payloads with a small cache "
            "overruns the codec window and corrupts data"
        ),
        "conditions": [
            {"field": "compression",     "op": "==", "value": "zstd"},
            {"field": "payload_entropy", "op": ">",  "value": 0.80},
            {"field": "cache_size",      "op": "==", "value": "small"},
        ],
        "effect": {
            "type": "failure_multiplier",
            "target": "pass_fail",
            "value": 4.0,
        },
        "error_type_bias": "corruption",
        "phase": "outcome",
    },

    # ── Rule 3: config × environment → thermal runaway ───────────────────
    {
        "id": "rule_3",
        "description": (
            "Turbo power mode above 75 °C trips thermal protection"
        ),
        "conditions": [
            {"field": "power_mode",  "op": "==", "value": "turbo"},
            {"field": "temperature", "op": ">",  "value": 75.0},
        ],
        "effect": {
            "type": "failure_multiplier",
            "target": "pass_fail",
            "value": 3.0,
        },
        "error_type_bias": "thermal",
        "phase": "outcome",
    },

    # ── Rule 4: config × randomization → unprotected fault injection ─────
    {
        "id": "rule_4",
        "description": (
            "ECC disabled while fault injection exceeds 20 % leaves "
            "bit flips uncorrected"
        ),
        "conditions": [
            {"field": "ecc_mode",       "op": "==", "value": "off"},
            {"field": "injection_rate", "op": ">",  "value": 0.20},
        ],
        "effect": {
            "type": "failure_multiplier",
            "target": "pass_fail",
            "value": 2.8,
        },
        "error_type_bias": "ecc_uncorrectable",
        "phase": "outcome",
    },

    # ── Rule 5: 3-way config × randomization → prefetch thrashing ────────
    {
        "id": "rule_5",
        "description": (
            "Aggressive prefetch under random access with little memory "
            "thrashes the line fill buffer and slows execution"
        ),
        "conditions": [
            {"field": "prefetch_depth", "op": ">=", "value": 8},
            {"field": "access_pattern", "op": "==", "value": "random"},
            {"field": "memory_size",    "op": "<=", "value": 512},
        ],
        "effect": {
            "type": "exec_time_multiplier",
            "target": "execution_time",
            "value": 2.2,
        },
        "phase": "outcome",
    },

    # ── Rule 6: config × randomization → eco-mode clamp ──────────────────
    {
        "id": "rule_6",
        "description": (
            "Eco power mode on large workloads clamps the clock and "
            "stretches execution time"
        ),
        "conditions": [
            {"field": "power_mode", "op": "==", "value": "eco"},
            {"field": "workload",   "op": "==", "value": "large"},
        ],
        "effect": {
            "type": "exec_time_multiplier",
            "target": "execution_time",
            "value": 1.8,
        },
        "phase": "outcome",
    },

    # ── Rule 7: 3-way randomization × config → burst overflow ────────────
    {
        "id": "rule_7",
        "description": (
            "Long bursts into a shallow queue under high traffic overflow "
            "the ingress FIFO"
        ),
        "conditions": [
            {"field": "burst_length",    "op": ">",  "value": 200},
            {"field": "queue_depth",     "op": "<=", "value": 4},
            {"field": "traffic_pattern", "op": "==", "value": "high"},
        ],
        "effect": {
            "type": "failure_multiplier",
            "target": "pass_fail",
            "value": 3.2,
        },
        "error_type_bias": "overflow",
        "phase": "outcome",
    },

    # ── Rule 8: seed-driven access-pattern bias (sampling) ───────────────
    {
        "id": "rule_8",
        "description": (
            "High seed ranges bias the constraint solver toward strided "
            "access patterns"
        ),
        "conditions": [
            {"field": "random_seed", "op": ">=", "value": 90000},
        ],
        "effect": {
            "type": "value_bias",
            "target": "access_pattern",
            "value": "stride",
            "probability": 0.75,
        },
        "phase": "sampling",
    },

    # ── Rule 9: concurrency-driven traffic bias (sampling) ───────────────
    {
        "id": "rule_9",
        "description": (
            "High concurrency drives the traffic generator into its "
            "high-rate profile"
        ),
        "conditions": [
            {"field": "concurrency", "op": ">=", "value": 16},
        ],
        "effect": {
            "type": "value_bias",
            "target": "traffic_pattern",
            "value": "high",
            "probability": 0.60,
        },
        "phase": "sampling",
    },

    # ── Rule 10: config × randomization → throughput collapse ────────────
    {
        "id": "rule_10",
        "description": (
            "gzip compression under concurrency of 8 or more serialises on "
            "the codec and collapses throughput"
        ),
        "conditions": [
            {"field": "compression", "op": "==", "value": "gzip"},
            {"field": "concurrency", "op": ">=", "value": 8},
        ],
        "effect": {
            "type": "throughput_multiplier",
            "target": "throughput",
            "value": 0.55,
        },
        "phase": "outcome",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Vectorised Sampling
# ═══════════════════════════════════════════════════════════════════════════

def sample_field(spec: FieldSpec, n: int, rng: np.random.Generator) -> np.ndarray:
    """Sample *n* values for a single field, fully vectorised."""
    # Categorical / boolean → uniform choice
    if spec.field_type in ("categorical", "boolean"):
        return rng.choice(spec.domain, size=n)

    # Numeric — discrete set (e.g. memory_size)
    if spec.is_discrete_set:
        return np.array(rng.choice(spec.domain, size=n))

    # Numeric — continuous / integer range
    lo, hi = spec.domain
    params = spec.distribution_params or {}

    if spec.distribution == "normal":
        vals = rng.normal(params.get("mean", (lo + hi) / 2),
                          params.get("std", (hi - lo) / 6), size=n)
        vals = np.clip(vals, lo, hi)
    elif spec.distribution == "log_normal":
        vals = rng.lognormal(params.get("mean", 4.0),
                             params.get("std", 0.5), size=n)
        vals = np.clip(vals, lo, hi)
    else:  # uniform
        if spec.is_integer:
            return rng.integers(int(lo), int(hi) + 1, size=n)
        vals = rng.uniform(lo, hi, size=n)

    if spec.is_integer:
        vals = vals.astype(int)
    elif spec.decimal_places is not None:
        vals = np.round(vals, spec.decimal_places)

    return vals


# ═══════════════════════════════════════════════════════════════════════════
# Vectorised Rule Application
# ═══════════════════════════════════════════════════════════════════════════

_OPS = {
    "==": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    ">":  lambda s, v: s > v,
    ">=": lambda s, v: s >= v,
    "<":  lambda s, v: s < v,
    "<=": lambda s, v: s <= v,
}


def _build_mask(df: pd.DataFrame, conditions: List[Dict]) -> pd.Series:
    """Boolean mask — True where ALL conditions hold (vectorised AND)."""
    mask = pd.Series(True, index=df.index)
    for c in conditions:
        mask &= _OPS[c["op"]](df[c["field"]], c["value"])
    return mask


def _apply_sampling_rules(df: pd.DataFrame, rules: List[Dict],
                           rng: np.random.Generator) -> None:
    """Apply sampling-phase rules (modify input columns in-place)."""
    for rule in rules:
        if rule["phase"] != "sampling":
            continue
        mask = _build_mask(df, rule["conditions"])
        eff = rule["effect"]
        if eff["type"] == "value_bias":
            # Override target column with biased value for matching rows
            override = mask & (rng.random(len(df)) < eff["probability"])
            df.loc[override, eff["target"]] = eff["value"]


def _apply_outcome_rules(
    df: pd.DataFrame,
    rules: List[Dict],
    fail_prob: np.ndarray,
    exec_time: np.ndarray,
    tp_mult: np.ndarray,
) -> pd.Series:
    """Apply outcome-phase rules.  Returns rule-assigned error-type Series."""
    error_bias = pd.Series("", index=df.index)
    priority = pd.Series(0.0, index=df.index)

    for rule in rules:
        if rule["phase"] != "outcome":
            continue
        mask = _build_mask(df, rule["conditions"])
        eff = rule["effect"]

        if eff["type"] == "failure_multiplier":
            fail_prob[mask.values] *= eff["value"]
            # Track which rule "owns" the error type (highest multiplier wins)
            if "error_type_bias" in rule:
                higher = mask & (eff["value"] > priority)
                error_bias[higher] = rule["error_type_bias"]
                priority[higher] = eff["value"]

        elif eff["type"] == "exec_time_multiplier":
            exec_time[mask.values] *= eff["value"]

        elif eff["type"] == "throughput_multiplier":
            tp_mult[mask.values] *= eff["value"]

    return error_bias


# ═══════════════════════════════════════════════════════════════════════════
# Main Generator
# ═══════════════════════════════════════════════════════════════════════════

def generate(n_runs: int, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic test-run dataset (fully vectorised)."""
    rng = np.random.default_rng(seed)

    # 1 ── Identifier
    df = pd.DataFrame({"run_id": [f"RUN-{i + 1:06d}" for i in range(n_runs)]})

    # 2 ── Independent sampling of all non-outcome fields (schema-driven)
    for spec in SCHEMA:
        if spec.category != "outcome":
            df[spec.name] = sample_field(spec, n_runs, rng)

    # 3 ── Sampling-phase rules (e.g. seed → workload bias)
    _apply_sampling_rules(df, RULES, rng)

    # 4 ── Base outcomes ───────────────────────────────────────────────────
    pf_spec = get_field("pass_fail")
    base_fail = pf_spec.distribution_params["base_fail_rate"]
    fail_prob = np.full(n_runs, base_fail, dtype=np.float64)

    et_spec = get_field("execution_time")
    et_p = et_spec.distribution_params
    exec_time = rng.lognormal(et_p["mean"], et_p["std"], size=n_runs)
    exec_time = np.clip(exec_time, *et_spec.domain)

    tp_mult = np.ones(n_runs, dtype=np.float64)

    # 5 ── Outcome-phase rules ─────────────────────────────────────────────
    error_bias = _apply_outcome_rules(df, RULES, fail_prob, exec_time, tp_mult)

    # 6 ── Resolve pass / fail ─────────────────────────────────────────────
    fail_prob = np.minimum(fail_prob, 0.95)
    is_fail = rng.random(n_runs) < fail_prob
    df["pass_fail"] = np.where(is_fail, "fail", "pass")

    # 7 ── Execution time (re-clip after multipliers) ──────────────────────
    exec_time = np.clip(exec_time, *et_spec.domain)
    df["execution_time"] = np.round(exec_time, et_spec.decimal_places or 1)

    # 8 ── Throughput (inversely proportional + noise) ─────────────────────
    tp_spec = get_field("throughput")
    throughput = (500_000.0 / exec_time) * tp_mult + rng.normal(0, 200, size=n_runs)
    throughput = np.clip(throughput, *tp_spec.domain)
    df["throughput"] = np.round(throughput).astype(int)

    # 9 ── Error type (linked to rules for failing rows) ───────────────────
    fail_mask = is_fail
    # Failing rows with no rule → random error type
    no_rule_fail = fail_mask & (error_bias == "")
    error_options = ["timeout", "overflow", "corruption", "assertion"]
    n_random = no_rule_fail.sum()
    if n_random > 0:
        error_bias[no_rule_fail] = rng.choice(error_options, size=n_random)
    # Passing rows → "none"
    error_bias[~fail_mask] = "none"
    df["error_type"] = error_bias

    return df


# ═══════════════════════════════════════════════════════════════════════════
# Ground Truth Export
# ═══════════════════════════════════════════════════════════════════════════

def write_ground_truth(path: str) -> None:
    """Serialise hidden rules to JSON (never imported by ML code)."""
    with open(path, "w") as fh:
        json.dump({"rules": RULES}, fh, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# Raw Log Export
# ═══════════════════════════════════════════════════════════════════════════

def write_raw_log(df: pd.DataFrame, path: str) -> None:
    """Emit the same runs as UVM-style block logs.

    The banner line is what `ingest._find_banner` latches onto; everything
    else is plain ``key : value`` so the block parser can harvest it without
    a format-specific reader.  Written streaming — 50k blocks is far too much
    to build as one string.
    """
    cfg = [f.name for f in get_fields_by_category("configuration")]
    rnd = [f.name for f in get_fields_by_category("randomization")]
    env = [f.name for f in get_fields_by_category("environment")]

    sections = (("CONFIG", cfg), ("RANDOMIZATION", rnd), ("ENVIRONMENT", env))
    records = df.to_dict("records")

    with open(path, "w", newline="\n") as fh:
        fh.write("# UVM simulation log - Configuration Intelligence testbench\n")
        fh.write(f"# runs={len(df)} schema_version=2\n")
        for rec in records:
            verdict = "PASSED" if rec["pass_fail"] == "pass" else "FAILED"
            fh.write(f"UVM_INFO @0: RUN_START :: {rec['run_id']}\n")
            for title, names in sections:
                fh.write(f"  [{title}]\n")
                for name in names:
                    fh.write(f"    {name} : {rec[name]}\n")
            fh.write("  [RESULT]\n")
            fh.write(f"    verdict : {verdict}\n")
            fh.write(f"    execution_time : {rec['execution_time']}\n")
            fh.write(f"    throughput : {rec['throughput']}\n")
            fh.write(f"    error_type : {rec['error_type']}\n")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic test-run data."
    )
    parser.add_argument(
        "--n-runs", type=int, default=1000,
        help="Number of test runs to generate (default: 1000)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed for reproducible generation (default: 42)",
    )
    parser.add_argument(
        "--output", default="synthetic_test_runs.csv",
        help="Output CSV path (default: synthetic_test_runs.csv)",
    )
    parser.add_argument(
        "--rules-output", default="ground_truth_rules.json",
        help="Output path for ground-truth rules JSON",
    )
    parser.add_argument(
        "--log-output", default=None,
        help="Also emit raw UVM-style block logs to this path",
    )
    args = parser.parse_args()

    print(f"Generating {args.n_runs:,} test runs (seed={args.seed}) ...")
    df = generate(args.n_runs, args.seed)
    df.to_csv(args.output, index=False)
    print(f"  -> {args.output}  ({len(df):,} rows, {len(df.columns)} columns)")

    if args.log_output:
        write_raw_log(df, args.log_output)
        size_mb = Path(args.log_output).stat().st_size / 1e6
        print(f"  -> {args.log_output}  ({size_mb:,.1f} MB raw log)")

    write_ground_truth(args.rules_output)
    print(f"  -> {args.rules_output}  ({len(RULES)} rules)")
    print("Done.")


if __name__ == "__main__":
    main()
