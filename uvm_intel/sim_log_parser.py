#!/usr/bin/env python3
"""
Parser for real simulator transcripts (QuestaSim, VCS, Xcelium).

Unlike the generated corpus, a real log holds exactly one run and carries no
[CONFIG]/[METRICS] blocks, so everything is recovered from the text:

    config  - test name, seed and +plusargs from the simulator command line
    errors  - UVM_ERROR / UVM_FATAL report lines
    verdict - "*** TEST PASSED/FAILED ***" banner, else the UVM report counts
    metrics - "Label : value" lines printed by the testbench (scoreboard and
              coverage summaries), stored as metric_<label> columns

The row has the same shape as one produced by log_parser._flush, so the rest
of the pipeline cannot tell the two sources apart.
"""

import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .log_format import fingerprint

# Prefix for testbench-reported numbers. They describe the outcome of a run,
# so risk_model.select_features keeps them out of the feature set.
METRIC_PREFIX = "metric_"

# # UVM_ERROR testbench.sv(1342) @ 1025000: uvm_test_top.env.sb [axi4_scoreboard] MISMATCH ...
# UVM_INFO @ 0: reporter [RNTST] Running test base_test...
RE_SIM_UVM_LINE = re.compile(
    r"^(?:#\s*)?UVM_(?P<severity>INFO|WARNING|ERROR|FATAL)\s+"
    r"(?:(?P<file>\S+)\((?P<line>\d+)\)\s+)?"
    r"@\s+(?P<time>\d+)(?:\s*(?P<unit>[munpf]?s))?:\s+"
    r"(?P<component>\S+)\s+\[(?P<tag>[^\]]+)\]\s*(?P<message>.*)$"
)
RE_SIM_SUMMARY_COUNT = re.compile(
    r"^(?:#\s*)?UVM_(?P<severity>INFO|WARNING|ERROR|FATAL)\s*:\s*(?P<count>\d+)\s*$"
)
RE_SIM_VERDICT = re.compile(r"\bTEST\s+(?P<verdict>PASSED|FAILED)\b", re.I)
RE_RUNNING_TEST = re.compile(r"\[RNTST\]\s+Running test\s+(?P<test>\w+)")
# "   Write transactions : 1"  /  "  Read  CG : 42.4%"
RE_METRIC = re.compile(
    r"^(?:#\s*)?\s*(?P<label>[A-Za-z][A-Za-z0-9 _/()-]{0,40}?)\s*:\s*"
    r"(?P<value>-?\d+(?:\.\d+)?)\s*%?\s*$"
)
# Questa: "#    Time: 305 ns  Iteration: 68"   VCS: "$finish at simulation time 305000"
RE_FINISH_TIME = re.compile(r"\bTime:\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[munpf]?s)\b")
# Questa: "# End time: 04:05:58 on May 19,2026, Elapsed time: 0:00:03"
RE_ELAPSED = re.compile(r"Elapsed time:\s*(?P<h>\d+):(?P<m>\d{2}):(?P<s>\d{2})")
RE_SEED = re.compile(r"(?:-sv_seed|-svseed|\+ntb_random_seed=)\s*'?(?P<seed>\w+)")
# Standalone +KEY=VALUE only; "-voptargs=+acc=npr" is a tool flag, not config.
RE_PLUSARG = re.compile(
    r"(?:^|(?<=[\s'\"]))\+(?P<key>[A-Za-z_]\w*)=(?P<value>[^\s'\"]+)")

_TO_NS = {"s": 1e9, "ms": 1e6, "us": 1e3, "ns": 1.0, "ps": 1e-3, "fs": 1e-6}
# UVM plusargs that control the run harness rather than the DUT/testbench config.
_HARNESS_PLUSARGS = {"UVM_TESTNAME", "UVM_VERBOSITY", "UVM_TIMEOUT",
                     "UVM_MAX_QUIT_COUNT", "UVM_OBJECTION_TRACE",
                     "UVM_PHASE_TRACE", "UVM_CONFIG_DB_TRACE", "ntb_random_seed"}


def _snake(label: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", label.lower()).strip("_")


def _number(text: str) -> Any:
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _detect_simulator(text_head: str) -> str:
    head = text_head.lower()
    if "questa" in head or "modelsim" in head or "vsim" in head:
        return "questa"
    if "xcelium" in head or "xrun" in head or "irun" in head:
        return "xcelium"
    if "vcs" in head or "synopsys" in head:
        return "vcs"
    return "unknown"


def _parse_command_line(lines: List[str]) -> Dict[str, Any]:
    """Pull seed and +plusargs from the first simulator invocation line."""
    cfg: Dict[str, Any] = {}
    for line in lines[:80]:
        if "+UVM_TESTNAME" not in line and not RE_SEED.search(line):
            continue
        m = RE_SEED.search(line)
        if m:
            cfg["seed"] = _number(m.group("seed"))
        for p in RE_PLUSARG.finditer(line):
            key, value = p.group("key"), p.group("value")
            if key == "UVM_TESTNAME":
                cfg["test_name"] = value
            elif key not in _HARNESS_PLUSARGS:
                cfg[key.lower()] = _number(value)
        break
    return cfg


def parse_sim_log(path: str, lines: List[str]
                  ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    """Parse one simulator transcript.

    Returns (run_row or None, error_rows, error_line_count, unparsed_count).
    None means the file holds no UVM output at all, so it is not a run.
    """
    run_id = os.path.splitext(os.path.basename(path))[0]
    cfg = _parse_command_line(lines)
    cfg["simulator"] = _detect_simulator("".join(lines[:40]))

    errors: List[Dict[str, Any]] = []
    summary: Dict[str, int] = {}
    metrics: Dict[str, Any] = {}
    verdict: Optional[str] = None
    finish_ns: Optional[float] = None
    last_uvm_time = 0
    elapsed_s: Optional[int] = None
    saw_uvm = False
    in_report = False  # inside the run phase, where testbench summaries print
    unparsed = 0

    for raw in lines:
        line = raw.rstrip("\n\r")
        body = line[1:].strip() if line.startswith("#") else line.strip()
        if not body:
            continue

        m = RE_SIM_UVM_LINE.match(line) or RE_SIM_UVM_LINE.match(body)
        if m:
            saw_uvm = True
            in_report = True
            t = int(m.group("time"))
            last_uvm_time = max(last_uvm_time, t)
            if m.group("tag") == "RNTST" and "test_name" not in cfg:
                rt = RE_RUNNING_TEST.search(body)
                if rt:
                    cfg["test_name"] = rt.group("test")
            if m.group("severity") in ("ERROR", "FATAL"):
                msg = m.group("message").strip()
                errors.append({
                    "run_id": run_id,
                    "severity": m.group("severity"),
                    "time_ns": t,  # rescaled below once the tick unit is known
                    "component": m.group("component"),
                    "tag": m.group("tag"),
                    "message": msg,
                    "fingerprint": fingerprint(msg),
                })
            v = RE_SIM_VERDICT.search(m.group("message"))
            if v:
                verdict = v.group("verdict").upper()
            continue

        s = RE_SIM_SUMMARY_COUNT.match(line) or RE_SIM_SUMMARY_COUNT.match(body)
        if s:
            summary[s.group("severity")] = int(s.group("count"))
            continue

        if "UVM Report Summary" in body:
            in_report = False
            continue

        v = RE_SIM_VERDICT.search(body)
        if v and ("***" in body or body.upper().startswith("TEST")):
            verdict = v.group("verdict").upper()
            continue

        ft = RE_FINISH_TIME.search(body)
        if ft and saw_uvm:
            finish_ns = float(ft.group("value")) * _TO_NS[ft.group("unit")]
            continue

        el = RE_ELAPSED.search(body)
        if el and line.startswith("#"):  # the vsim step, not the compile steps
            elapsed_s = (int(el.group("h")) * 3600 + int(el.group("m")) * 60
                         + int(el.group("s")))
            continue

        if in_report:
            mm = RE_METRIC.match(body)
            if mm:
                metrics[METRIC_PREFIX + _snake(mm.group("label"))] = _number(
                    mm.group("value"))
                continue

        unparsed += 1

    if not saw_uvm and not summary:
        return None, [], 0, unparsed

    # UVM prints raw $time ticks; recover the tick size from the $finish time.
    ticks_per_ns = 1.0
    if finish_ns and last_uvm_time:
        ratio = last_uvm_time / finish_ns
        if ratio > 0:
            ticks_per_ns = 10 ** round(math.log10(ratio))
    for e in errors:
        e["time_ns"] = int(e["time_ns"] / ticks_per_ns)

    n_err = summary.get("ERROR", sum(e["severity"] == "ERROR" for e in errors))
    n_fatal = summary.get("FATAL", sum(e["severity"] == "FATAL" for e in errors))
    if verdict is None:
        # No explicit banner: fall back to the report counts. A log with no
        # report summary at all means the simulation never finished cleanly.
        verdict = "FAILED" if (n_err or n_fatal or not summary) else "PASSED"

    tags = [e["tag"] for e in errors]
    if not tags and verdict == "FAILED":
        tags = ["NO_REPORT_SUMMARY"] if not summary else ["TEST_FAILED"]

    row: Dict[str, Any] = {"run_id": run_id, **cfg}
    row.setdefault("test_name", "unknown_test")
    if finish_ns is not None:
        row["sim_time_ns"] = round(finish_ns, 3)
    if elapsed_s is not None:
        row["execution_time_ms"] = elapsed_s * 1000.0
    row.update(metrics)
    row["uvm_error_count"] = n_err
    row["uvm_fatal_count"] = n_fatal
    row["verdict"] = verdict
    row["pass_fail"] = "fail" if verdict == "FAILED" else "pass"
    row["uvm_error_total"] = n_err
    row["uvm_fatal_total"] = n_fatal
    row["uvm_warning_total"] = summary.get("WARNING", 0)
    row["primary_error_tag"] = tags[0] if tags else "NONE"
    row["distinct_error_tags"] = len(set(tags))
    row["trace_fingerprint"] = " || ".join(
        dict.fromkeys(e["fingerprint"] for e in errors)) or (
        "CLEAN" if verdict == "PASSED" else tags[0])
    row["error_trace"] = " ".join(e["message"] for e in errors)
    return row, errors, len(errors), unparsed
