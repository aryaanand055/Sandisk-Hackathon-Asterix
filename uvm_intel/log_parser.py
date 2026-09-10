#!/usr/bin/env python3
"""
Phase 1 - UVM log parser.

Turns raw simulation logs into two tidy frames:

    runs   - one row per run: configuration + metrics + verdict
    errors - one row per UVM_ERROR / UVM_FATAL line, with a seed-invariant
             fingerprint used later for clustering

The scanner is a single pass over the lines with cheap ``startswith`` guards
before any regex, so a 50k-run corpus parses in a few seconds.

Usage
-----
    python -m uvm_intel.log_parser data/uvm_logs/*.log
"""

import argparse
import glob
import json
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd

from .log_format import (
    BANNER, CONFIG_CLOSE, CONFIG_OPEN, METRICS_CLOSE, METRICS_OPEN,
    RE_SUMMARY_COUNT, RE_UVM_LINE, RE_VERDICT, fingerprint,
)

# Severities that count as a failure signal.
_FAIL_SEVERITIES = ("ERROR", "FATAL")


class ParseStats:
    """Counters describing what the parser saw - surfaced in the UI."""

    def __init__(self) -> None:
        self.files = 0
        self.lines = 0
        self.runs = 0
        self.error_lines = 0
        self.malformed_blocks = 0
        self.unparsed_lines = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "files": self.files, "lines": self.lines, "runs": self.runs,
            "error_lines": self.error_lines,
            "malformed_blocks": self.malformed_blocks,
            "unparsed_lines": self.unparsed_lines,
        }


def _flush(block: Dict[str, Any], runs: List[Dict], errors: List[Dict],
           stats: ParseStats) -> None:
    """Commit one finished run block to the output lists."""
    cfg = block.get("config")
    if not cfg or not block.get("run_id"):
        if block.get("run_id") or cfg:
            stats.malformed_blocks += 1
        return

    run_id = block["run_id"]
    row: Dict[str, Any] = {"run_id": run_id, **cfg}
    row.pop("run_id", None)
    row["run_id"] = run_id
    row.update(block.get("metrics", {}))

    row["verdict"] = block.get("verdict", "UNKNOWN")
    row["pass_fail"] = "fail" if row["verdict"] == "FAILED" else "pass"
    counts = block.get("summary", {})
    row["uvm_error_total"] = counts.get("ERROR", 0)
    row["uvm_fatal_total"] = counts.get("FATAL", 0)
    row["uvm_warning_total"] = counts.get("WARNING", 0)

    blk_errors = block.get("errors", [])
    tags = [e["tag"] for e in blk_errors]
    row["primary_error_tag"] = tags[0] if tags else "NONE"
    row["distinct_error_tags"] = len(set(tags))
    # Whole-run fingerprint: the ordered set of distinct error templates.
    row["trace_fingerprint"] = " || ".join(
        dict.fromkeys(e["fingerprint"] for e in blk_errors)) or "CLEAN"
    row["error_trace"] = " ".join(e["message"] for e in blk_errors)

    runs.append(row)
    errors.extend(blk_errors)
    stats.runs += 1


def parse_lines(lines: Iterable[str], stats: ParseStats
                ) -> Tuple[List[Dict], List[Dict]]:
    """Single-pass scan over log lines."""
    runs: List[Dict] = []
    errors: List[Dict] = []
    block: Dict[str, Any] = {}
    mode = None  # None | "config" | "metrics"
    buf: List[str] = []

    for raw in lines:
        stats.lines += 1
        line = raw.rstrip("\n\r")

        # --- JSON payload accumulation -----------------------------------
        if mode == "config":
            if line == CONFIG_CLOSE:
                try:
                    block["config"] = json.loads("".join(buf))
                except json.JSONDecodeError:
                    stats.malformed_blocks += 1
                mode, buf = None, []
            else:
                buf.append(line)
            continue
        if mode == "metrics":
            if line == METRICS_CLOSE:
                try:
                    block["metrics"] = json.loads("".join(buf))
                except json.JSONDecodeError:
                    stats.malformed_blocks += 1
                mode, buf = None, []
            else:
                buf.append(line)
            continue

        if not line:
            continue

        # --- Block boundary ----------------------------------------------
        if line.startswith(BANNER):
            _flush(block, runs, errors, stats)
            block = {"run_id": line[len(BANNER):].strip(), "errors": [],
                     "summary": {}}
            continue

        if line == CONFIG_OPEN:
            mode, buf = "config", []
            continue
        if line == METRICS_OPEN:
            mode, buf = "metrics", []
            continue

        # --- UVM report lines --------------------------------------------
        if line.startswith("UVM_"):
            m = RE_UVM_LINE.match(line)
            if m:
                sev = m.group("severity")
                if sev in _FAIL_SEVERITIES:
                    msg = m.group("message")
                    block.setdefault("errors", []).append({
                        "run_id": block.get("run_id", ""),
                        "severity": sev,
                        "time_ns": int(m.group("time_ns")),
                        "component": m.group("component"),
                        "tag": m.group("tag"),
                        "message": msg,
                        "fingerprint": fingerprint(msg),
                    })
                    stats.error_lines += 1
                continue
            s = RE_SUMMARY_COUNT.match(line)
            if s:
                block.setdefault("summary", {})[s.group("severity")] = int(
                    s.group("count"))
                continue
            stats.unparsed_lines += 1
            continue

        if line.startswith("**"):
            v = RE_VERDICT.match(line)
            if v:
                block["verdict"] = v.group("verdict")
            continue

        # Separators and banners are expected noise; anything else is not.
        if not line.startswith("=") and not line.startswith("---"):
            stats.unparsed_lines += 1

    _flush(block, runs, errors, stats)
    return runs, errors


def parse_files(paths: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame, ParseStats]:
    """Parse one or more log files into (runs, errors, stats)."""
    stats = ParseStats()
    all_runs: List[Dict] = []
    all_errors: List[Dict] = []

    for path in paths:
        stats.files += 1
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            r, e = parse_lines(fh, stats)
        all_runs.extend(r)
        all_errors.extend(e)

    runs_df = pd.DataFrame(all_runs)
    errors_df = pd.DataFrame(all_errors) if all_errors else pd.DataFrame(
        columns=["run_id", "severity", "time_ns", "component", "tag",
                 "message", "fingerprint"])
    return runs_df, errors_df, stats


def parse_text(text: str) -> Tuple[pd.DataFrame, pd.DataFrame, ParseStats]:
    """Parse a log corpus already held in memory (used by the API)."""
    stats = ParseStats()
    stats.files = 1
    runs, errors = parse_lines(text.splitlines(), stats)
    runs_df = pd.DataFrame(runs)
    errors_df = pd.DataFrame(errors) if errors else pd.DataFrame(
        columns=["run_id", "severity", "time_ns", "component", "tag",
                 "message", "fingerprint"])
    return runs_df, errors_df, stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse UVM logs into tables.")
    ap.add_argument("paths", nargs="+", help="Log files or globs")
    ap.add_argument("--out-runs", default="data/parsed_runs.csv")
    ap.add_argument("--out-errors", default="data/parsed_errors.csv")
    args = ap.parse_args()

    paths: List[str] = []
    for p in args.paths:
        paths.extend(sorted(glob.glob(p)) or [p])

    runs, errors, stats = parse_files(paths)
    print(json.dumps(stats.as_dict(), indent=2))
    print(f"\nruns   : {runs.shape}")
    print(f"errors : {errors.shape}")
    if not runs.empty:
        print(f"\nverdicts: {runs['pass_fail'].value_counts().to_dict()}")
        print(f"columns : {list(runs.columns)}")
    runs.to_csv(args.out_runs, index=False)
    errors.to_csv(args.out_errors, index=False)
    print(f"\n  -> {args.out_runs}\n  -> {args.out_errors}")


if __name__ == "__main__":
    main()
