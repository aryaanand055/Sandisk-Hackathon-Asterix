#!/usr/bin/env python3
"""
Phase 1 (alternate rule set) - synthetic UVM log generator.

A standalone sibling of generate_logs.py that shares the same log grammar,
configuration space, and metric model, but injects five different failure
rules (N1-N5) touching a different subset of the configuration space:

    N1  num_channels=1 & queue_depth>=32        -> FIFO_OVERFLOW
    N2  scrambler_enable=0 & error_inj>0.03      -> DATA_MISMATCH
    N3  test_name=Read_Disturb & ecc_mode=BCH    -> RETENTION_FAIL
    N4  burst_length=4 & num_planes=1 & clk<=400 -> ASSERTION_FAIL (deterministic)
    N5  test_mode_enabled=1 & prefetch_depth>=12 -> TIMEOUT

This file does not import or modify generate_logs.py's RULES, apply_rules,
or render_run - those are rule-set-specific. It reuses only the genuinely
generic pieces (config sampling, metric model, error-message templates,
log rendering shell) via local copies so the deterministic bug's message
text stays truthful to ITS OWN trigger condition rather than borrowing the
original ruleset's hardcoded "beat=64 / plane 3" text.

Usage
-----
    python -m uvm_intel.generate_logs_altset --n-runs 50000 --parts 10
"""

import argparse
import json
import os
from typing import Any, Dict, List

import numpy as np

from .log_format import (
    BANNER, CONFIG_CLOSE, CONFIG_OPEN, ERROR_COMPONENT, METRICS_CLOSE,
    METRICS_OPEN, RUN_SEPARATOR, SUMMARY_HEADER, VERDICT_FAIL, VERDICT_PASS,
)
from .generate_logs import (
    CONFIG_SPACE, EXEC_CEILING_MS, NOISE_TAGS, NOISE_WEIGHTS,
    build_mask, compute_metrics, sample_configs,
)

# A clean configuration must sit below the 2% risk ceiling the dashboard's
# recommender optimises against - same rationale as generate_logs.py.
BASE_FAIL_PROB = 0.012


# ═══════════════════════════════════════════════════════════════════════════
# Alternate failure rules
# ═══════════════════════════════════════════════════════════════════════════

RULES: List[Dict[str, Any]] = [
    {
        "id": "N1",
        "description": (
            "Single channel cannot drain a deep queue fast enough, "
            "overflowing the write FIFO"
        ),
        "conditions": [
            {"field": "num_channels", "op": "==", "value": 1},
            {"field": "queue_depth", "op": ">=", "value": 32},
        ],
        "effect": "set", "value": 0.75,
        "error_tag": "FIFO_OVERFLOW", "deterministic": False,
    },
    {
        "id": "N2",
        "description": (
            "Disabled scrambler surfaces injected bit errors as raw "
            "scoreboard mismatches"
        ),
        "conditions": [
            {"field": "scrambler_enable", "op": "==", "value": 0},
            {"field": "error_injection_rate", "op": ">", "value": 0.03},
        ],
        "effect": "add", "value": 0.30,
        "error_tag": "DATA_MISMATCH", "deterministic": False,
    },
    {
        "id": "N3",
        "description": (
            "BCH correction is not strong enough for a read-disturb-heavy "
            "workload"
        ),
        "conditions": [
            {"field": "test_name", "op": "==", "value": "Read_Disturb"},
            {"field": "ecc_mode", "op": "==", "value": "BCH"},
        ],
        "effect": "add", "value": 0.35,
        "error_tag": "RETENTION_FAIL", "deterministic": False,
    },
    {
        "id": "N4",
        "description": (
            "Deterministic RTL bug: a short burst on a single plane at low "
            "clock trips a fixed timing assertion"
        ),
        "conditions": [
            {"field": "burst_length", "op": "==", "value": 4},
            {"field": "num_planes", "op": "==", "value": 1},
            {"field": "clock_freq_mhz", "op": "<=", "value": 400},
        ],
        "effect": "set", "value": 0.95,
        "error_tag": "ASSERTION_FAIL", "deterministic": True,
    },
    {
        "id": "N5",
        "description": (
            "Test-mode instrumentation overhead plus deep prefetch starves "
            "the watchdog monitor"
        ),
        "conditions": [
            {"field": "test_mode_enabled", "op": "==", "value": 1},
            {"field": "prefetch_depth", "op": ">=", "value": 12},
        ],
        "effect": "add", "value": 0.28,
        "error_tag": "TIMEOUT", "deterministic": False,
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Rule application (mirrors generate_logs.apply_rules, bound to local RULES)
# ═══════════════════════════════════════════════════════════════════════════

def apply_rules(cols: Dict[str, np.ndarray], n: int, rng: np.random.Generator):
    """Resolve failure probability, verdict and error tag for every run."""
    prob = np.full(n, BASE_FAIL_PROB)
    tag = np.full(n, "", dtype=object)
    tag_priority = np.zeros(n)
    deterministic = np.zeros(n, dtype=bool)
    fired: Dict[str, np.ndarray] = {}

    for rule in RULES:
        m = build_mask(cols, rule["conditions"])
        fired[rule["id"]] = m
        if rule["effect"] == "add":
            prob[m] += rule["value"]

    for rule in RULES:
        if rule["effect"] == "set":
            prob[fired[rule["id"]]] = rule["value"]

    prob = np.clip(prob, 0.001, 0.99)
    is_fail = rng.random(n) < prob

    for rule in RULES:
        if not rule["error_tag"]:
            continue
        m = fired[rule["id"]] & is_fail & (rule["value"] > tag_priority)
        tag[m] = rule["error_tag"]
        tag_priority[m] = rule["value"]
        if rule["deterministic"]:
            deterministic[m] = True

    unclaimed = is_fail & (tag == "")
    k = int(unclaimed.sum())
    if k:
        tag[unclaimed] = rng.choice(NOISE_TAGS, size=k, p=NOISE_WEIGHTS)

    return prob, is_fail, tag, deterministic, fired


# ═══════════════════════════════════════════════════════════════════════════
# Error trace rendering
# ═══════════════════════════════════════════════════════════════════════════
#
# Local copy of the per-tag message templates. Kept separate from
# generate_logs.py so the deterministic branch can describe N4's ACTUAL
# trigger (burst_length=4, num_planes=1, low clock) instead of the other
# ruleset's fixed "beat=64 / plane 3" text, which would contradict this
# file's own CONFIG values if reused unchanged.

def _error_lines(tag, det, t_ns, rng, cfg) -> List[str]:
    comp = ERROR_COMPONENT[tag]
    if det:
        # N4 - deterministic RTL bug: identical text on every hit, regardless
        # of seed, because the trigger is purely structural (burst/plane/
        # clock), not data-dependent.
        return [
            f"UVM_ERROR @ {t_ns} ns: {comp} [ASSERTION_FAIL] "
            f"Assertion 'a_burst_beat_align' failed: burst_len=4 plane=0 "
            f"clk_mhz=400 beat=3 addr=0x00003a10 expected=IDLE observed=ACTIVE",
            f"UVM_ERROR @ {t_ns + 15} ns: {comp} [ASSERTION_FAIL] "
            f"Assertion 'a_burst_beat_align' failed: burst_len=4 plane=0 "
            f"clk_mhz=400 beat=3 addr=0x00003a10 expected=IDLE observed=ACTIVE",
        ]

    addr = int(rng.integers(0, 2**28))
    templates = {
        "FIFO_OVERFLOW": (
            f"Write to full FIFO: fifo_id={rng.integers(0, 8)} "
            f"depth={cfg['queue_depth']} wr_ptr=0x{rng.integers(0, 256):02x} "
            f"rd_ptr=0x{rng.integers(0, 256):02x} addr=0x{addr:08x}"),
        "ECC_UNCORRECTABLE": (
            f"Uncorrectable ECC at addr=0x{addr:08x} "
            f"syndrome=0x{rng.integers(0, 2**16):04x} "
            f"bits_flipped={rng.integers(9, 24)}"),
        "TIMEOUT": (
            f"Response watchdog expired after {rng.integers(4000, 9000)} cycles "
            f"on tag={rng.integers(0, 64)} addr=0x{addr:08x}"),
        "DATA_MISMATCH": (
            f"Scoreboard compare failed at addr=0x{addr:08x} "
            f"expected=0x{rng.integers(0, 2**32):08x} "
            f"observed=0x{rng.integers(0, 2**32):08x}"),
        "PROTOCOL_VIOLATION": (
            f"Illegal transition on channel {rng.integers(0, 8)} "
            f"state=0x{rng.integers(0, 16):x} addr=0x{addr:08x}"),
        "ASSERTION_FAIL": (
            f"Assertion 'a_no_overlap' failed at addr=0x{addr:08x} "
            f"cycle={rng.integers(1000, 90000)}"),
        "RETENTION_FAIL": (
            f"Retention check failed block={rng.integers(0, 4096)} "
            f"page={rng.integers(0, 256)} raw_ber={rng.uniform(0.01, 0.09):.4f} "
            f"addr=0x{addr:08x}"),
    }
    lines = [f"UVM_ERROR @ {t_ns} ns: {comp} [{tag}] {templates[tag]}"]
    for extra in range(int(rng.integers(0, 3))):
        lines.append(
            f"UVM_ERROR @ {t_ns + (extra + 1) * 137} ns: {comp} [{tag}] "
            f"{templates[tag]}")
    return lines


def render_run(i, cols, is_fail, tag, det, exec_ms, tp, cycles, rng) -> str:
    """Render one complete run block (shell identical to generate_logs.py)."""
    run_id = f"RUN-{i + 1:06d}"
    cfg = {k: (v[i].item() if hasattr(v[i], "item") else v[i])
           for k, v in cols.items()}
    cfg_json = {"run_id": run_id, **cfg}

    t_end = int(exec_ms[i] * 1000)
    out = [
        RUN_SEPARATOR,
        f"{BANNER}{run_id}",
        RUN_SEPARATOR,
        CONFIG_OPEN,
        json.dumps(cfg_json, separators=(",", ":")),
        CONFIG_CLOSE,
        f"UVM_INFO @ 0 ns: reporter [RNTST] Running test "
        f"{cfg['test_name'].lower()}_test...",
        f"UVM_INFO @ 500 ns: uvm_test_top.env [BUILD] cache_policy="
        f"{cfg['cache_policy']} qd={cfg['queue_depth']} ecc={cfg['ecc_mode']}",
        f"UVM_INFO @ 1500 ns: uvm_test_top.env.agent.drv [DRV_START] "
        f"Driving {cfg['queue_depth'] * 16} transactions on "
        f"{cfg['num_channels']} channels",
    ]

    n_err = 0
    if is_fail[i]:
        elines = _error_lines(tag[i], det[i], max(t_end - 4000, 2000), rng, cfg)
        out.extend(elines)
        n_err = len(elines)
        if tag[i] in ("TIMEOUT", "PROTOCOL_VIOLATION"):
            out.append(f"UVM_FATAL @ {t_end} ns: uvm_test_top [TEST_ABORT] "
                       f"Aborting on unrecoverable {tag[i]}")
    else:
        out.append(f"UVM_INFO @ {max(t_end - 1000, 2000)} ns: "
                   f"uvm_test_top.env.sb [SB_OK] All transactions matched")

    n_fatal = 1 if (is_fail[i] and tag[i] in ("TIMEOUT", "PROTOCOL_VIOLATION")) else 0
    out += [
        METRICS_OPEN,
        json.dumps({
            "execution_time_ms": float(exec_ms[i]),
            "throughput_mbps": float(tp[i]),
            "cycles": int(cycles[i]),
            "uvm_error_count": n_err,
            "uvm_fatal_count": n_fatal,
        }, separators=(",", ":")),
        METRICS_CLOSE,
        SUMMARY_HEADER,
        f"UVM_INFO    : {4 + n_err:>4d}",
        f"UVM_WARNING : {0:>4d}",
        f"UVM_ERROR   : {n_err:>4d}",
        f"UVM_FATAL   : {n_fatal:>4d}",
        VERDICT_FAIL if is_fail[i] else VERDICT_PASS,
        "",
    ]
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def generate(n_runs: int, seed: int, out_dir: str, parts: int) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    cols = sample_configs(n_runs, rng)
    prob, is_fail, tag, det, fired = apply_rules(cols, n_runs, rng)
    exec_ms, tp, cycles = compute_metrics(cols, is_fail, tag, rng, n_runs)

    os.makedirs(out_dir, exist_ok=True)
    per_part = -(-n_runs // parts)
    written = []
    for p in range(parts):
        lo, hi = p * per_part, min((p + 1) * per_part, n_runs)
        if lo >= hi:
            break
        path = os.path.join(out_dir, f"uvm_runs_altset_part{p + 1:02d}.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(
                render_run(i, cols, is_fail, tag, det, exec_ms, tp, cycles, rng)
                for i in range(lo, hi)))
        written.append((path, hi - lo))

    gt_rules = []
    for r in RULES:
        m = fired[r["id"]]
        n_m = int(m.sum())
        gt_rules.append({
            **{k: v for k, v in r.items()},
            "observed": {
                "rows_matched": n_m,
                "match_share": round(n_m / n_runs, 4),
                "fail_rate_when_fired": round(float(is_fail[m].mean()), 4) if n_m else None,
                "fail_rate_otherwise": round(float(is_fail[~m].mean()), 4),
                "lift": (round(float(is_fail[m].mean() / is_fail[~m].mean()), 3)
                         if n_m and is_fail[~m].mean() else None),
            },
        })

    tags, counts = np.unique(tag[is_fail], return_counts=True)
    return {
        "metadata": {
            "n_runs": n_runs, "seed": seed, "parts": len(written),
            "base_fail_prob": BASE_FAIL_PROB,
            "observed_fail_rate": round(float(is_fail.mean()), 4),
            "exec_ceiling_ms": EXEC_CEILING_MS,
            "rule_set": "altset (N1-N5)",
        },
        "rules": gt_rules,
        "error_tag_distribution": {str(t): int(c) for t, c in zip(tags, counts)},
        "files": [{"path": p, "runs": n} for p, n in written],
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate synthetic UVM logs using the alternate N1-N5 rule set."
    )
    ap.add_argument("--n-runs", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--parts", type=int, default=10)
    ap.add_argument("--out-dir", default="data/uvm_logs_altset")
    ap.add_argument("--ground-truth", default="data/uvm_ground_truth_altset.json")
    args = ap.parse_args()

    print(f"Generating {args.n_runs:,} UVM runs (alternate rule set) "
          f"-> {args.out_dir} ...")
    gt = generate(args.n_runs, args.seed, args.out_dir, args.parts)

    os.makedirs(os.path.dirname(args.ground_truth) or ".", exist_ok=True)
    with open(args.ground_truth, "w") as fh:
        json.dump(gt, fh, indent=2)

    md = gt["metadata"]
    print(f"  overall fail rate: {md['observed_fail_rate']:.3f}")
    print(f"  error tags: {gt['error_tag_distribution']}")
    for r in gt["rules"]:
        o = r["observed"]
        print(f"  [{r['id']}] n={o['rows_matched']:>6,}  "
              f"fail_fired={o['fail_rate_when_fired']}  "
              f"vs {o['fail_rate_otherwise']}  lift={o['lift']}")
    total = sum(f["runs"] for f in gt["files"])
    print(f"  -> {len(gt['files'])} files, {total:,} runs")
    print(f"  -> {args.ground_truth}")


if __name__ == "__main__":
    main()
