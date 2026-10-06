#!/usr/bin/env python3
"""
Phase 1 - synthetic UVM log generator.

Produces a balanced pass/fail corpus of simulation logs in the grammar defined
by log_format.py, with deliberately embedded failure rules. The rules are
written to a ground-truth JSON so a downstream pipeline can be graded on
whether it rediscovers them.

Sampling is vectorised with numpy; only the final text rendering loops.

Usage
-----
    python -m uvm_intel.generate_logs --n-runs 50000 --parts 10

Every option defaults to the original corpus, so the command above still
reproduces the bundled sample byte for byte. The optional switches make the
data easier to learn from:

    --extra-deterministic   two more RTL-style bugs that always fail
    --build-fields          firmware / RTL / testbench versions, known before
                            the run starts, with rules tied to them
    --seeds-per-config K    run each sampled configuration K times
    --base-fail-prob P      floor failure rate of a clean config (noise)
    --rule-strength S       multiply every additive rule's effect
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

# ═══════════════════════════════════════════════════════════════════════════
# Configuration space
# ═══════════════════════════════════════════════════════════════════════════

TEST_NAMES = [
    "Back_To_Back_Program", "Random_Read", "Sequential_Write", "Mixed_RW",
    "Erase_Suspend", "Power_Cycle", "Garbage_Collect", "Read_Disturb",
]
CACHE_POLICIES = ["Adaptive", "WriteThrough", "WriteBack", "Disabled"]
ECC_MODES = ["BCH", "LDPC", "Disabled"]

# name -> (values, weights). Weights are deliberately lopsided.
CONFIG_SPACE: Dict[str, Any] = {
    "test_name":       (TEST_NAMES, [0.18, 0.16, 0.15, 0.14, 0.11, 0.09, 0.09, 0.08]),
    "cache_policy":    (CACHE_POLICIES, [0.32, 0.26, 0.28, 0.14]),
    "test_mode_enabled": ([0, 1], [0.72, 0.28]),
    "queue_depth":     ([1, 2, 4, 8, 16, 32, 64], [0.08, 0.12, 0.18, 0.22, 0.18, 0.14, 0.08]),
    "num_channels":    ([1, 2, 4, 8], [0.15, 0.30, 0.35, 0.20]),
    "num_planes":      ([1, 2, 4], [0.30, 0.45, 0.25]),
    "ecc_mode":        (ECC_MODES, [0.42, 0.40, 0.18]),
    "scrambler_enable": ([0, 1], [0.45, 0.55]),
    "burst_length":    ([4, 8, 16, 32, 64], [0.16, 0.24, 0.28, 0.20, 0.12]),
    "clock_freq_mhz":  ([400, 600, 800, 1000, 1200], [0.14, 0.22, 0.30, 0.22, 0.12]),
    "prefetch_depth":  (list(range(0, 17)), None),
}

# A clean configuration - no rule firing - must sit comfortably below the 2%
# ceiling the recommender optimises against, otherwise that constraint is
# unsatisfiable by construction. Failures come from the rules, not the floor.
BASE_FAIL_PROB = 0.012
EXEC_CEILING_MS = 2000.0          # simulation watchdog budget


# ═══════════════════════════════════════════════════════════════════════════
# Embedded failure rules
# ═══════════════════════════════════════════════════════════════════════════
#
# effect:
#   "set"  -> failure probability is forced to `value` (overrides additive)
#   "add"  -> `value` is added to the running failure probability
#
# deterministic=True marks an RTL-style bug whose error trace is byte-identical
# on every hit, regardless of seed. Everything else randomises addresses and
# cycle counts, so seed noise and real bugs are separable downstream.

RULES: List[Dict[str, Any]] = [
    {
        "id": "R1",
        "description": ("Back_To_Back_Program with Adaptive cache policy "
                        "overflows the write FIFO"),
        "conditions": [
            {"field": "test_name", "op": "==", "value": "Back_To_Back_Program"},
            {"field": "cache_policy", "op": "==", "value": "Adaptive"},
        ],
        "effect": "set", "value": 0.85,
        "error_tag": "FIFO_OVERFLOW", "deterministic": False,
    },
    {
        "id": "R2",
        "description": "Test mode raises failure probability across all runs",
        "conditions": [
            {"field": "test_mode_enabled", "op": "==", "value": 1},
        ],
        "effect": "add", "value": 0.35,
        "error_tag": None, "deterministic": False,
    },
    {
        "id": "R3",
        "description": "Deep queues with ECC disabled surface uncorrectable errors",
        "conditions": [
            {"field": "queue_depth", "op": ">=", "value": 32},
            {"field": "ecc_mode", "op": "==", "value": "Disabled"},
        ],
        "effect": "add", "value": 0.35,
        "error_tag": "ECC_UNCORRECTABLE", "deterministic": False,
    },
    {
        "id": "R4",
        "description": "Hot and undervolted NAND loses retention",
        "conditions": [
            {"field": "temperature_c", "op": ">", "value": 85.0},
            {"field": "voltage_mv", "op": "<", "value": 1100.0},
        ],
        "effect": "add", "value": 0.30,
        "error_tag": "RETENTION_FAIL", "deterministic": False,
    },
    {
        "id": "R5",
        "description": ("Deterministic RTL bug: 4-plane + 64-beat burst + "
                        "scrambler violates the protocol at a fixed address"),
        "conditions": [
            {"field": "num_planes", "op": "==", "value": 4},
            {"field": "burst_length", "op": "==", "value": 64},
            {"field": "scrambler_enable", "op": "==", "value": 1},
        ],
        "effect": "set", "value": 0.98,
        "error_tag": "PROTOCOL_VIOLATION", "deterministic": True,
    },
    {
        "id": "R6",
        "description": "High clock with deep prefetch starves the monitor and times out",
        "conditions": [
            {"field": "clock_freq_mhz", "op": ">=", "value": 1000},
            {"field": "prefetch_depth", "op": ">", "value": 8},
        ],
        "effect": "add", "value": 0.30,
        "error_tag": "TIMEOUT", "deterministic": False,
    },
    {
        "id": "R7",
        "description": ("Disabled cache with a deep queue loses write ordering "
                        "and mismatches the scoreboard"),
        "conditions": [
            {"field": "cache_policy", "op": "==", "value": "Disabled"},
            {"field": "queue_depth", "op": ">=", "value": 16},
        ],
        "effect": "add", "value": 0.30,
        "error_tag": "DATA_MISMATCH", "deterministic": False,
    },
]

# Byte-identical trace each deterministic rule prints, keyed by rule id.
DETERMINISTIC_TRACES = {
    "R5": ("Illegal burst termination on plane 3: beat=64 addr=0x0000c3f0 "
           "expected_ack=1 observed_ack=0"),
    "R8": ("Unknown opcode 0x7f in LDPC single-plane decode path: "
           "slot=63 addr=0x0001fe00"),
    "R9": ("Bad-block table walk hit reserved entry 0xffff during GC on "
           "channel 7 addr=0x00a0b000"),
}

# --extra-deterministic: more RTL-style bugs. A config that matches always
# fails the same way, so these are the easiest signal a model can learn.
EXTRA_DETERMINISTIC_RULES: List[Dict[str, Any]] = [
    {
        "id": "R8",
        "description": ("Deterministic RTL bug: LDPC on a single plane with "
                        "queue depth 64 decodes an illegal opcode"),
        "conditions": [
            {"field": "ecc_mode", "op": "==", "value": "LDPC"},
            {"field": "num_planes", "op": "==", "value": 1},
            {"field": "queue_depth", "op": "==", "value": 64},
        ],
        "effect": "set", "value": 0.97,
        "error_tag": "CMD_DECODE_ERROR", "deterministic": True,
    },
    {
        "id": "R9",
        "description": ("Deterministic RTL bug: Garbage_Collect across 8 "
                        "channels walks a corrupt bad-block table"),
        "conditions": [
            {"field": "test_name", "op": "==", "value": "Garbage_Collect"},
            {"field": "num_channels", "op": "==", "value": 8},
        ],
        "effect": "set", "value": 0.96,
        "error_tag": "BAD_BLOCK_MAP", "deterministic": True,
    },
]

# --build-fields: versions fixed before the run starts. Fair model inputs
# (no leakage), and each carries a regression the model can find.
BUILD_SPACE: Dict[str, Any] = {
    "firmware_version":  (["fw_3.1.0", "fw_3.2.0", "fw_3.2.1", "fw_4.0.0-rc1"],
                          [0.25, 0.30, 0.30, 0.15]),
    "rtl_build":         (["rtl_2024.08", "rtl_2024.10", "rtl_2024.12"],
                          [0.30, 0.40, 0.30]),
    "testbench_version": (["tb_1.4", "tb_1.5"], [0.40, 0.60]),
}

BUILD_RULES: List[Dict[str, Any]] = [
    {
        "id": "R10",
        "description": "Release-candidate firmware 4.0.0-rc1 hangs the command queue",
        "conditions": [
            {"field": "firmware_version", "op": "==", "value": "fw_4.0.0-rc1"},
        ],
        "effect": "add", "value": 0.40,
        "error_tag": "TIMEOUT", "deterministic": False,
    },
    {
        "id": "R11",
        "description": "RTL build 2024.12 regressed the BCH decoder",
        "conditions": [
            {"field": "rtl_build", "op": "==", "value": "rtl_2024.12"},
            {"field": "ecc_mode", "op": "==", "value": "BCH"},
        ],
        "effect": "add", "value": 0.35,
        "error_tag": "ECC_UNCORRECTABLE", "deterministic": False,
    },
    {
        "id": "R12",
        "description": "Testbench 1.4 has a stale power-cycle assertion",
        "conditions": [
            {"field": "testbench_version", "op": "==", "value": "tb_1.4"},
            {"field": "test_name", "op": "==", "value": "Power_Cycle"},
        ],
        "effect": "add", "value": 0.45,
        "error_tag": "ASSERTION_FAIL", "deterministic": False,
    },
]

# Failures no rule claimed - the "random seed noise" population.
NOISE_TAGS = ["DATA_MISMATCH", "ASSERTION_FAIL"]
NOISE_WEIGHTS = [0.6, 0.4]

_OPS = {
    "==": lambda s, v: s == v, "!=": lambda s, v: s != v,
    ">": lambda s, v: s > v, ">=": lambda s, v: s >= v,
    "<": lambda s, v: s < v, "<=": lambda s, v: s <= v,
}


# ═══════════════════════════════════════════════════════════════════════════
# Sampling
# ═══════════════════════════════════════════════════════════════════════════

def active_rules(extra_deterministic: bool = False,
                 build_fields: bool = False) -> List[Dict[str, Any]]:
    """The rule set a corpus is generated with."""
    rules = list(RULES)
    if extra_deterministic:
        rules += EXTRA_DETERMINISTIC_RULES
    if build_fields:
        rules += BUILD_RULES
    return rules


def sample_configs(n: int, rng: np.random.Generator,
                   build_fields: bool = False,
                   seeds_per_config: int = 1) -> Dict[str, np.ndarray]:
    """Draw the full configuration matrix, vectorised.

    With seeds_per_config K, n/K configurations are drawn and each is run K
    times with a fresh seed, so the same settings appear with several
    outcomes and the model can estimate a failure rate instead of a coin flip.
    """
    if seeds_per_config > 1:
        n_cfg = -(-n // seeds_per_config)
        base = sample_configs(n_cfg, rng, build_fields)
        cols = {k: np.repeat(v, seeds_per_config)[:n]
                for k, v in base.items() if k != "seed"}
        cols["seed"] = rng.integers(0, 2**31 - 1, size=n)
        return cols

    cols: Dict[str, np.ndarray] = {}
    for name, (values, weights) in CONFIG_SPACE.items():
        p = np.asarray(weights, float) / np.sum(weights) if weights else None
        cols[name] = rng.choice(values, size=n, p=p)

    # Continuous environment
    cols["voltage_mv"] = np.round(
        np.clip(rng.normal(1160, 45, n), 1050, 1250), 1)
    cols["temperature_c"] = np.round(
        np.clip(rng.normal(62, 15, n), 25, 95), 1)
    cols["error_injection_rate"] = np.round(rng.uniform(0.0, 0.05, n), 4)
    cols["seed"] = rng.integers(0, 2**31 - 1, size=n)

    # Drawn after everything else so the default corpus is unchanged.
    if build_fields:
        for name, (values, weights) in BUILD_SPACE.items():
            p = np.asarray(weights, float) / np.sum(weights)
            cols[name] = rng.choice(values, size=n, p=p)
    return cols


def build_mask(cols: Dict[str, np.ndarray], conditions: List[Dict]) -> np.ndarray:
    mask = np.ones(len(next(iter(cols.values()))), dtype=bool)
    for c in conditions:
        mask &= _OPS[c["op"]](cols[c["field"]], c["value"])
    return mask


def apply_rules(cols: Dict[str, np.ndarray], n: int, rng: np.random.Generator,
                rules: List[Dict[str, Any]] = None,
                base_fail_prob: float = BASE_FAIL_PROB,
                rule_strength: float = 1.0):
    """Resolve failure probability, verdict and error tag for every run.

    The returned `deterministic` array holds the fixed trace of the
    deterministic rule that claimed a run, or "" when none did.
    """
    rules = RULES if rules is None else rules
    prob = np.full(n, base_fail_prob)
    tag = np.full(n, "", dtype=object)
    tag_priority = np.zeros(n)
    deterministic = np.full(n, "", dtype=object)
    fired: Dict[str, np.ndarray] = {}

    # Additive rules first, then "set" rules override.
    for rule in rules:
        m = build_mask(cols, rule["conditions"])
        fired[rule["id"]] = m
        if rule["effect"] == "add":
            prob[m] += rule["value"] * rule_strength

    for rule in rules:
        if rule["effect"] == "set":
            prob[fired[rule["id"]]] = rule["value"]

    prob = np.clip(prob, 0.001, 0.99)
    is_fail = rng.random(n) < prob

    # Attribute an error tag: highest-value rule that fired on a failing row.
    for rule in rules:
        if not rule["error_tag"]:
            continue
        m = fired[rule["id"]] & is_fail & (rule["value"] > tag_priority)
        tag[m] = rule["error_tag"]
        tag_priority[m] = rule["value"]
        deterministic[m] = (DETERMINISTIC_TRACES[rule["id"]]
                            if rule["deterministic"] else "")

    unclaimed = is_fail & (tag == "")
    k = int(unclaimed.sum())
    if k:
        tag[unclaimed] = rng.choice(NOISE_TAGS, size=k, p=NOISE_WEIGHTS)

    return prob, is_fail, tag, deterministic, fired


def compute_metrics(cols, is_fail, tag, rng, n):
    """Execution time and throughput, coupled to config and failure mode."""
    # Baseline duration shrinks with parallelism, grows with work per run.
    work = (cols["queue_depth"] * cols["burst_length"]).astype(float)
    parallel = (cols["num_channels"] * cols["num_planes"]).astype(float)
    speed = cols["clock_freq_mhz"].astype(float) / 800.0
    base = 120.0 * (work / 256.0) / (parallel ** 0.6) / speed
    exec_ms = base * rng.lognormal(0.0, 0.35, n)

    # Failure modes have distinct timing profiles.
    exec_ms[tag == "TIMEOUT"] = EXEC_CEILING_MS * rng.uniform(0.98, 1.0,
                                                              int((tag == "TIMEOUT").sum()))
    for t, (lo, hi) in {
        "FIFO_OVERFLOW": (1.2, 1.8), "ECC_UNCORRECTABLE": (1.1, 1.5),
        "RETENTION_FAIL": (1.0, 1.4), "PROTOCOL_VIOLATION": (0.15, 0.35),
        "DATA_MISMATCH": (0.30, 0.70), "ASSERTION_FAIL": (0.20, 0.55),
    }.items():
        m = tag == t
        k = int(m.sum())
        if k:
            exec_ms[m] *= rng.uniform(lo, hi, k)

    nt = tag != "TIMEOUT"
    exec_ms[nt] = EXEC_CEILING_MS * np.tanh(exec_ms[nt] / EXEC_CEILING_MS)
    exec_ms = np.maximum(exec_ms, 1.0)

    # Throughput: bytes moved over elapsed time, degraded when the run fails.
    bytes_moved = work * parallel * 512.0
    tp = bytes_moved / (exec_ms / 1000.0) / 1e6 * rng.uniform(0.92, 1.08, n)
    tp[is_fail] *= rng.uniform(0.25, 0.75, int(is_fail.sum()))
    tp = tp / (1.0 + tp / 8000.0)

    cycles = (exec_ms / 1000.0 * cols["clock_freq_mhz"] * 1e6).astype(np.int64)
    return np.round(exec_ms, 2), np.round(tp, 2), cycles


# ═══════════════════════════════════════════════════════════════════════════
# Error trace rendering
# ═══════════════════════════════════════════════════════════════════════════

def _error_lines(tag, det, t_ns, rng, cfg) -> List[str]:
    """Render the UVM_ERROR / UVM_FATAL lines for one failing run."""
    comp = ERROR_COMPONENT[tag]
    if det:
        # Deterministic RTL bug - byte-identical every time it fires.
        return [
            f"UVM_ERROR @ {t_ns} ns: {comp} [{tag}] {det}",
            f"UVM_ERROR @ {t_ns + 20} ns: {comp} [{tag}] {det}",
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
    """Render one complete run block."""
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
        if det[i] or tag[i] in ("TIMEOUT", "PROTOCOL_VIOLATION"):
            out.append(f"UVM_FATAL @ {t_end} ns: uvm_test_top [TEST_ABORT] "
                       f"Aborting on unrecoverable {tag[i]}")
    else:
        out.append(f"UVM_INFO @ {max(t_end - 1000, 2000)} ns: "
                   f"uvm_test_top.env.sb [SB_OK] All transactions matched")

    n_fatal = 1 if (is_fail[i] and (det[i] or tag[i] in ("TIMEOUT", "PROTOCOL_VIOLATION"))) else 0
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

def _oracle_auc(prob: np.ndarray, is_fail: np.ndarray) -> Any:
    """ROC-AUC of the generator's own failure probabilities: the best any
    model could score on this corpus, since the rest is pure chance."""
    if is_fail.all() or not is_fail.any():
        return None
    from sklearn.metrics import roc_auc_score
    return round(float(roc_auc_score(is_fail, prob)), 4)


def generate(n_runs: int, seed: int, out_dir: str, parts: int,
             extra_deterministic: bool = False, build_fields: bool = False,
             seeds_per_config: int = 1, base_fail_prob: float = BASE_FAIL_PROB,
             rule_strength: float = 1.0) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    rules = active_rules(extra_deterministic, build_fields)
    cols = sample_configs(n_runs, rng, build_fields, seeds_per_config)
    prob, is_fail, tag, det, fired = apply_rules(
        cols, n_runs, rng, rules, base_fail_prob, rule_strength)
    exec_ms, tp, cycles = compute_metrics(cols, is_fail, tag, rng, n_runs)

    os.makedirs(out_dir, exist_ok=True)
    per_part = -(-n_runs // parts)
    written = []
    for p in range(parts):
        lo, hi = p * per_part, min((p + 1) * per_part, n_runs)
        if lo >= hi:
            break
        path = os.path.join(out_dir, f"uvm_runs_part{p + 1:02d}.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(
                render_run(i, cols, is_fail, tag, det, exec_ms, tp, cycles, rng)
                for i in range(lo, hi)))
        written.append((path, hi - lo))

    # Ground truth for grading the downstream pipeline.
    gt_rules = []
    for r in rules:
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
            "base_fail_prob": base_fail_prob,
            "observed_fail_rate": round(float(is_fail.mean()), 4),
            "exec_ceiling_ms": EXEC_CEILING_MS,
            "options": {
                "extra_deterministic": extra_deterministic,
                "build_fields": build_fields,
                "seeds_per_config": seeds_per_config,
                "rule_strength": rule_strength,
            },
            "distinct_configs": -(-n_runs // max(seeds_per_config, 1)),
            "oracle_roc_auc": _oracle_auc(prob, is_fail),
        },
        "rules": gt_rules,
        "error_tag_distribution": {str(t): int(c) for t, c in zip(tags, counts)},
        "files": [{"path": p, "runs": n} for p, n in written],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic UVM logs.")
    ap.add_argument("--n-runs", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--parts", type=int, default=10)
    ap.add_argument("--out-dir", default="data/uvm_logs")
    ap.add_argument("--ground-truth", default="data/uvm_ground_truth.json")
    ap.add_argument("--extra-deterministic", action="store_true",
                    help="add two always-failing RTL bugs (R8, R9)")
    ap.add_argument("--build-fields", action="store_true",
                    help="add firmware/RTL/testbench versions and their rules")
    ap.add_argument("--seeds-per-config", type=int, default=1,
                    help="run each configuration this many times")
    ap.add_argument("--base-fail-prob", type=float, default=BASE_FAIL_PROB,
                    help="failure rate of a config no rule touches")
    ap.add_argument("--rule-strength", type=float, default=1.0,
                    help="multiplier on every additive rule")
    args = ap.parse_args()

    print(f"Generating {args.n_runs:,} UVM runs -> {args.out_dir} ...")
    gt = generate(args.n_runs, args.seed, args.out_dir, args.parts,
                  args.extra_deterministic, args.build_fields,
                  args.seeds_per_config, args.base_fail_prob,
                  args.rule_strength)

    os.makedirs(os.path.dirname(args.ground_truth) or ".", exist_ok=True)
    with open(args.ground_truth, "w") as fh:
        json.dump(gt, fh, indent=2)

    md = gt["metadata"]
    print(f"  overall fail rate: {md['observed_fail_rate']:.3f}")
    print(f"  best possible ROC-AUC: {md['oracle_roc_auc']}")
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
