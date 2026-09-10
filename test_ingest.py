#!/usr/bin/env python3
"""
Tests for ingest.py.

Covers the four things real logs vary in -- format, field names, field values,
missing data -- and then proves the normalised frame survives the real
preprocess.py -> train_baseline.py path.

    python test_ingest.py
"""

import json
import random
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from ingest import (
    ingest, read_any, detect_target, IngestReport, MISSING_LABEL, OTHER_LABEL,
)

PASSED = FAILED = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  [ok]   {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name}" + (f"\n         {detail}" if detail else ""))


# =========================================================================
# Synthetic corpora -- the SAME 60 runs rendered four different ways
# =========================================================================

def _rows(n: int = 60, seed: int = 7):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        cache = rng.choice(["small", "medium", "large"])
        sched = rng.choice(["static", "dynamic", "adaptive"])
        # A real signal so the model has something to learn.
        fail = (cache == "small" and sched == "dynamic") or rng.random() < 0.15
        out.append({
            "run_id": f"RUN-{i:04d}",
            "cache_size": cache,
            "scheduler": sched,
            "memory_mb": rng.choice([256, 512, 1024, 2048]),
            "temperature": round(rng.uniform(25, 95), 1),
            "verdict": "FAILED" if fail else "PASSED",
        })
    return out


def as_uvm_blocks(rows) -> str:
    parts = []
    for r in rows:
        cfg = {k: r[k] for k in ("cache_size", "scheduler", "memory_mb", "temperature")}
        parts.append(
            f"UVM SIMULATION LOG :: {r['run_id']}\n"
            f"[CONFIG]\n{json.dumps(cfg)}\n[/CONFIG]\n"
            f"** UVM_REPORT :: TEST {r['verdict']}\n"
        )
    return "\n".join(parts)


def as_key_value(rows) -> str:
    parts = []
    for r in rows:
        parts.append(
            f"TEST_ID: {r['run_id']}\n"
            f"CACHE: {r['cache_size']}\n"
            f"SCHED: {r['scheduler']}\n"
            f"MEM: {r['memory_mb']}\n"
            f"TEMP: {r['temperature']}\n"
            f"RESULT: {r['verdict']}\n"
        )
    return "\n".join(parts)


def as_jsonl(rows) -> str:
    return "\n".join(json.dumps(r) for r in rows)


def as_csv(rows) -> str:
    return pd.DataFrame(rows).to_csv(index=False)


# =========================================================================
# 1. Format variation
# =========================================================================

def test_formats():
    print("\n[1] Format variation - same 60 runs, four renderings")
    rows = _rows()
    expected_fail = sum(1 for r in rows if r["verdict"] == "FAILED")

    for name, text in (
        ("uvm blocks", as_uvm_blocks(rows)),
        ("key:value ", as_key_value(rows)),
        ("jsonl     ", as_jsonl(rows)),
        ("csv       ", as_csv(rows)),
    ):
        try:
            df, rep = ingest(text)
            ok_rows = len(df) == len(rows)
            fails = int((df[rep.target_column] == "fail").sum())
            ok_fails = fails == expected_fail
            check(f"{name} -> {len(df)} rows, {fails} fail "
                  f"(fmt={rep.source_format})",
                  ok_rows and ok_fails,
                  f"expected {len(rows)} rows / {expected_fail} fail")
        except Exception as exc:
            check(f"{name} parses", False, f"{type(exc).__name__}: {exc}")

    # Regression: a banner id must stay an identifier. If 'RUN-0007' is reduced
    # to the integer 7 it becomes a numeric predictor, and any chronological
    # drift in the corpus leaks into the model as row order.
    text = "\n".join(
        f"UVM SIMULATION LOG :: RUN-{i:04d}\n[CONFIG]\n"
        f"{json.dumps({k: r[k] for k in ('cache_size', 'scheduler')})}\n[/CONFIG]\n"
        f"** UVM_REPORT :: TEST {r['verdict']}\n"
        for i, r in enumerate(rows))
    df, rep = ingest(text)
    idcol = "row_id"
    from preprocess import detect_column_roles
    roles = detect_column_roles(df)
    check("banner id keeps its stem (RUN-0000, not 0)",
          idcol in df.columns and str(df[idcol].iloc[0]) == "RUN-0000",
          f"got {df[idcol].iloc[0] if idcol in df else 'missing'!r}")
    check("banner id never becomes a predictor",
          idcol not in roles["categorical"] + roles["numeric"],
          f"roles={ {k: v for k, v in roles.items() if v} }")


# =========================================================================
# 2. Field-name variation
# =========================================================================

def test_field_names():
    print("\n[2] Field-name variation")
    rows = _rows()
    renamed = [
        {"simulation_id": r["run_id"], "cache_mem_cfg": r["cache_size"],
         "sched_type": r["scheduler"], "dram_mb": r["memory_mb"],
         "die_temp_c": r["temperature"], "test_status": r["verdict"]}
        for r in rows
    ]
    df, rep = ingest(as_jsonl(renamed))
    check("arbitrary field names need no mapping",
          len(df) == len(rows) and rep.target_column == "test_status",
          f"target={rep.target_column}, cols={list(df.columns)}")

    df2, rep2 = ingest(as_jsonl(renamed),
                       column_overrides={"cache_mem_cfg": "cache_size"})
    check("column_overrides rename applied",
          "cache_size" in df2.columns and "cache_mem_cfg" not in df2.columns)


# =========================================================================
# 3. Value variation
# =========================================================================

def test_value_variants():
    print("\n[3] Value variation")
    rows = _rows()
    spellings = {"small": ["small", "SMALL", "Small", "small "],
                 "medium": ["medium", "MEDIUM", "Medium"],
                 "large": ["large", "LARGE", "Large"]}
    rng = random.Random(3)
    noisy = []
    for r in rows:
        d = dict(r)
        d["cache_size"] = rng.choice(spellings[r["cache_size"]])
        noisy.append(d)

    df, rep = ingest(as_jsonl(noisy))
    check("case/whitespace variants merge to 3 levels",
          df["cache_size"].nunique() == 3,
          f"got {sorted(df['cache_size'].unique())}")
    check("merges are reported", "cache_size" in rep.value_merges)

    # Abbreviations need domain knowledge -> value_overrides.
    abbrev = []
    for r in rows:
        d = dict(r)
        d["cache_size"] = {"small": "S", "medium": "M", "large": "L"}[r["cache_size"]]
        abbrev.append(d)
    df2, _ = ingest(as_jsonl(abbrev),
                    value_overrides={"cache_size": {"S": "small", "M": "medium",
                                                    "L": "large"}})
    check("value_overrides expand abbreviations",
          set(df2["cache_size"].unique()) == {"small", "medium", "large"},
          f"got {sorted(df2['cache_size'].unique())}")


def test_verdict_vocabulary():
    print("\n[4] Verdict vocabulary")
    rows = _rows()
    for pass_word, fail_word in (("SUCCESS", "FAILURE"), ("ok", "crash"),
                                 ("GREEN", "RED"), ("1", "0")):
        variant = [{**r, "verdict": pass_word if r["verdict"] == "PASSED"
                    else fail_word} for r in rows]
        try:
            df, rep = ingest(as_jsonl(variant))
            vals = set(df[rep.target_column].unique())
            check(f"'{pass_word}'/'{fail_word}' -> pass/fail",
                  vals == {"pass", "fail"}, f"got {vals}")
        except Exception as exc:
            check(f"'{pass_word}'/'{fail_word}' handled", False,
                  f"{type(exc).__name__}: {exc}")

    # preprocess.py's own heuristic misses SUCCESS/FAILURE; confirm we fix it.
    from preprocess import _is_binary_target
    s = pd.Series(["SUCCESS", "FAILURE"] * 10)
    check("(baseline) preprocess alone cannot read SUCCESS/FAILURE",
          not _is_binary_target(s))


# =========================================================================
# 5. Missing data
# =========================================================================

def test_missing_data():
    print("\n[5] Missing data")
    rows = _rows()
    rng = random.Random(11)
    holey = []
    for r in rows:
        d = dict(r)
        if rng.random() < 0.25:
            d["temperature"] = None            # numeric gap
        if rng.random() < 0.25:
            d["cache_size"] = None             # categorical gap
        if rng.random() < 0.20:
            d["scheduler"] = rng.choice(["", "N/A", "null", "-"])  # nullish text
        holey.append(d)

    df, rep = ingest(as_jsonl(holey))
    check("no NaN survives", not df.isna().any().any(),
          f"NaN in {df.columns[df.isna().any()].tolist()}")
    check("numeric gaps filled with median", "temperature" in rep.numeric_filled)
    check("categorical gaps become an explicit level",
          MISSING_LABEL in set(df["cache_size"].unique()))
    check("'N/A'/'null'/'-' treated as missing",
          MISSING_LABEL in set(df["scheduler"].unique()),
          f"got {sorted(df['scheduler'].unique())}")

    # Rows with no verdict cannot be trained on and must go.
    unlabelled = [dict(r) for r in rows]
    for r in unlabelled[:10]:
        r["verdict"] = None
    df2, rep2 = ingest(as_jsonl(unlabelled))
    check("unlabelled rows dropped",
          len(df2) == len(rows) - 10 and rep2.target_rows_dropped == 10,
          f"rows={len(df2)}, dropped={rep2.target_rows_dropped}")

    # A mostly-empty column is noise, not signal.
    sparse = [{**r, "rare_probe": (r["run_id"] if random.Random(2).random() < 0.05
                                   else None)} for r in rows]
    df3, rep3 = ingest(as_jsonl(sparse))
    check("mostly-empty column dropped",
          "rare_probe" not in df3.columns,
          f"cols={list(df3.columns)}")


# =========================================================================
# 6. Cardinality
# =========================================================================

def test_cardinality():
    print("\n[6] Cardinality control")
    rows = _rows()
    rng = random.Random(5)
    wide = [{**r,
             "commit_sha": f"{rng.randrange(16**8):08x}",        # near-unique
             "toolchain": f"v{rng.randrange(200)}"}              # wide but useful
            for r in rows]
    df, rep = ingest(as_jsonl(wide), max_levels=10)

    check("near-unique junk column dropped",
          "commit_sha" not in df.columns,
          f"cols={list(df.columns)}")
    check("wide column capped, not discarded",
          "toolchain" in df.columns and df["toolchain"].nunique() <= 10,
          f"levels={df['toolchain'].nunique() if 'toolchain' in df else 'dropped'}")
    if "toolchain" in df.columns:
        check("capped tail bucketed into __other__",
              OTHER_LABEL in set(df["toolchain"].unique()))

    # run_id is a join key: it must survive ingest so predictions can be traced
    # back, while still being kept out of the feature matrix by preprocess.
    check("run_id preserved as a join key", "run_id" in df.columns)
    from preprocess import detect_column_roles
    roles = detect_column_roles(df)
    check("run_id excluded from features downstream",
          "run_id" in roles["identifier"]
          and "run_id" not in roles["categorical"] + roles["numeric"],
          f"roles={ {k: v for k, v in roles.items() if v} }")


# =========================================================================
# 7. Failure modes should be loud, not silent
# =========================================================================

def test_error_paths():
    print("\n[7] Error handling")

    def raises(fn, needle):
        try:
            fn()
            return False, "no exception"
        except ValueError as e:
            return (needle.lower() in str(e).lower()), str(e)[:90]
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    ok, msg = raises(lambda: ingest("\n".join(
        json.dumps({"a": 1, "b": "x"}) for _ in range(5))), "verdict")
    check("no verdict column -> clear error", ok, msg)

    ok, msg = raises(lambda: ingest("\n".join(
        json.dumps({"cfg": "a", "verdict": "PASSED"}) for _ in range(5))),
        "verdict")
    check("single-class target -> clear error", ok, msg)

    ok, msg = raises(lambda: ingest("   "), "empty")
    check("empty input -> clear error", ok, msg)

    rows = _rows()
    df, rep = ingest(as_jsonl([{**r, "verdict":
                                ("WOBBLE" if i < 5 else r["verdict"])}
                               for i, r in enumerate(rows)]))
    check("unknown verdict values dropped and warned",
          len(df) == len(rows) - 5 and any("unrecognised" in w
                                           for w in rep.warnings),
          f"rows={len(df)}, warnings={rep.warnings}")


# =========================================================================
# 8. End-to-end through the real pipeline
# =========================================================================

def test_end_to_end():
    print("\n[8] End-to-end: ingest -> preprocess -> train_baseline")
    rows = _rows(n=400, seed=21)
    rng = random.Random(13)

    # Everything wrong at once: block format, odd names, mixed spellings,
    # missing values, a junk high-cardinality column, exotic verdict words.
    messy = []
    for r in rows:
        messy.append({
            "run_id": r["run_id"],
            "cache_mem_cfg": rng.choice(
                {"small": ["small", "SMALL", "Small"],
                 "medium": ["medium", "MEDIUM"],
                 "large": ["large", "Large"]}[r["cache_size"]]),
            "sched_type": r["scheduler"],
            "dram_mb": r["memory_mb"] if rng.random() > 0.2 else None,
            "die_temp_c": r["temperature"],
            "commit_sha": f"{rng.randrange(16**8):08x}",
            "test_status": "SUCCESS" if r["verdict"] == "PASSED" else "FAILURE",
        })

    text = "\n".join(
        f"UVM SIMULATION LOG :: {m['run_id']}\n"
        f"[CONFIG]\n{json.dumps({k: v for k, v in m.items() if k not in ('run_id', 'test_status')})}\n[/CONFIG]\n"
        f"** UVM_REPORT :: TEST {m['test_status']}\n"
        for m in messy
    )

    df, rep = ingest(text)
    rep.print_summary()

    with tempfile.TemporaryDirectory() as td:
        csv_path = str(Path(td) / "runs.csv")
        df.to_csv(csv_path, index=False)

        from preprocess import preprocess
        try:
            result = preprocess(csv_path, test_size=0.25, seed=42)
            check("preprocess.py accepts the ingested frame", True)
            check("target auto-detected downstream",
                  result.roles["target"] == [rep.target_column],
                  f"roles.target={result.roles['target']}")
            check("no NaN reaches the feature matrix",
                  not result.X_full.isna().any().any())
            check("feature count stays sane (no one-hot explosion)",
                  result.X_full.shape[1] < 40,
                  f"{result.X_full.shape[1]} encoded columns")
        except Exception as exc:
            check("preprocess.py accepts the ingested frame", False,
                  f"{type(exc).__name__}: {exc}")
            return

        from train_baseline import train
        import io, contextlib
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                _model, payload = train(
                    csv_path=csv_path, model_name="random_forest", seed=42,
                    output_predictions=str(Path(td) / "pred.csv"),
                    output_results=str(Path(td) / "res.json"))
            auc = payload["metrics"]["roc_auc"]
            check(f"RandomForest trains and scores (ROC-AUC={auc})", True)
            check("learned the planted signal (ROC-AUC > 0.75)", auc > 0.75,
                  f"ROC-AUC={auc}")
            top = payload["feature_importances"][0]["feature"]
            check(f"top feature is a real knob ('{top}')",
                  top in ("cache_mem_cfg", "sched_type"),
                  f"got '{top}'")
        except Exception as exc:
            check("train_baseline.train runs", False,
                  f"{type(exc).__name__}: {exc}")


# =========================================================================

def main() -> int:
    print("=" * 64)
    print("  ingest.py test suite")
    print("=" * 64)

    test_formats()
    test_field_names()
    test_value_variants()
    test_verdict_vocabulary()
    test_missing_data()
    test_cardinality()
    test_error_paths()
    test_end_to_end()

    print("\n" + "=" * 64)
    print(f"  {PASSED} passed, {FAILED} failed")
    print("=" * 64)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
