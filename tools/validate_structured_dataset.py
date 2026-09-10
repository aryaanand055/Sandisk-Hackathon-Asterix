#!/usr/bin/env python3
"""
Validator for the structured verification datasets.

Re-reads what the generator wrote - without trusting it - and checks that the
invariants declared in ground_truth.json actually hold:

  * uvm.log parses with the existing uvm_intel.log_parser (legacy mode still works)
  * verdict in uvm.log agrees with status in outcomes.csv, run for run
  * uvm_error_count / uvm_fatal_count in outcomes.csv match the lines in uvm.log
  * scoreboard_mismatches matches the MISMATCH rows in transactions.csv
  * run_id sets line up across every file that carries one
  * no transaction starts after its run finished
  * passing runs carry no failure_type
  * no derived metric leaked into an input file

Column aliases are read from MANIFEST.json and undone before checking, which
doubles as a test that the alias map is complete and correct.

Usage
-----
    python tools/validate_structured_dataset.py data/datasets/*
"""

import glob
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from uvm_intel.log_parser import ParseStats, parse_lines  # noqa: E402

# Names that must never appear as a column in a raw input file.
DERIVED_FORBIDDEN = {
    "latency", "latency_ns", "response_latency", "failure_probability",
    "risk_score", "failure_rate", "correlation", "feature_importance",
    "shap_value", "cluster_id", "anomaly_score", "pareto_rank",
    "confidence", "root_cause", "predicted_status", "influence_score",
}


class Check:
    def __init__(self):
        self.rows = []

    def add(self, name, ok, detail=""):
        self.rows.append((name, bool(ok), detail))

    def report(self, title):
        print(f"\n{title}")
        print("-" * len(title))
        for name, ok, detail in self.rows:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {name}" + (f"  -- {detail}" if detail else ""))
        return all(ok for _, ok, _ in self.rows)


def load_csv(path, aliases):
    """Read a CSV and undo the profile's column aliasing."""
    df = pd.read_csv(path, low_memory=False)
    inverse = {v: k for k, v in (aliases or {}).items()}
    return df.rename(columns=inverse)


def validate(dataset_dir):
    manifest_path = os.path.join(dataset_dir, "MANIFEST.json")
    if not os.path.isfile(manifest_path):
        return None
    with open(manifest_path) as fh:
        man = json.load(fh)
    with open(os.path.join(dataset_dir, "ground_truth.json")) as fh:
        gt = json.load(fh)

    alias = man.get("column_aliases", {})
    chk = Check()

    def present(name):
        return os.path.isfile(os.path.join(dataset_dir, name))

    frames = {}
    for name in ("config.csv", "randomization.csv", "transactions.csv",
                 "telemetry.csv", "outcomes.csv", "registers.csv"):
        if present(name):
            frames[name] = load_csv(os.path.join(dataset_dir, name), alias.get(name, {}))

    # ── declared files exist, and nothing undeclared is lying around ───────
    declared = set(man["files"])
    on_disk = {f for f in os.listdir(dataset_dir)
               if f.endswith((".csv", ".log"))}
    chk.add("declared files all present", declared <= on_disk | {"uvm.log"},
            f"missing={sorted(declared - on_disk)}")
    chk.add("no undeclared csv/log files on disk", on_disk <= declared,
            f"extra={sorted(on_disk - declared)}")

    # ── uvm.log parses with the legacy parser ─────────────────────────────
    runs_df = None
    if present("uvm.log"):
        stats = ParseStats()
        with open(os.path.join(dataset_dir, "uvm.log"), encoding="utf-8") as fh:
            runs, errors = parse_lines(fh, stats)
        runs_df = pd.DataFrame(runs)
        chk.add("uvm.log parses with uvm_intel.log_parser",
                stats.runs == man["n_runs"] and stats.malformed_blocks == 0,
                f"runs={stats.runs} expected={man['n_runs']} "
                f"malformed={stats.malformed_blocks} error_lines={stats.error_lines}")
        chk.add("legacy parser recovers config fields from the log",
                {"test_name", "seed", "temperature_c", "voltage_mv"} <= set(runs_df.columns),
                f"got {len(runs_df.columns)} columns")

    out = frames.get("outcomes.csv")

    # ── log verdict vs outcomes.csv ───────────────────────────────────────
    if out is not None and runs_df is not None:
        m = out.merge(runs_df[["run_id", "pass_fail", "uvm_error_total",
                               "uvm_fatal_total"]], on="run_id", how="inner",
                      suffixes=("", "_log"))
        chk.add("every run in outcomes.csv appears in uvm.log", len(m) == len(out),
                f"joined={len(m)} outcomes={len(out)}")
        bad = (m["pass_fail"] != m["pass_fail_log"]).sum()
        chk.add("verdict agrees between uvm.log and outcomes.csv", bad == 0,
                f"{bad} disagreements")
        bad = (m["uvm_error_count"] != m["uvm_error_total"]).sum()
        chk.add("uvm_error_count matches UVM_ERROR lines in the log", bad == 0,
                f"{bad} mismatches")
        bad = (m["uvm_fatal_count"] != m["uvm_fatal_total"]).sum()
        chk.add("uvm_fatal_count matches UVM_FATAL lines in the log", bad == 0,
                f"{bad} mismatches")

    # ── transactions reconcile with outcomes ──────────────────────────────
    txn = frames.get("transactions.csv")
    if out is not None and txn is not None:
        mism = (txn[txn["checker_result"] == "MISMATCH"]
                .groupby("run_id").size().rename("counted"))
        j = out.set_index("run_id")[["scoreboard_mismatches"]].join(mism).fillna(0)
        bad = (j["scoreboard_mismatches"] != j["counted"]).sum()
        chk.add("scoreboard_mismatches equals MISMATCH rows in transactions.csv",
                bad == 0, f"{bad} runs disagree")

        end = out.set_index("run_id")["execution_time_ms"] * 1e6
        starts = txn.groupby("run_id")["start_time_ns"].max()
        joined = pd.concat([end.rename("end_ns"), starts.rename("last_start")], axis=1).dropna()
        bad = (joined["last_start"] > joined["end_ns"]).sum()
        chk.add("no transaction starts after its run ended", bad == 0,
                f"{bad} runs violate")

    # ── outcome self-consistency ──────────────────────────────────────────
    if out is not None:
        passing = out[out["pass_fail"] == "pass"]
        chk.add("passing runs carry failure_type NONE",
                (passing["failure_type"] == "NONE").all(),
                f"{(passing['failure_type'] != 'NONE').sum()} violations")
        failing = out[out["pass_fail"] == "fail"]
        chk.add("failing runs all carry an error code",
                (failing["error_code"].astype(str).str.len() > 0).all())
        rate = round(float((out["pass_fail"] == "fail").mean()), 4)
        chk.add("fail rate matches the manifest", abs(rate - man["fail_rate"]) < 0.0005,
                f"csv={rate} manifest={man['fail_rate']}")

    # ── run_id alignment across files ─────────────────────────────────────
    keyed = {n: set(df["run_id"]) for n, df in frames.items() if "run_id" in df.columns}
    if len(keyed) > 1:
        base_name, base = next(iter(keyed.items()))
        for name, ids in keyed.items():
            chk.add(f"run_id set of {name} aligns with {base_name}", ids == base,
                    f"only_here={len(ids - base)} only_there={len(base - ids)}")

    # ── no derived metrics in raw inputs ──────────────────────────────────
    leaked = {}
    for name, df in frames.items():
        hits = [c for c in df.columns if c.strip().lower() in DERIVED_FORBIDDEN]
        if hits:
            leaked[name] = hits
    chk.add("no derived analytics leaked into input files", not leaked, str(leaked))

    # ── waveforms ─────────────────────────────────────────────────────────
    for w in man.get("waveforms", []):
        p = os.path.join(dataset_dir, w["path"].replace("/", os.sep))
        chk.add(f"waveform {os.path.basename(w['path'])} exists and is a VCD",
                os.path.isfile(p) and open(p).readline().startswith("$date"))
    wdir = os.path.join(dataset_dir, "waveforms")
    if os.path.isdir(wdir):
        declared_w = {os.path.basename(w["path"]) for w in man.get("waveforms", [])}
        found_w = {f for f in os.listdir(wdir) if f.endswith(".vcd")}
        chk.add("no stale waveform files", found_w == declared_w,
                f"extra={sorted(found_w - declared_w)}")

    # ── ground-truth rule support ─────────────────────────────────────────
    # Support is judged as a share of the corpus, so the small test bundles are
    # held to the same standard as the big ones without needing 50 raw hits.
    weak = [f"{r['id']}({r['observed']['rows_matched']})" for r in gt["rules"]
            if (r["observed"]["rows_matched"] or 0) < 25
            or (r["observed"]["match_share"] or 0) < 0.01]
    chk.add("every ground-truth rule fires on >=1% of runs (min 25)", not weak,
            f"under-supported: {weak}")
    flat = [r["id"] for r in gt["rules"]
            if (r["observed"]["lift"] or 0) < 1.3]
    chk.add("every ground-truth rule shows lift >= 1.3", not flat,
            f"weak lift: {flat}")

    ok = chk.report(f"{man['dataset']}  ({os.path.basename(dataset_dir)})")
    return ok


def main():
    targets = sys.argv[1:] or sorted(glob.glob(os.path.join("data", "datasets", "*")))
    results = {}
    for t in targets:
        if os.path.isdir(t):
            r = validate(t)
            if r is not None:
                results[t] = r
    print("\n" + "=" * 60)
    for t, ok in results.items():
        print(f"  {'OK  ' if ok else 'FAIL'}  {t}")
    print("=" * 60)
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
