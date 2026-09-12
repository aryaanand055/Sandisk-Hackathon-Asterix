#!/usr/bin/env python3
"""
Structured multi-file verification dataset generator.

Emits the input-file set described in the ingestion spec:

    config.csv          configuration knobs, one row per run
    randomization.csv   seed + randomized stimulus attributes, one row per run
    transactions.csv    DUT inputs / DUT outputs / protocol fields, many rows per run
    telemetry.csv       simulator + environment telemetry, one row per run
    outcomes.csv        raw PASS / FAIL verdict and error identity, one row per run
    uvm.log             the same runs rendered in the legacy UVM log grammar
    registers.csv       register / memory access dump (optional category)
    waveforms/*.vcd     internal RTL signals for a few runs (optional category)

Every profile embeds a documented set of causal rules. The rules are evaluated
over the *union* of config + randomization + telemetry fields, so a correct
ingestion layer has to join the files to recover them. After generation the
observed lift of each rule is measured and written to ground_truth.json.

Nothing derived (latency, failure probability, risk, correlation, importance)
is written to any input file. Only raw measurements.

Usage
-----
    python tools/generate_structured_dataset.py --all
    python tools/generate_structured_dataset.py --profile nvme_axi --n-runs 50000
"""

import argparse
import json
import os
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════
# Log grammar (identical to uvm_intel/log_format.py so the legacy parser reads it)
# ═══════════════════════════════════════════════════════════════════════════

RUN_SEPARATOR = "=" * 64
BANNER = "UVM SIMULATION LOG :: "
CONFIG_OPEN, CONFIG_CLOSE = "[CONFIG]", "[/CONFIG]"
METRICS_OPEN, METRICS_CLOSE = "[METRICS]", "[/METRICS]"
SUMMARY_HEADER = "--- UVM Report Summary ---"
VERDICT_PASS, VERDICT_FAIL = "** TEST PASSED **", "** TEST FAILED **"

_OPS = {
    "==": lambda s, v: s == v, "!=": lambda s, v: s != v,
    ">": lambda s, v: s > v, ">=": lambda s, v: s >= v,
    "<": lambda s, v: s < v, "<=": lambda s, v: s <= v,
}


def _pick(rng, values, weights, n):
    p = np.asarray(weights, float) / np.sum(weights) if weights else None
    return rng.choice(values, size=n, p=p)


def _end_ns(exec_ms):
    """Simulated end-of-run timestamp, in real nanoseconds.

    Every timestamp written to uvm.log, transactions.csv and registers.csv is
    derived from this, so 1 ms of execution_time_ms is exactly 1e6 ns and the
    timestamps reconcile with sim_cycles at the configured clock.
    """
    return max(int(round(float(exec_ms) * 1e6)), 5000)


# ═══════════════════════════════════════════════════════════════════════════
# PROFILE A - nvme_axi : SSD controller behind an AXI4 host interface
# ═══════════════════════════════════════════════════════════════════════════

A_TESTS = ["Back_To_Back_Program", "Random_Read", "Sequential_Write", "Mixed_RW",
           "Erase_Suspend", "Power_Cycle", "Garbage_Collect", "Read_Disturb"]

A_ERROR_COMPONENT = {
    "FIFO_OVERFLOW":      "uvm_test_top.env.sb",
    "ECC_UNCORRECTABLE":  "uvm_test_top.env.ecc_mon",
    "TIMEOUT":            "uvm_test_top.env.axi_agent.mon",
    "DATA_MISMATCH":      "uvm_test_top.env.sb",
    "PROTOCOL_VIOLATION": "uvm_test_top.env.axi_agent.protocol_chk",
    "ASSERTION_FAIL":     "uvm_test_top.dut_wrapper",
    "RETENTION_FAIL":     "uvm_test_top.env.nand_model",
    "THERMAL_SHUTDOWN":   "uvm_test_top.env.pmu_mon",
}

A_ERROR_CODE = {
    "FIFO_OVERFLOW": "E_FIFO_0x21", "ECC_UNCORRECTABLE": "E_ECC_0x33",
    "TIMEOUT": "E_TMO_0x40", "DATA_MISMATCH": "E_CMP_0x11",
    "PROTOCOL_VIOLATION": "E_PROT_0x52", "ASSERTION_FAIL": "E_ASRT_0x60",
    "RETENTION_FAIL": "E_RET_0x71", "THERMAL_SHUTDOWN": "E_THRM_0x80",
}

A_RULES: List[Dict[str, Any]] = [
    {"id": "A1",
     "description": "Back_To_Back_Program on the Adaptive cache policy overruns the write FIFO",
     "files": ["config.csv"],
     "conditions": [{"field": "test_name", "op": "==", "value": "Back_To_Back_Program"},
                    {"field": "cache_policy", "op": "==", "value": "Adaptive"}],
     "effect": "set", "value": 0.85,
     "error_tag": "FIFO_OVERFLOW", "deterministic": False},
    {"id": "A2",
     "description": "Test mode raises failure probability across every run",
     "files": ["config.csv"],
     "conditions": [{"field": "test_mode_enabled", "op": "==", "value": 1}],
     "effect": "add", "value": 0.35,
     "error_tag": None, "deterministic": False},
    {"id": "A3",
     "description": "Deep queues with ECC disabled surface uncorrectable bit errors",
     "files": ["config.csv"],
     "conditions": [{"field": "queue_depth", "op": ">=", "value": 32},
                    {"field": "ecc_mode", "op": "==", "value": "Disabled"}],
     "effect": "add", "value": 0.32,
     "error_tag": "ECC_UNCORRECTABLE", "deterministic": False},
    {"id": "A4",
     "description": "Hot and undervolted NAND loses charge retention "
                    "(requires joining config.csv with telemetry.csv)",
     "files": ["telemetry.csv"],
     "conditions": [{"field": "temperature_c", "op": ">", "value": 80.0},
                    {"field": "voltage_mv", "op": "<", "value": 1120.0}],
     "effect": "add", "value": 0.30,
     "error_tag": "RETENTION_FAIL", "deterministic": False},
    {"id": "A5",
     "description": "Deterministic RTL bug: 4 planes + 64-beat burst + scrambler "
                    "terminates the AXI burst illegally at a fixed address",
     "files": ["config.csv"],
     "conditions": [{"field": "num_planes", "op": "==", "value": 4},
                    {"field": "burst_length", "op": "==", "value": 64},
                    {"field": "scrambler_enable", "op": "==", "value": 1}],
     "effect": "set", "value": 0.97,
     "error_tag": "PROTOCOL_VIOLATION", "deterministic": True},
    {"id": "A6",
     "description": "High clock with deep prefetch starves the monitor and trips the watchdog",
     "files": ["config.csv"],
     "conditions": [{"field": "clock_freq_mhz", "op": ">=", "value": 1000},
                    {"field": "prefetch_depth", "op": ">", "value": 8}],
     "effect": "add", "value": 0.28,
     "error_tag": "TIMEOUT", "deterministic": False},
    {"id": "A7",
     "description": "High-entropy payloads on a wide bus with the scrambler off "
                    "mismatch the scoreboard (config.csv x randomization.csv)",
     "files": ["config.csv", "randomization.csv"],
     "conditions": [{"field": "payload_entropy", "op": ">", "value": 0.80},
                    {"field": "scrambler_enable", "op": "==", "value": 0},
                    {"field": "data_width_bits", "op": ">=", "value": 128}],
     "effect": "add", "value": 0.26,
     "error_tag": "DATA_MISMATCH", "deterministic": False},
    {"id": "A8",
     "description": "Turbo power mode above 75 C trips thermal protection "
                    "(telemetry.csv only - invisible without it)",
     "files": ["telemetry.csv"],
     "conditions": [{"field": "power_mode", "op": "==", "value": "turbo"},
                    {"field": "temperature_c", "op": ">", "value": 75.0}],
     "effect": "add", "value": 0.25,
     "error_tag": "THERMAL_SHUTDOWN", "deterministic": False},
]

A_NOISE = (["DATA_MISMATCH", "ASSERTION_FAIL"], [0.6, 0.4])


def a_sample_config(n, rng):
    c = {}
    c["test_name"] = _pick(rng, A_TESTS, [0.18, 0.16, 0.15, 0.14, 0.11, 0.09, 0.09, 0.08], n)
    c["cache_policy"] = _pick(rng, ["Adaptive", "WriteThrough", "WriteBack", "Disabled"],
                              [0.32, 0.26, 0.28, 0.14], n)
    c["test_mode_enabled"] = _pick(rng, [0, 1], [0.72, 0.28], n)
    c["queue_depth"] = _pick(rng, [1, 2, 4, 8, 16, 32, 64],
                             [0.08, 0.12, 0.18, 0.22, 0.18, 0.14, 0.08], n)
    c["num_channels"] = _pick(rng, [1, 2, 4, 8], [0.15, 0.30, 0.35, 0.20], n)
    c["num_planes"] = _pick(rng, [1, 2, 4], [0.30, 0.45, 0.25], n)
    c["ecc_mode"] = _pick(rng, ["BCH", "LDPC", "Disabled"], [0.42, 0.40, 0.18], n)
    c["scrambler_enable"] = _pick(rng, [0, 1], [0.45, 0.55], n)
    c["burst_length"] = _pick(rng, [4, 8, 16, 32, 64], [0.16, 0.24, 0.28, 0.20, 0.12], n)
    c["clock_freq_mhz"] = _pick(rng, [400, 600, 800, 1000, 1200],
                                [0.14, 0.22, 0.30, 0.22, 0.12], n)
    c["prefetch_depth"] = rng.integers(0, 17, n)
    c["data_width_bits"] = _pick(rng, [32, 64, 128, 256], [0.18, 0.32, 0.30, 0.20], n)
    c["addr_width_bits"] = _pick(rng, [32, 40, 48], [0.30, 0.45, 0.25], n)
    c["fifo_depth"] = _pick(rng, [8, 16, 32, 64, 128], [0.14, 0.22, 0.28, 0.22, 0.14], n)
    c["cache_size_kb"] = _pick(rng, [128, 256, 512, 1024], [0.22, 0.28, 0.30, 0.20], n)
    c["buffer_size_kb"] = _pick(rng, [32, 64, 128, 256], [0.25, 0.30, 0.28, 0.17], n)
    c["memory_size_mb"] = _pick(rng, [256, 512, 1024, 2048], [0.20, 0.30, 0.30, 0.20], n)
    c["num_agents"] = _pick(rng, [1, 2, 3, 4], [0.30, 0.35, 0.20, 0.15], n)
    c["agent_mode"] = _pick(rng, ["ACTIVE", "PASSIVE"], [0.85, 0.15], n)
    c["env_mode"] = _pick(rng, ["functional", "stress", "regression"], [0.45, 0.25, 0.30], n)
    c["protocol"] = np.full(n, "AXI4", dtype=object)
    c["reset_cycles"] = _pick(rng, [8, 16, 32], [0.30, 0.45, 0.25], n)
    c["timeout_ns"] = _pick(rng, [500000, 1000000, 2000000], [0.25, 0.45, 0.30], n)
    c["error_injection_enable"] = _pick(rng, [0, 1], [0.55, 0.45], n)
    c["error_injection_rate"] = np.round(rng.uniform(0.0, 0.05, n), 4) * c["error_injection_enable"]
    c["coverage_enable"] = _pick(rng, [0, 1], [0.25, 0.75], n)
    c["assertion_enable"] = _pick(rng, [0, 1], [0.12, 0.88], n)
    c["uvm_verbosity"] = _pick(rng, ["UVM_LOW", "UVM_MEDIUM", "UVM_HIGH", "UVM_DEBUG"],
                               [0.40, 0.38, 0.15, 0.07], n)
    c["debug_level"] = _pick(rng, [0, 1, 2], [0.60, 0.28, 0.12], n)
    c["cpu_threads"] = _pick(rng, [1, 2, 4, 8], [0.20, 0.32, 0.32, 0.16], n)
    c["gpu_accel"] = _pick(rng, [0, 1], [0.88, 0.12], n)
    c["compile_options"] = _pick(rng, ["-O2 -sv -timescale=1ns/1ps",
                                       "-O3 -sv -timescale=1ns/1ps -assert svaext",
                                       "-O1 -sv -debug_access+all"],
                                 [0.45, 0.35, 0.20], n)
    c["sim_options"] = _pick(rng, ["+UVM_TESTNAME=auto +ntb_random_seed_automatic",
                                   "+UVM_TESTNAME=auto -cm line+cond+fsm",
                                   "+UVM_TESTNAME=auto +UVM_MAX_QUIT_COUNT=5"],
                             [0.40, 0.35, 0.25], n)
    # Custom, environment-specific parameters - must survive ingestion untouched.
    c["wear_leveling_mode"] = _pick(rng, ["static", "dynamic", "hybrid"], [0.3, 0.45, 0.25], n)
    c["plane_interleave"] = _pick(rng, [0, 1], [0.4, 0.6], n)
    c["vendor_cmd_set"] = _pick(rng, ["v1.2", "v1.3", "v2.0"], [0.25, 0.45, 0.30], n)

    c["num_transactions"] = (np.asarray(c["queue_depth"]) * 16).astype(int)
    c["clock_period_ns"] = np.round(1000.0 / np.asarray(c["clock_freq_mhz"], float), 4)
    c["test_class"] = np.array([t.lower() + "_test" for t in c["test_name"]], dtype=object)
    c["sequence_name"] = np.array([t.lower() + "_seq" for t in c["test_name"]], dtype=object)
    return c


def a_sample_random(n, rng, cfg):
    r = {}
    r["seed"] = rng.integers(0, 2**31 - 1, n)
    r["rand_mode"] = _pick(rng, ["constrained", "full_random", "directed"], [0.62, 0.28, 0.10], n)
    r["constraint_set"] = _pick(rng, ["default", "corner", "stress"], [0.55, 0.25, 0.20], n)
    r["rand_addr_base"] = np.array([f"0x{v:08x}" for v in
                                    (rng.integers(0, 1 << 20, n) << 12)], dtype=object)
    r["rand_addr_range_kb"] = _pick(rng, [64, 256, 1024, 4096], [0.25, 0.30, 0.28, 0.17], n)
    r["rand_data_pattern"] = _pick(rng, ["random", "walking_ones", "checkerboard",
                                         "all_zeros", "incremental"],
                                   [0.42, 0.15, 0.18, 0.10, 0.15], n)
    r["payload_entropy"] = np.round(np.clip(rng.beta(2.2, 2.0, n), 0.01, 0.999), 3)
    r["rand_rw_ratio"] = np.round(rng.uniform(0.1, 0.9, n), 2)
    r["rand_opcode_mix"] = _pick(rng, ["rd_heavy", "wr_heavy", "balanced", "erase_mixed"],
                                 [0.28, 0.30, 0.30, 0.12], n)
    r["rand_burst_len_mean"] = np.round(np.asarray(cfg["burst_length"], float)
                                        * rng.uniform(0.6, 1.0, n), 1)
    r["rand_packet_len_bytes"] = _pick(rng, [512, 1024, 2048, 4096], [0.30, 0.32, 0.24, 0.14], n)
    r["rand_delay_min_ns"] = rng.integers(0, 20, n)
    r["rand_delay_max_ns"] = r["rand_delay_min_ns"] + rng.integers(5, 200, n)
    r["rand_idle_cycles"] = rng.integers(0, 64, n)
    r["rand_wait_states"] = rng.integers(0, 8, n)
    r["rand_priority_mode"] = _pick(rng, ["fixed", "weighted", "round_robin"],
                                    [0.30, 0.40, 0.30], n)
    r["rand_traffic_pattern"] = _pick(rng, ["sequential", "random", "strided", "hotspot"],
                                      [0.30, 0.35, 0.20, 0.15], n)
    r["rand_workload"] = _pick(rng, ["oltp", "streaming", "mixed", "boot"],
                               [0.28, 0.27, 0.32, 0.13], n)
    r["rand_order"] = _pick(rng, ["in_order", "out_of_order"], [0.6, 0.4], n)
    r["rand_err_inj_mode"] = _pick(rng, ["none", "bitflip", "stuck_at", "jitter"],
                                   [0.55, 0.20, 0.13, 0.12], n)
    r["rand_transaction_count"] = np.asarray(cfg["num_transactions"])
    return r


def a_sample_env(n, rng):
    """Environment half of telemetry - sampled before rules are resolved."""
    e = {}
    e["power_mode"] = _pick(rng, ["nominal", "low_power", "turbo"], [0.55, 0.20, 0.25], n)
    # Turbo runs hot, low-power runs cool - the environment is not independent of
    # the power setting, which is what makes the thermal rule physically sensible.
    bump = np.where(e["power_mode"] == "turbo", 9.0,
                    np.where(e["power_mode"] == "low_power", -5.0, 0.0))
    e["temperature_c"] = np.round(np.clip(rng.normal(62, 15, n) + bump, 25, 98), 1)
    e["voltage_mv"] = np.round(np.clip(rng.normal(1160, 45, n), 1050, 1250), 1)
    return e


def a_metrics(cols, is_fail, tag, rng, n, ceiling=2000.0):
    work = (np.asarray(cols["queue_depth"], float) * np.asarray(cols["burst_length"], float))
    parallel = (np.asarray(cols["num_channels"], float) * np.asarray(cols["num_planes"], float))
    speed = np.asarray(cols["clock_freq_mhz"], float) / 800.0
    base = 120.0 * (work / 256.0) / (parallel ** 0.6) / speed
    exec_ms = base * rng.lognormal(0.0, 0.35, n)

    m = tag == "TIMEOUT"
    exec_ms[m] = ceiling * rng.uniform(0.98, 1.0, int(m.sum()))
    for t, (lo, hi) in {"FIFO_OVERFLOW": (1.2, 1.8), "ECC_UNCORRECTABLE": (1.1, 1.5),
                        "RETENTION_FAIL": (1.0, 1.4), "PROTOCOL_VIOLATION": (0.15, 0.35),
                        "DATA_MISMATCH": (0.30, 0.70), "ASSERTION_FAIL": (0.20, 0.55),
                        "THERMAL_SHUTDOWN": (0.55, 0.95)}.items():
        k = tag == t
        if k.sum():
            exec_ms[k] *= rng.uniform(lo, hi, int(k.sum()))
    nt = tag != "TIMEOUT"
    exec_ms[nt] = ceiling * np.tanh(exec_ms[nt] / ceiling)
    exec_ms = np.maximum(exec_ms, 1.0)

    bytes_moved = work * parallel * 512.0
    tp = bytes_moved / (exec_ms / 1000.0) / 1e6 * rng.uniform(0.92, 1.08, n)
    tp[is_fail] *= rng.uniform(0.25, 0.75, int(is_fail.sum()))
    tp = tp / (1.0 + tp / 8000.0)
    cycles = (exec_ms / 1000.0 * np.asarray(cols["clock_freq_mhz"], float) * 1e6).astype(np.int64)
    return np.round(exec_ms, 2), np.round(tp, 2), cycles


def a_error_message(tag, det, rng, cfg):
    """Raw error text plus the source location the report macro would print."""
    if det:
        return ("Illegal burst termination on plane 3: beat=64 addr=0x0000c3f0 "
                "expected_ack=1 observed_ack=0", "axi_protocol_checker.sv", 412)
    addr = int(rng.integers(0, 2**28))
    return {
        "FIFO_OVERFLOW": (
            f"Write to full FIFO: fifo_id={rng.integers(0, 8)} depth={cfg['fifo_depth']} "
            f"wr_ptr=0x{rng.integers(0, 256):02x} rd_ptr=0x{rng.integers(0, 256):02x} "
            f"addr=0x{addr:08x}", "nand_scoreboard.sv", 188),
        "ECC_UNCORRECTABLE": (
            f"Uncorrectable ECC at addr=0x{addr:08x} syndrome=0x{rng.integers(0, 2**16):04x} "
            f"bits_flipped={rng.integers(9, 24)}", "ecc_monitor.sv", 96),
        "TIMEOUT": (
            f"Response watchdog expired after {rng.integers(4000, 9000)} cycles "
            f"on tag={rng.integers(0, 64)} addr=0x{addr:08x}", "axi_monitor.sv", 254),
        "DATA_MISMATCH": (
            f"Scoreboard compare failed at addr=0x{addr:08x} "
            f"expected=0x{rng.integers(0, 2**32):08x} observed=0x{rng.integers(0, 2**32):08x}",
            "nand_scoreboard.sv", 231),
        "PROTOCOL_VIOLATION": (
            f"Illegal transition on channel {rng.integers(0, 8)} "
            f"state=0x{rng.integers(0, 16):x} addr=0x{addr:08x}",
            "axi_protocol_checker.sv", 377),
        "ASSERTION_FAIL": (
            f"Assertion 'a_no_overlap' failed at addr=0x{addr:08x} "
            f"cycle={rng.integers(1000, 90000)}", "dut_assertions.sv", 64),
        "RETENTION_FAIL": (
            f"Retention check failed block={rng.integers(0, 4096)} page={rng.integers(0, 256)} "
            f"raw_ber={rng.uniform(0.01, 0.09):.4f} addr=0x{addr:08x}", "nand_model.sv", 512),
        "THERMAL_SHUTDOWN": (
            f"Thermal trip asserted: die_temp={rng.uniform(88, 104):.1f} "
            f"throttle_level={rng.integers(2, 5)} addr=0x{addr:08x}", "pmu_monitor.sv", 145),
    }[tag]


# ═══════════════════════════════════════════════════════════════════════════
# PROFILE B - apb_periph : APB peripheral subsystem (different knobs + rules)
# ═══════════════════════════════════════════════════════════════════════════

B_TESTS = ["Reg_Sweep", "Uart_Loopback", "Dma_Burst", "Irq_Storm",
           "Backpressure", "Reset_Recovery", "Parity_Stress"]

B_ERROR_COMPONENT = {
    "BUS_STARVATION":  "uvm_test_top.env.apb_agent.arb_mon",
    "FRAMING_ERROR":   "uvm_test_top.env.uart_agent.mon",
    "FIFO_UNDERRUN":   "uvm_test_top.env.dma_sb",
    "IRQ_LOST":        "uvm_test_top.env.irq_mon",
    "PSLVERR_TIMEOUT": "uvm_test_top.env.apb_agent.protocol_chk",
    "METASTABILITY":   "uvm_test_top.env.cdc_chk",
    "PREADY_TIMEOUT":  "uvm_test_top.env.apb_agent.mon",
    "REG_MISMATCH":    "uvm_test_top.env.reg_sb",
    "ASSERTION_FAIL":  "uvm_test_top.dut_wrapper",
}

B_ERROR_CODE = {
    "BUS_STARVATION": "B_ARB_0x12", "FRAMING_ERROR": "B_UART_0x24",
    "FIFO_UNDERRUN": "B_DMA_0x31", "IRQ_LOST": "B_IRQ_0x45",
    "PSLVERR_TIMEOUT": "B_APB_0x55", "METASTABILITY": "B_CDC_0x62",
    "PREADY_TIMEOUT": "B_APB_0x58", "REG_MISMATCH": "B_REG_0x70",
    "ASSERTION_FAIL": "B_ASRT_0x81",
}

B_RULES: List[Dict[str, Any]] = [
    {"id": "B1",
     "description": "Static arbitration with 8+ select lines starves the low-priority master",
     "files": ["config.csv"],
     "conditions": [{"field": "arbitration_scheme", "op": "==", "value": "static"},
                    {"field": "psel_count", "op": ">=", "value": 8}],
     "effect": "set", "value": 0.78,
     "error_tag": "BUS_STARVATION", "deterministic": False},
    {"id": "B2",
     "description": "No parity at 921600+ baud corrupts UART frames",
     "files": ["config.csv"],
     "conditions": [{"field": "parity_mode", "op": "==", "value": "none"},
                    {"field": "baud_rate", "op": ">=", "value": 921600}],
     "effect": "add", "value": 0.34,
     "error_tag": "FRAMING_ERROR", "deterministic": False},
    {"id": "B3",
     "description": "DMA enabled against a shallow FIFO underruns the stream",
     "files": ["config.csv"],
     "conditions": [{"field": "dma_enable", "op": "==", "value": 1},
                    {"field": "fifo_depth", "op": "<=", "value": 8}],
     "effect": "add", "value": 0.30,
     "error_tag": "FIFO_UNDERRUN", "deterministic": False},
    {"id": "B4",
     "description": "Edge-triggered interrupts on a slow clock drop events",
     "files": ["config.csv"],
     "conditions": [{"field": "irq_mode", "op": "==", "value": "edge"},
                    {"field": "clk_mhz", "op": "<=", "value": 50}],
     "effect": "add", "value": 0.22,
     "error_tag": "IRQ_LOST", "deterministic": False},
    {"id": "B5",
     "description": "Deterministic RTL bug: APB3 with 4+ wait states and no retry "
                    "hangs the PSLVERR handshake",
     "files": ["config.csv"],
     "conditions": [{"field": "bus_protocol", "op": "==", "value": "APB3"},
                    {"field": "wait_state_cfg", "op": ">=", "value": 4},
                    {"field": "retry_limit", "op": "==", "value": 0}],
     "effect": "set", "value": 0.95,
     "error_tag": "PSLVERR_TIMEOUT", "deterministic": True},
    {"id": "B6",
     "description": "Undervoltage above 70 C makes the CDC synchroniser metastable "
                    "(telemetry.csv only)",
     "files": ["telemetry.csv"],
     "conditions": [{"field": "voltage_mv", "op": "<", "value": 1090.0},
                    {"field": "temperature_c", "op": ">", "value": 65.0}],
     "effect": "add", "value": 0.20,
     "error_tag": "METASTABILITY", "deterministic": False},
    {"id": "B7",
     "description": "Hotspot burst traffic with long randomized wait states stalls PREADY "
                    "(randomization.csv x config.csv)",
     "files": ["randomization.csv"],
     "conditions": [{"field": "rand_traffic_pattern", "op": "==", "value": "burst_hotspot"},
                    {"field": "rand_wait_states", "op": ">=", "value": 6}],
     "effect": "add", "value": 0.25,
     "error_tag": "PREADY_TIMEOUT", "deterministic": False},
]

B_NOISE = (["REG_MISMATCH", "ASSERTION_FAIL"], [0.55, 0.45])


def b_sample_config(n, rng):
    c = {}
    c["test_name"] = _pick(rng, B_TESTS, [0.20, 0.16, 0.15, 0.14, 0.13, 0.12, 0.10], n)
    c["bus_protocol"] = _pick(rng, ["APB3", "APB4"], [0.45, 0.55], n)
    c["arbitration_scheme"] = _pick(rng, ["round_robin", "priority", "static"],
                                    [0.40, 0.35, 0.25], n)
    c["psel_count"] = _pick(rng, [2, 4, 8, 16], [0.28, 0.34, 0.24, 0.14], n)
    c["wait_state_cfg"] = rng.integers(0, 8, n)
    c["retry_limit"] = _pick(rng, [0, 1, 2, 4], [0.30, 0.30, 0.25, 0.15], n)
    c["parity_mode"] = _pick(rng, ["none", "even", "odd"], [0.35, 0.35, 0.30], n)
    c["baud_rate"] = _pick(rng, [115200, 230400, 460800, 921600, 1500000],
                           [0.24, 0.22, 0.20, 0.20, 0.14], n)
    c["fifo_depth"] = _pick(rng, [4, 8, 16, 32, 64], [0.14, 0.20, 0.28, 0.24, 0.14], n)
    c["dma_enable"] = _pick(rng, [0, 1], [0.45, 0.55], n)
    c["irq_mode"] = _pick(rng, ["level", "edge"], [0.55, 0.45], n)
    c["clk_mhz"] = _pick(rng, [25, 50, 100, 200], [0.20, 0.28, 0.32, 0.20], n)
    c["apb_data_width"] = _pick(rng, [8, 16, 32], [0.20, 0.30, 0.50], n)
    c["addr_width_bits"] = _pick(rng, [16, 32], [0.35, 0.65], n)
    c["timeout_us"] = _pick(rng, [50, 100, 250, 500], [0.22, 0.32, 0.28, 0.18], n)
    c["num_agents"] = _pick(rng, [1, 2, 3], [0.40, 0.40, 0.20], n)
    c["agent_mode"] = _pick(rng, ["ACTIVE", "PASSIVE"], [0.88, 0.12], n)
    c["env_mode"] = _pick(rng, ["functional", "stress", "regression"], [0.40, 0.30, 0.30], n)
    c["test_mode_enabled"] = _pick(rng, [0, 1], [0.80, 0.20], n)
    c["reset_cycles"] = _pick(rng, [4, 8, 16], [0.35, 0.40, 0.25], n)
    c["coverage_enable"] = _pick(rng, [0, 1], [0.30, 0.70], n)
    c["assertion_enable"] = _pick(rng, [0, 1], [0.10, 0.90], n)
    c["uvm_verbosity"] = _pick(rng, ["UVM_LOW", "UVM_MEDIUM", "UVM_HIGH"],
                               [0.45, 0.40, 0.15], n)
    c["debug_mode"] = _pick(rng, [0, 1], [0.75, 0.25], n)
    c["error_injection_enable"] = _pick(rng, [0, 1], [0.60, 0.40], n)
    c["error_injection_rate"] = np.round(rng.uniform(0.0, 0.04, n), 4) * c["error_injection_enable"]
    c["compile_options"] = _pick(rng, ["-O2 -sv", "-O2 -sv -assert svaext", "-O0 -sv -debug"],
                                 [0.45, 0.35, 0.20], n)
    c["sim_options"] = _pick(rng, ["+UVM_TESTNAME=auto", "+UVM_TESTNAME=auto -cm line+tgl"],
                             [0.6, 0.4], n)
    # Custom columns.
    c["vendor_ip_rev"] = _pick(rng, ["r1p0", "r1p2", "r2p0"], [0.30, 0.40, 0.30], n)
    c["lint_waivers"] = rng.integers(0, 12, n)
    c["num_transactions"] = (np.asarray(c["fifo_depth"]) * 64).astype(int)
    c["clock_period_ns"] = np.round(1000.0 / np.asarray(c["clk_mhz"], float), 4)
    c["test_class"] = np.array([t.lower() + "_test" for t in c["test_name"]], dtype=object)
    c["sequence_name"] = np.array([t.lower() + "_seq" for t in c["test_name"]], dtype=object)
    c["protocol"] = np.array([f"{p}+UART" for p in c["bus_protocol"]], dtype=object)
    return c


def b_sample_random(n, rng, cfg):
    r = {}
    r["seed"] = rng.integers(0, 2**31 - 1, n)
    r["rand_mode"] = _pick(rng, ["constrained", "full_random", "directed"], [0.65, 0.25, 0.10], n)
    r["constraint_set"] = _pick(rng, ["default", "corner", "stress"], [0.50, 0.28, 0.22], n)
    r["rand_addr_base"] = np.array([f"0x{v:04x}" for v in (rng.integers(0, 1 << 8, n) << 8)],
                                   dtype=object)
    r["rand_addr_range_kb"] = _pick(rng, [4, 16, 64], [0.35, 0.40, 0.25], n)
    r["rand_data_pattern"] = _pick(rng, ["random", "walking_ones", "incremental", "all_ones"],
                                   [0.45, 0.20, 0.22, 0.13], n)
    r["payload_entropy"] = np.round(np.clip(rng.beta(2.0, 2.4, n), 0.01, 0.999), 3)
    r["rand_rw_ratio"] = np.round(rng.uniform(0.2, 0.8, n), 2)
    r["rand_opcode_mix"] = _pick(rng, ["reg_rd", "reg_wr", "balanced"], [0.32, 0.30, 0.38], n)
    r["rand_packet_len_bytes"] = _pick(rng, [8, 16, 64, 128], [0.30, 0.30, 0.24, 0.16], n)
    r["rand_delay_min_ns"] = rng.integers(0, 40, n)
    r["rand_delay_max_ns"] = r["rand_delay_min_ns"] + rng.integers(10, 400, n)
    r["rand_idle_cycles"] = rng.integers(0, 32, n)
    r["rand_wait_states"] = rng.integers(0, 12, n)
    r["rand_priority_mode"] = _pick(rng, ["fixed", "weighted"], [0.5, 0.5], n)
    r["rand_traffic_pattern"] = _pick(rng, ["uniform", "burst_hotspot", "sparse", "ping_pong"],
                                      [0.32, 0.28, 0.22, 0.18], n)
    r["rand_workload"] = _pick(rng, ["sensor_poll", "console", "dma_stream", "boot"],
                               [0.28, 0.26, 0.28, 0.18], n)
    r["rand_order"] = _pick(rng, ["in_order", "out_of_order"], [0.75, 0.25], n)
    r["rand_err_inj_mode"] = _pick(rng, ["none", "bitflip", "glitch"], [0.60, 0.22, 0.18], n)
    r["rand_transaction_count"] = np.asarray(cfg["num_transactions"])
    return r


def b_sample_env(n, rng):
    e = {}
    e["power_mode"] = _pick(rng, ["nominal", "low_power", "turbo"], [0.60, 0.28, 0.12], n)
    bump = np.where(e["power_mode"] == "turbo", 8.0,
                    np.where(e["power_mode"] == "low_power", -4.0, 0.0))
    e["temperature_c"] = np.round(np.clip(rng.normal(55, 14, n) + bump, 20, 95), 1)
    e["voltage_mv"] = np.round(np.clip(rng.normal(1120, 40, n), 1000, 1240), 1)
    return e


def b_metrics(cols, is_fail, tag, rng, n, ceiling=800.0):
    """APB timing is cycle-driven: every transfer costs setup + access + waits.

    Deriving milliseconds from cycles (rather than the other way round) keeps
    execution_time_ms, sim_cycles and throughput_mbps mutually consistent.
    """
    ntx = np.asarray(cols["num_transactions"], float)
    clk = np.asarray(cols["clk_mhz"], float)
    waits = 2.0 + np.asarray(cols["wait_state_cfg"], float)
    retry = 1.0 + np.asarray(cols["retry_limit"], float) * 0.10
    jitter = rng.uniform(1.0, 1.6, n)
    cycles_f = ntx * waits * retry * jitter + 2000.0   # + reset/config overhead
    exec_ms = cycles_f / (clk * 1000.0)

    for t, (lo, hi) in {"PSLVERR_TIMEOUT": (2.4, 3.0), "PREADY_TIMEOUT": (2.0, 2.8),
                        "BUS_STARVATION": (1.4, 2.0), "FIFO_UNDERRUN": (0.6, 1.1),
                        "FRAMING_ERROR": (0.9, 1.3), "IRQ_LOST": (0.8, 1.2),
                        "METASTABILITY": (0.7, 1.2), "REG_MISMATCH": (0.4, 0.9),
                        "ASSERTION_FAIL": (0.3, 0.8)}.items():
        k = tag == t
        if k.sum():
            exec_ms[k] *= rng.uniform(lo, hi, int(k.sum()))
    exec_ms = np.clip(exec_ms, 0.01, ceiling)

    bytes_moved = (ntx * np.asarray(cols["apb_data_width"], float) / 8.0)
    tp = bytes_moved / (exec_ms / 1000.0) / 1e6 * rng.uniform(0.9, 1.1, n)
    tp[is_fail] *= rng.uniform(0.2, 0.7, int(is_fail.sum()))
    cycles = (exec_ms * clk * 1000.0).astype(np.int64)
    return np.round(exec_ms, 4), np.round(tp, 2), cycles


def b_error_message(tag, det, rng, cfg):
    if det:
        return ("PSLVERR handshake stalled: paddr=0x0f40 pready=0 pslverr=1 "
                "wait_states=7 retry=0", "apb_protocol_checker.sv", 233)
    addr = int(rng.integers(0, 1 << 16))
    return {
        "BUS_STARVATION": (
            f"Master {rng.integers(1, 8)} starved for {rng.integers(500, 4000)} cycles "
            f"paddr=0x{addr:04x}", "apb_arbiter_monitor.sv", 118),
        "FRAMING_ERROR": (
            f"UART frame error: expected_stop=1 observed_stop=0 "
            f"byte=0x{rng.integers(0, 256):02x} baud={cfg['baud_rate']}",
            "uart_monitor.sv", 87),
        "FIFO_UNDERRUN": (
            f"DMA FIFO underrun: level=0 requested={rng.integers(1, 16)} "
            f"paddr=0x{addr:04x}", "dma_scoreboard.sv", 154),
        "IRQ_LOST": (
            f"Interrupt edge dropped: irq_id={rng.integers(0, 16)} "
            f"pending=0x{rng.integers(0, 1 << 16):04x}", "irq_monitor.sv", 71),
        "PSLVERR_TIMEOUT": (
            f"PSLVERR asserted without completion paddr=0x{addr:04x} "
            f"waits={cfg['wait_state_cfg']}", "apb_protocol_checker.sv", 233),
        "METASTABILITY": (
            f"CDC synchroniser unstable on bit {rng.integers(0, 32)} "
            f"sampled=0x{rng.integers(0, 1 << 8):02x}", "cdc_checker.sv", 45),
        "PREADY_TIMEOUT": (
            f"PREADY not asserted within {rng.integers(64, 512)} cycles "
            f"paddr=0x{addr:04x}", "apb_monitor.sv", 191),
        "REG_MISMATCH": (
            f"Register readback mismatch reg=CTRL{rng.integers(0, 8)} "
            f"expected=0x{rng.integers(0, 1 << 32):08x} "
            f"observed=0x{rng.integers(0, 1 << 32):08x}", "reg_scoreboard.sv", 209),
        "ASSERTION_FAIL": (
            f"Assertion 'a_penable_stable' failed paddr=0x{addr:04x} "
            f"cycle={rng.integers(100, 40000)}", "apb_assertions.sv", 58),
    }[tag]


# ═══════════════════════════════════════════════════════════════════════════
# Profile registry
# ═══════════════════════════════════════════════════════════════════════════

PROFILES: Dict[str, Dict[str, Any]] = {
    "nvme_axi": {
        "protocol": "AXI4",
        "dut": "nvme_ssd_controller",
        "rules": A_RULES, "noise": A_NOISE,
        "base_fail": 0.012, "exec_ceiling": 2000.0,
        "sample_config": a_sample_config, "sample_random": a_sample_random,
        "sample_env": a_sample_env, "metrics": a_metrics,
        "error_message": a_error_message,
        "error_component": A_ERROR_COMPONENT, "error_code": A_ERROR_CODE,
        "log_config_fields": ["test_name", "cache_policy", "test_mode_enabled", "queue_depth",
                              "num_channels", "num_planes", "ecc_mode", "scrambler_enable",
                              "burst_length", "clock_freq_mhz", "prefetch_depth",
                              "data_width_bits", "fifo_depth", "cache_size_kb"],
        "aliases": {},          # canonical column names
        "clock_field": "clock_freq_mhz",
    },
    "apb_periph": {
        "protocol": "APB",
        "dut": "apb_peripheral_subsystem",
        "rules": B_RULES, "noise": B_NOISE,
        "base_fail": 0.020, "exec_ceiling": 800.0,
        "sample_config": b_sample_config, "sample_random": b_sample_random,
        "sample_env": b_sample_env, "metrics": b_metrics,
        "error_message": b_error_message,
        "error_component": B_ERROR_COMPONENT, "error_code": B_ERROR_CODE,
        "log_config_fields": ["test_name", "bus_protocol", "arbitration_scheme", "psel_count",
                              "wait_state_cfg", "retry_limit", "parity_mode", "baud_rate",
                              "fifo_depth", "dma_enable", "irq_mode", "clk_mhz",
                              "apb_data_width", "test_mode_enabled"],
        # Deliberate column-name drift, to exercise alias normalisation.
        "aliases": {
            "config.csv":        {"run_id": "runId", "test_name": "testcase"},
            "randomization.csv": {},
            "transactions.csv":  {"run_id": "Run_ID", "txn_id": "transaction_id"},
            "telemetry.csv":     {"run_id": "simulation_id"},
            "outcomes.csv":      {"run_id": "runId", "status": "result",
                                  "failure_type": "failure_class", "error_code": "err_code"},
        },
        "clock_field": "clk_mhz",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════════════════

def build_mask(ns, conditions):
    n = len(next(iter(ns.values())))
    mask = np.ones(n, dtype=bool)
    for c in conditions:
        mask &= _OPS[c["op"]](np.asarray(ns[c["field"]]), c["value"])
    return mask


def apply_rules(ns, rules, noise, base_fail, n, rng):
    prob = np.full(n, base_fail)
    tag = np.full(n, "", dtype=object)
    prio = np.zeros(n)
    det = np.zeros(n, dtype=bool)
    fired: Dict[str, np.ndarray] = {}

    for r in rules:
        m = build_mask(ns, r["conditions"])
        fired[r["id"]] = m
        if r["effect"] == "add":
            prob[m] += r["value"]
    for r in rules:
        if r["effect"] == "set":
            prob[fired[r["id"]]] = r["value"]

    prob = np.clip(prob, 0.001, 0.99)
    is_fail = rng.random(n) < prob

    for r in rules:
        if not r["error_tag"]:
            continue
        m = fired[r["id"]] & is_fail & (r["value"] > prio)
        tag[m] = r["error_tag"]
        prio[m] = r["value"]
        if r["deterministic"]:
            det[m] = True

    unclaimed = is_fail & (tag == "")
    k = int(unclaimed.sum())
    if k:
        tag[unclaimed] = rng.choice(noise[0], size=k, p=noise[1])
    return prob, is_fail, tag, det, fired


def _scalar(v):
    return v.item() if hasattr(v, "item") else v


def build_run_table(profile_name, n_runs, seed):
    """Sample everything and resolve outcomes. Returns a dict of column arrays."""
    p = PROFILES[profile_name]
    rng = np.random.default_rng(seed)

    cfg = p["sample_config"](n_runs, rng)
    rnd = p["sample_random"](n_runs, rng, cfg)
    env = p["sample_env"](n_runs, rng)

    ns = {**cfg, **rnd, **env}
    prob, is_fail, tag, det, fired = apply_rules(
        ns, p["rules"], p["noise"], p["base_fail"], n_runs, rng)
    exec_ms, tp, cycles = p["metrics"](cfg, is_fail, tag, rng, n_runs, p["exec_ceiling"])

    run_ids = np.array([f"RUN-{i + 1:06d}" for i in range(n_runs)], dtype=object)
    return {"profile": profile_name, "rng": rng, "run_ids": run_ids,
            "cfg": cfg, "rnd": rnd, "env": env, "prob": prob, "is_fail": is_fail,
            "tag": tag, "det": det, "fired": fired,
            "exec_ms": exec_ms, "throughput": tp, "cycles": cycles}


# ── transactions ───────────────────────────────────────────────────────────

def build_transactions(tbl, max_txn=10):
    """Per-run transaction window: DUT inputs, DUT outputs, protocol fields.

    Every failing transaction is always included, so the MISMATCH/error rows in
    this file reconcile exactly with outcomes.csv.
    """
    p = PROFILES[tbl["profile"]]
    rng = tbl["rng"]
    cfg, rnd = tbl["cfg"], tbl["rnd"]
    rows: List[Dict[str, Any]] = []
    axi = p["protocol"] == "AXI4"

    for i, run_id in enumerate(tbl["run_ids"]):
        n_tx = int(min(max_txn, max(4, _scalar(cfg["num_transactions"][i]) // 8)))
        end_ns = _end_ns(tbl["exec_ms"][i])
        starts = np.sort(rng.integers(2000, end_ns, n_tx))
        fail_idx = int(rng.integers(0, n_tx)) if tbl["is_fail"][i] else -1
        tag = tbl["tag"][i]
        seq = _scalar(cfg["sequence_name"][i])
        rw_ratio = float(rnd["rand_rw_ratio"][i])

        for j in range(n_tx):
            is_write = rng.random() < rw_ratio
            start = int(starts[j])
            dur = int(rng.integers(20, 400))
            bad = (j == fail_idx)
            addr = int(rng.integers(0, 1 << 28)) if axi else int(rng.integers(0, 1 << 16))
            wdata = int(rng.integers(0, 1 << 32))
            rdata = int(rng.integers(0, 1 << 32))
            expected = wdata if is_write else rdata
            observed = expected
            if bad and tag in ("DATA_MISMATCH", "ECC_UNCORRECTABLE", "REG_MISMATCH",
                               "FRAMING_ERROR", "RETENTION_FAIL"):
                observed = expected ^ (1 << int(rng.integers(0, 32)))
            checker = "MISMATCH" if observed != expected else "MATCH"
            timed_out = bad and tag in ("TIMEOUT", "PSLVERR_TIMEOUT", "PREADY_TIMEOUT")

            row = {
                "run_id": run_id,
                "txn_id": f"{run_id}-T{j:04d}",
                "sequence_id": f"{run_id}-S{j // 4:02d}",
                "sequence_name": seq,
                "txn_type": "WRITE" if is_write else "READ",
                "start_time_ns": start,
                "end_time_ns": "" if timed_out else min(start + dur, end_ns),
                "clock_cycle": int(start / max(_scalar(cfg["clock_period_ns"][i]), 0.1)),
                "channel_id": int(rng.integers(0, max(2, _scalar(
                    cfg.get("num_channels", cfg.get("psel_count"))[i])))),
                "src_id": int(rng.integers(0, 4)),
                "dst_id": int(rng.integers(0, 4)),
                "priority": int(rng.integers(0, 4)),
                "addr": f"0x{addr:08x}" if axi else f"0x{addr:04x}",
                "wdata": f"0x{wdata:08x}" if is_write else "",
                "rdata": "" if (is_write or timed_out) else f"0x{rdata:08x}",
                "expected_data": f"0x{expected:08x}",
                "observed_data": "" if timed_out else f"0x{observed:08x}",
                "checker_result": "TIMEOUT" if timed_out else checker,
                "error_id": (p["error_code"][tag] if bad and tag in p["error_code"] else ""),
            }

            if axi:
                blen = int(_scalar(cfg["burst_length"][i]))
                row.update({
                    "opcode": "AXI_WR" if is_write else "AXI_RD",
                    "burst_len": blen,
                    "beat_size_bytes": int(_scalar(cfg["data_width_bits"][i]) // 8),
                    "burst_type": "INCR" if rng.random() < 0.8 else "WRAP",
                    "AWADDR": f"0x{addr:08x}" if is_write else "",
                    "AWVALID": 1 if is_write else 0,
                    "AWREADY": 0 if (timed_out and is_write) else (1 if is_write else 0),
                    "WDATA": f"0x{wdata:08x}" if is_write else "",
                    "WSTRB": f"0x{rng.integers(0, 256):02x}" if is_write else "",
                    "WVALID": 1 if is_write else 0,
                    "WREADY": 0 if (timed_out and is_write) else (1 if is_write else 0),
                    "BRESP": ("SLVERR" if bad and tag == "PROTOCOL_VIOLATION"
                              else ("" if not is_write else "OKAY")),
                    "ARADDR": "" if is_write else f"0x{addr:08x}",
                    "ARVALID": 0 if is_write else 1,
                    "ARREADY": 0 if (timed_out and not is_write) else (0 if is_write else 1),
                    "RDATA": "" if (is_write or timed_out) else f"0x{observed:08x}",
                    "RRESP": ("" if is_write else
                              ("SLVERR" if bad and tag in ("ECC_UNCORRECTABLE",
                                                           "PROTOCOL_VIOLATION") else "OKAY")),
                    "RVALID": 0 if (is_write or timed_out) else 1,
                    "RREADY": 0 if is_write else 1,
                    "interrupt_out": 1 if bad and tag == "THERMAL_SHUTDOWN" else 0,
                    "byte_enable": f"0x{rng.integers(0, 256):02x}",
                })
            else:
                row.update({
                    "opcode": "APB_WR" if is_write else "APB_RD",
                    "PADDR": f"0x{addr:04x}",
                    "PWRITE": 1 if is_write else 0,
                    "PWDATA": f"0x{wdata:08x}" if is_write else "",
                    "PRDATA": "" if (is_write or timed_out) else f"0x{observed:08x}",
                    "PSEL": int(rng.integers(1, max(2, _scalar(cfg["psel_count"][i]) + 1))),
                    "PENABLE": 1,
                    "PREADY": 0 if timed_out else 1,
                    "PSLVERR": 1 if bad and tag in ("PSLVERR_TIMEOUT", "BUS_STARVATION") else 0,
                    "PSTRB": f"0x{rng.integers(0, 16):01x}" if is_write else "",
                    "uart_tx_byte": f"0x{rng.integers(0, 256):02x}",
                    "uart_rx_byte": f"0x{rng.integers(0, 256):02x}",
                    "parity_error": 1 if bad and tag == "FRAMING_ERROR" else 0,
                    "framing_error": 1 if bad and tag == "FRAMING_ERROR" else 0,
                    "irq_out": 1 if bad and tag == "IRQ_LOST" else 0,
                })
            rows.append(row)

    return pd.DataFrame(rows)


def build_registers(tbl, per_run=4):
    """Register / memory access dump."""
    rng = tbl["rng"]
    cfg = tbl["cfg"]
    names = ["CTRL0", "CTRL1", "STATUS", "INT_MASK", "INT_STATUS", "ECC_CFG",
             "FIFO_LEVEL", "TIMEOUT_CFG", "PERF_CNT0", "PERF_CNT1"]
    rows = []
    for i, run_id in enumerate(tbl["run_ids"]):
        end_ns = _end_ns(tbl["exec_ms"][i])
        for k in range(per_run):
            name = names[int(rng.integers(0, len(names)))]
            base = names.index(name) * 4
            is_write = rng.random() < 0.5
            val = int(rng.integers(0, 1 << 32))
            mismatch = bool(tbl["is_fail"][i] and k == per_run - 1 and rng.random() < 0.25)
            rows.append({
                "run_id": run_id,
                "access_time_ns": int(rng.integers(1000, end_ns)),
                "access_type": "WRITE" if is_write else "READ",
                "block": "csr",
                "reg_name": name,
                "reg_addr": f"0x{base:04x}",
                "reg_value": f"0x{val:08x}",
                "expected_value": f"0x{val ^ (1 if mismatch else 0):08x}",
                "field_name": f"{name.lower()}_field{int(rng.integers(0, 4))}",
                "field_value": int(rng.integers(0, 16)),
                "status": "MISMATCH" if mismatch else "OK",
                "mem_block_id": int(rng.integers(0, max(2, _scalar(
                    cfg.get("num_planes", cfg.get("psel_count"))[i])))),
            })
    return pd.DataFrame(rows)


# ── telemetry ──────────────────────────────────────────────────────────────

HOSTS = ["farm-node-01", "farm-node-02", "farm-node-07", "farm-node-11", "farm-node-19"]
SIMULATORS = [("Xcelium", "23.09.004"), ("VCS", "2023.12-SP1"), ("Questa", "2023.4")]
CPUS = ["EPYC-7763", "Xeon-Gold-6338", "EPYC-9354"]


def build_telemetry(tbl):
    rng = tbl["rng"]
    cfg, env = tbl["cfg"], tbl["env"]
    n = len(tbl["run_ids"])
    sim_idx = rng.integers(0, len(SIMULATORS), n)
    exec_ms = tbl["exec_ms"]

    cpu_avg = np.round(np.clip(rng.normal(58, 14, n)
                               + np.asarray(cfg["cpu_threads"] if "cpu_threads" in cfg
                                            else np.ones(n)) * 2.0, 5, 99), 1)
    wall = np.round(exec_ms / 1000.0 * rng.uniform(6.0, 14.0, n) + rng.uniform(2, 30, n), 2)
    df = pd.DataFrame({
        "run_id": tbl["run_ids"],
        "host": [HOSTS[k] for k in rng.integers(0, len(HOSTS), n)],
        "os_release": "rhel8.8",
        "simulator": [SIMULATORS[k][0] for k in sim_idx],
        "simulator_version": [SIMULATORS[k][1] for k in sim_idx],
        "cpu_model": [CPUS[k] for k in rng.integers(0, len(CPUS), n)],
        "cpu_cores_allocated": (cfg["cpu_threads"] if "cpu_threads" in cfg
                                else rng.integers(1, 5, n)),
        "cpu_util_avg_pct": cpu_avg,
        "cpu_util_peak_pct": np.round(np.clip(cpu_avg + rng.uniform(3, 30, n), 5, 100), 1),
        "mem_util_avg_pct": np.round(np.clip(rng.normal(46, 13, n), 5, 98), 1),
        "peak_mem_mb": np.round(np.clip(rng.normal(2600, 900, n)
                                        + exec_ms * 0.7, 400, 32000), 1),
        "disk_io_mb": np.round(np.clip(rng.normal(310, 140, n), 5, 4000), 1),
        "wall_time_s": wall,
        "cpu_time_s": np.round(wall * rng.uniform(0.7, 1.6, n), 2),
        "license_wait_s": np.round(np.clip(rng.exponential(9, n), 0, 400), 2),
        "sim_perf_cycles_per_sec": np.round(
            tbl["cycles"] / np.maximum(wall, 0.1), 1),
        "temperature_c": env["temperature_c"],
        "voltage_mv": env["voltage_mv"],
        "power_mode": env["power_mode"],
        "power_w": np.round(np.clip(rng.normal(4.2, 1.1, n)
                                    + (env["power_mode"] == "turbo") * 2.4, 0.6, 14), 2),
        "grid_queue": [["short", "normal", "long"][k] for k in rng.integers(0, 3, n)],
    })
    return df


# ── outcomes ───────────────────────────────────────────────────────────────

def build_outcomes(tbl, log_stats):
    p = PROFILES[tbl["profile"]]
    n = len(tbl["run_ids"])
    tags = tbl["tag"]
    return pd.DataFrame({
        "run_id": tbl["run_ids"],
        "test_id": [f"{c}-{i+1:06d}" for i, c in enumerate(tbl["cfg"]["test_class"])],
        "seed": tbl["rnd"]["seed"],
        "status": np.where(tbl["is_fail"], "FAIL", "PASS"),
        "pass_fail": np.where(tbl["is_fail"], "fail", "pass"),
        "failure_type": np.where(tbl["is_fail"], tags, "NONE"),
        "error_code": [p["error_code"].get(t, "") if f else ""
                       for t, f in zip(tags, tbl["is_fail"])],
        "error_id": [f"{t}" if f else "" for t, f in zip(tags, tbl["is_fail"])],
        "first_error_time_ns": [s["first_error_ns"] for s in log_stats],
        "uvm_error_count": [s["n_err"] for s in log_stats],
        "uvm_warning_count": [s["n_warn"] for s in log_stats],
        "uvm_fatal_count": [s["n_fatal"] for s in log_stats],
        "assertion_failures": [s["n_assert"] for s in log_stats],
        "scoreboard_mismatches": [s["n_mismatch"] for s in log_stats],
        "execution_time_ms": tbl["exec_ms"],
        "throughput_mbps": tbl["throughput"],
        "sim_cycles": tbl["cycles"],
        "exit_code": np.where(tbl["is_fail"], 1, 0),
        "verdict_source": "uvm_report_server",
    })


# ── uvm.log ────────────────────────────────────────────────────────────────

def render_log(tbl, txn_df):
    """Render every run in the legacy log grammar. Returns (text, per-run stats)."""
    p = PROFILES[tbl["profile"]]
    rng = tbl["rng"]
    cfg, rnd, env = tbl["cfg"], tbl["rnd"], tbl["env"]
    mismatch_by_run = (txn_df[txn_df["checker_result"] == "MISMATCH"]
                       .groupby("run_id").size().to_dict()) if len(txn_df) else {}
    txn_count_by_run = txn_df.groupby("run_id").size().to_dict() if len(txn_df) else {}

    chunks: List[str] = []
    stats: List[Dict[str, int]] = []

    for i, run_id in enumerate(tbl["run_ids"]):
        cfg_json = {"run_id": run_id}
        for f in p["log_config_fields"]:
            cfg_json[f] = _scalar(cfg[f][i])
        cfg_json.update({
            "seed": int(rnd["seed"][i]),
            "rand_traffic_pattern": _scalar(rnd["rand_traffic_pattern"][i]),
            "payload_entropy": float(rnd["payload_entropy"][i]),
            "temperature_c": float(env["temperature_c"][i]),
            "voltage_mv": float(env["voltage_mv"][i]),
            "power_mode": _scalar(env["power_mode"][i]),
            "error_injection_rate": float(cfg["error_injection_rate"][i]),
        })

        t_end = _end_ns(tbl["exec_ms"][i])
        tag = tbl["tag"][i]
        fail = bool(tbl["is_fail"][i])
        n_txn = int(txn_count_by_run.get(run_id, 0))

        out = [RUN_SEPARATOR, f"{BANNER}{run_id}", RUN_SEPARATOR,
               CONFIG_OPEN, json.dumps(cfg_json, separators=(",", ":")), CONFIG_CLOSE]
        info = [
            f"UVM_INFO @ 0 ns: reporter [RNTST] Running test {_scalar(cfg['test_class'][i])}...",
            f"UVM_INFO @ 0 ns: uvm_test_top [SEED] Random seed = {int(rnd['seed'][i])} "
            f"mode={_scalar(rnd['rand_mode'][i])} constraints={_scalar(rnd['constraint_set'][i])}",
            f"UVM_INFO @ 500 ns: uvm_test_top.env [BUILD] protocol={_scalar(cfg['protocol'][i])} "
            f"agents={_scalar(cfg['num_agents'][i])} verbosity={_scalar(cfg['uvm_verbosity'][i])}",
            f"UVM_INFO @ 800 ns: uvm_test_top.env [RESET] reset asserted for "
            f"{_scalar(cfg['reset_cycles'][i])} cycles, deasserted @ "
            f"{800 + int(_scalar(cfg['reset_cycles'][i])) * 10} ns",
            f"UVM_INFO @ 1500 ns: uvm_test_top.env.agent.drv [DRV_START] Driving "
            f"{_scalar(cfg['num_transactions'][i])} transactions "
            f"(window of {n_txn} logged)",
            f"UVM_INFO @ 2000 ns: uvm_test_top.env.reg_env [REG_ACCESS] write reg=CTRL0 "
            f"addr=0x0000 value=0x{rng.integers(0, 1 << 16):04x}",
        ]
        out += info
        n_info = len(info)
        n_warn = n_err = n_fatal = n_assert = 0
        first_error_ns = ""

        if rng.random() < 0.30:
            out.append(f"UVM_WARNING @ {max(int(t_end * 0.4), 2100)} ns: "
                       f"uvm_test_top.env.agent.mon "
                       f"[PROTO_WARN] Backpressure sustained for "
                       f"{rng.integers(50, 900)} cycles")
            n_warn += 1

        if fail:
            msg, src_file, src_line = p["error_message"](tag, bool(tbl["det"][i]), rng, {
                k: _scalar(v[i]) for k, v in cfg.items()})
            comp = p["error_component"][tag]
            t0 = max(int(t_end * 0.88), 2500)
            n_lines = 1 if tbl["det"][i] else int(rng.integers(1, 4))
            for k in range(n_lines):
                t = t0 + k * 137
                out.append(f"UVM_ERROR @ {t} ns: {comp} [{tag}] {msg} "
                           f"file={src_file} line={src_line}")
                n_err += 1
                if first_error_ns == "":
                    first_error_ns = t
            if tbl["det"][i]:
                out.append(f"UVM_ERROR @ {t0 + 20} ns: {comp} [{tag}] {msg} "
                           f"file={src_file} line={src_line}")
                n_err += 1
            if _scalar(cfg["assertion_enable"][i]) == 1 and rng.random() < 0.45:
                acomp = p["error_component"]["ASSERTION_FAIL"]
                out.append(f"UVM_ERROR @ {t0 + 260} ns: {acomp} [ASSERTION_FAIL] "
                           f"Assertion 'a_{tag.lower()}_guard' failed "
                           f"property=p_{tag.lower()} severity=error "
                           f"file=dut_assertions.sv line={rng.integers(40, 300)}")
                n_err += 1
                n_assert += 1
            if tag in ("TIMEOUT", "PROTOCOL_VIOLATION", "PSLVERR_TIMEOUT", "PREADY_TIMEOUT"):
                out.append(f"UVM_FATAL @ {t_end} ns: uvm_test_top [TEST_ABORT] "
                           f"Aborting on unrecoverable {tag}")
                n_fatal += 1
        else:
            out.append(f"UVM_INFO @ {max(int(t_end * 0.94), 2500)} ns: uvm_test_top.env.sb "
                       f"[SB_OK] All transactions matched")
            n_info += 1

        n_mismatch = int(mismatch_by_run.get(run_id, 0))
        matched = max(n_txn - n_mismatch, 0)
        out.append(f"UVM_INFO @ {max(int(t_end * 0.96), 2600)} ns: uvm_test_top.env.sb "
                   f"[SB_SUMMARY] compared={n_txn} matched={matched} "
                   f"mismatched={n_mismatch}")
        out.append(f"UVM_INFO @ {max(int(t_end * 0.98), 2700)} ns: uvm_test_top [SIM_ENV] "
                   f"temp_c={float(env['temperature_c'][i])} "
                   f"voltage_mv={float(env['voltage_mv'][i])} "
                   f"power_mode={_scalar(env['power_mode'][i])}")
        n_info += 2

        out += [
            METRICS_OPEN,
            json.dumps({"execution_time_ms": float(tbl["exec_ms"][i]),
                        "throughput_mbps": float(tbl["throughput"][i]),
                        "cycles": int(tbl["cycles"][i]),
                        "uvm_error_count": n_err,
                        "uvm_fatal_count": n_fatal}, separators=(",", ":")),
            METRICS_CLOSE,
            SUMMARY_HEADER,
            f"UVM_INFO    : {n_info:>4d}",
            f"UVM_WARNING : {n_warn:>4d}",
            f"UVM_ERROR   : {n_err:>4d}",
            f"UVM_FATAL   : {n_fatal:>4d}",
            VERDICT_FAIL if fail else VERDICT_PASS,
            "",
        ]
        chunks.append("\n".join(out))
        stats.append({"n_info": n_info, "n_warn": n_warn, "n_err": n_err,
                      "n_fatal": n_fatal, "n_assert": n_assert,
                      "n_mismatch": n_mismatch, "first_error_ns": first_error_ns})
    return "\n".join(chunks), stats


# ── waveform (VCD) ─────────────────────────────────────────────────────────

def write_vcd(path, run_id, failing, rng, n_steps=400):
    sym = {"clk": "!", "rst_n": '"', "state": "#", "fifo_wr_ptr": "$",
           "fifo_rd_ptr": "%", "fifo_count": "&", "err_flag": "'",
           "ecc_syndrome": "(", "axi_awvalid": ")", "axi_awready": "*",
           "axi_rvalid": "+"}
    widths = {"state": 4, "fifo_wr_ptr": 8, "fifo_rd_ptr": 8,
              "fifo_count": 8, "ecc_syndrome": 16}

    lines = ["$date generated by generate_structured_dataset.py $end",
             "$version 1.0 $end", "$timescale 1ns $end",
             "$scope module tb_top $end", "$scope module dut $end"]
    for name, s in sym.items():
        w = widths.get(name, 1)
        lines.append(f"$var {'wire' if w == 1 else 'reg'} {w} {s} "
                     f"{name}{'' if w == 1 else f' [{w - 1}:0]'} $end")
    lines += ["$upscope $end", "$upscope $end", "$enddefinitions $end", "#0"]

    wr = rd = count = 0
    state = 0
    trip = int(n_steps * 0.72) if failing else -1
    for t in range(n_steps):
        lines.append(f"#{t * 10}")
        lines.append(f"{t % 2}!")
        lines.append(f'{0 if t < 8 else 1}"')
        if t % 2 == 0:
            state = (state + 1) % 6 if t > 8 else 0
            wr = (wr + int(rng.integers(0, 3))) % 256
            rd = (rd + int(rng.integers(0, 2))) % 256
            count = max(0, min(255, count + int(rng.integers(-1, 3))))
            if failing and t >= trip:
                count = min(255, count + 6)
            lines.append(f"b{state:04b} #")
            lines.append(f"b{wr:08b} $")
            lines.append(f"b{rd:08b} %")
            lines.append(f"b{count:08b} &")
            lines.append(f"{1 if (failing and t >= trip) else 0}'")
            lines.append(f"b{int(rng.integers(0, 1 << 16)):016b} (")
            lines.append(f"{int(rng.integers(0, 2))})")
            lines.append(f"{0 if (failing and t >= trip) else 1}*")
            lines.append(f"{int(rng.integers(0, 2))}+")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ═══════════════════════════════════════════════════════════════════════════
# Dataset assembly
# ═══════════════════════════════════════════════════════════════════════════

def _rename(df, alias_map):
    return df.rename(columns=alias_map) if alias_map else df


def _clean(out_dir):
    """Remove artifacts this generator owns, so a re-run never leaves orphans.

    Only the generator's own filenames are touched - anything else the user put
    in the directory is left alone.
    """
    for name in ALL_FILES + ["MANIFEST.json", "ground_truth.json"]:
        path = os.path.join(out_dir, name)
        if os.path.isfile(path):
            os.remove(path)
    wdir = os.path.join(out_dir, "waveforms")
    if os.path.isdir(wdir):
        for name in os.listdir(wdir):
            if name.endswith(".vcd"):
                os.remove(os.path.join(wdir, name))


def build_dataset(profile_name, n_runs, seed, out_dir, files, with_waveforms=False,
                  max_txn=10, label=""):
    p = PROFILES[profile_name]
    os.makedirs(out_dir, exist_ok=True)
    _clean(out_dir)
    tbl = build_run_table(profile_name, n_runs, seed)

    txn_df = build_transactions(tbl, max_txn=max_txn)
    log_text, log_stats = render_log(tbl, txn_df)

    cfg_df = pd.DataFrame({"run_id": tbl["run_ids"],
                           "test_id": [f"{c}-{i+1:06d}" for i, c
                                       in enumerate(tbl["cfg"]["test_class"])],
                           **{k: v for k, v in tbl["cfg"].items()}})
    rnd_df = pd.DataFrame({"run_id": tbl["run_ids"],
                           "sequence_name": tbl["cfg"]["sequence_name"],
                           **{k: v for k, v in tbl["rnd"].items()}})
    tel_df = build_telemetry(tbl)
    out_df = build_outcomes(tbl, log_stats)
    reg_df = build_registers(tbl)

    alias = p["aliases"]
    written = {}

    def _csv(name, df):
        path = os.path.join(out_dir, name)
        _rename(df, alias.get(name, {})).to_csv(path, index=False)
        written[name] = {"rows": int(len(df)), "bytes": os.path.getsize(path),
                         "columns": list(_rename(df, alias.get(name, {})).columns)}

    if "config.csv" in files:
        _csv("config.csv", cfg_df)
    if "randomization.csv" in files:
        _csv("randomization.csv", rnd_df)
    if "transactions.csv" in files:
        _csv("transactions.csv", txn_df)
    if "telemetry.csv" in files:
        _csv("telemetry.csv", tel_df)
    if "outcomes.csv" in files:
        _csv("outcomes.csv", out_df)
    if "registers.csv" in files:
        _csv("registers.csv", reg_df)
    if "uvm.log" in files:
        path = os.path.join(out_dir, "uvm.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(log_text)
        written["uvm.log"] = {"rows": int(n_runs), "bytes": os.path.getsize(path),
                              "columns": ["<uvm log grammar>"]}

    wave_files = []
    if with_waveforms:
        wdir = os.path.join(out_dir, "waveforms")
        os.makedirs(wdir, exist_ok=True)
        fails = np.flatnonzero(tbl["is_fail"])[:2]
        passes = np.flatnonzero(~tbl["is_fail"])[:2]
        for idx in list(fails) + list(passes):
            rid = tbl["run_ids"][idx]
            fp = os.path.join(wdir, f"{rid}.vcd")
            write_vcd(fp, rid, bool(tbl["is_fail"][idx]), tbl["rng"])
            wave_files.append({"path": f"waveforms/{rid}.vcd", "run_id": rid,
                               "verdict": "FAIL" if tbl["is_fail"][idx] else "PASS",
                               "bytes": os.path.getsize(fp)})

    # ── ground truth ───────────────────────────────────────────────────────
    is_fail, fired = tbl["is_fail"], tbl["fired"]
    gt_rules = []
    for r in p["rules"]:
        m = fired[r["id"]]
        n_m = int(m.sum())
        base = float(is_fail[~m].mean()) if (~m).sum() else None
        fire = float(is_fail[m].mean()) if n_m else None
        gt_rules.append({**r, "observed": {
            "rows_matched": n_m,
            "match_share": round(n_m / n_runs, 4),
            "fail_rate_when_fired": round(fire, 4) if fire is not None else None,
            "fail_rate_otherwise": round(base, 4) if base is not None else None,
            "lift": round(fire / base, 3) if (fire and base) else None,
        }})
    tags, counts = np.unique(tbl["tag"][is_fail], return_counts=True)

    gt = {
        "dataset": label or os.path.basename(out_dir),
        "profile": profile_name,
        "generator": "tools/generate_structured_dataset.py",
        "metadata": {
            "n_runs": n_runs, "seed": seed, "protocol": p["protocol"], "dut": p["dut"],
            "base_fail_prob": p["base_fail"], "exec_ceiling_ms": p["exec_ceiling"],
            "observed_fail_rate": round(float(is_fail.mean()), 4),
            "observed_pass_rate": round(float((~is_fail).mean()), 4),
            "files_provided": sorted(written.keys()),
            "categories_absent": sorted(
                {"config.csv", "randomization.csv", "transactions.csv", "telemetry.csv",
                 "outcomes.csv", "uvm.log", "registers.csv"} - set(written.keys())
                | ({"waveform"} if not with_waveforms else set())),
            "column_aliases": alias,
        },
        "rules": gt_rules,
        "error_tag_distribution": {str(t): int(c) for t, c in zip(tags, counts)},
        "files": written,
        "waveforms": wave_files,
        "invariants": [
            "outcomes.status == FAIL  <=>  uvm.log verdict is '** TEST FAILED **'",
            "outcomes.uvm_error_count == count of UVM_ERROR lines for that run in uvm.log",
            "outcomes.uvm_fatal_count == count of UVM_FATAL lines for that run in uvm.log",
            "outcomes.scoreboard_mismatches == rows in transactions.csv with "
            "checker_result == MISMATCH for that run",
            "outcomes.failure_type == NONE for every passing run",
            "timestamps are real nanoseconds: every start_time_ns in "
            "transactions.csv < execution_time_ms * 1e6",
            "run_id is the join key across every file that carries one",
        ],
        "raw_vs_derived": {
            "raw_in_files": ["config knobs", "seed and randomized fields", "transaction "
                             "inputs/outputs", "protocol signal values", "UVM report lines",
                             "assertion events", "register accesses", "environment telemetry",
                             "PASS/FAIL verdict", "execution_time_ms", "throughput_mbps",
                             "sim_cycles"],
            "must_be_derived_by_analytics": ["latency", "failure_probability", "risk_score",
                                             "failure_rate", "feature importance", "SHAP",
                                             "correlation", "cluster id", "pareto rank",
                                             "recommended configuration", "confidence"],
        },
    }
    with open(os.path.join(out_dir, "ground_truth.json"), "w", encoding="utf-8") as fh:
        json.dump(gt, fh, indent=2)

    manifest = {
        "dataset": gt["dataset"], "profile": profile_name, "n_runs": n_runs, "seed": seed,
        "protocol": p["protocol"], "join_key": "run_id",
        "files": written, "waveforms": wave_files,
        "pass_rate": gt["metadata"]["observed_pass_rate"],
        "fail_rate": gt["metadata"]["observed_fail_rate"],
        "column_aliases": alias,
        "absent_categories": gt["metadata"]["categories_absent"],
    }
    with open(os.path.join(out_dir, "MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return gt


# ═══════════════════════════════════════════════════════════════════════════

ALL_FILES = ["config.csv", "randomization.csv", "transactions.csv", "telemetry.csv",
             "outcomes.csv", "uvm.log", "registers.csv"]

BUNDLES = [
    {"dir": "dataset_a_nvme_axi", "profile": "nvme_axi", "n_runs": 6000, "seed": 1337,
     "files": ALL_FILES, "waveforms": True, "max_txn": 10,
     "label": "Dataset A - NVMe/AXI4 controller, complete input set"},
    {"dir": "dataset_b_apb_periph", "profile": "apb_periph", "n_runs": 4000, "seed": 2024,
     "files": ALL_FILES, "waveforms": False, "max_txn": 10,
     "label": "Dataset B - APB peripheral subsystem, aliased columns, no waveform"},
    {"dir": "dataset_c_partial", "profile": "nvme_axi", "n_runs": 1500, "seed": 777,
     "files": ["config.csv", "transactions.csv", "outcomes.csv"], "waveforms": False,
     "max_txn": 8, "label": "Dataset C - partial input set (no randomization/telemetry/log)"},
    {"dir": "dataset_d_legacy_log", "profile": "nvme_axi", "n_runs": 2000, "seed": 4242,
     "files": ["uvm.log"], "waveforms": False, "max_txn": 6,
     "label": "Dataset D - legacy mode, uvm.log only"},
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="generate every bundle")
    ap.add_argument("--profile", choices=list(PROFILES))
    ap.add_argument("--n-runs", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--out-dir", default="data/datasets/custom")
    ap.add_argument("--root", default="data/datasets")
    ap.add_argument("--max-txn", type=int, default=10)
    ap.add_argument("--no-waveforms", action="store_true")
    args = ap.parse_args()

    if args.all:
        for b in BUNDLES:
            out = os.path.join(args.root, b["dir"])
            print(f"\n=== {b['label']}")
            gt = build_dataset(b["profile"], b["n_runs"], b["seed"], out, b["files"],
                               with_waveforms=b["waveforms"], max_txn=b["max_txn"],
                               label=b["label"])
            md = gt["metadata"]
            print(f"    runs={md['n_runs']:,}  pass={md['observed_pass_rate']:.3f}  "
                  f"fail={md['observed_fail_rate']:.3f}")
            for f, meta in gt["files"].items():
                print(f"    {f:<20} {meta['rows']:>8,} rows  {meta['bytes'] / 1e6:6.2f} MB")
            for r in gt["rules"]:
                o = r["observed"]
                print(f"    [{r['id']}] n={o['rows_matched']:>6,} "
                      f"fail_fired={o['fail_rate_when_fired']} "
                      f"vs {o['fail_rate_otherwise']} lift={o['lift']}")
            print(f"    tags: {gt['error_tag_distribution']}")
        return

    if not args.profile:
        ap.error("pass --all or --profile")
    gt = build_dataset(args.profile, args.n_runs, args.seed, args.out_dir, ALL_FILES,
                       with_waveforms=not args.no_waveforms, max_txn=args.max_txn)
    print(json.dumps(gt["metadata"], indent=2))


if __name__ == "__main__":
    main()
