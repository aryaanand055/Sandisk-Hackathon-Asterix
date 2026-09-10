#!/usr/bin/env python3
"""
Dataset validation -- prints summary statistics and per-field failure rates
so injected rules are visibly detectable before any ML is run.

Usage:
    python validate_dataset.py [path/to/synthetic_test_runs.csv]
"""

import sys

import pandas as pd

from data_model import SCHEMA


def _fail_rate(series: pd.Series) -> float:
    """Compute failure rate for a pass_fail Series."""
    return (series == "fail").mean()


def main() -> None:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "synthetic_test_runs.csv"
    df = pd.read_csv(csv_path)

    sep = "=" * 68
    thin = "-" * 68
    sub = "-" * 30

    print(sep)
    print("  DATASET VALIDATION REPORT")
    print(sep)

    # -- Shape --
    print(f"\nRows:    {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    # -- Column types --
    print(f"\n{'Column':<20s}  {'dtype':<10s}  {'nunique':>7s}  {'sample values'}")
    print(thin)
    for col in df.columns:
        uniq = df[col].nunique()
        sample = ", ".join(str(v) for v in df[col].dropna().unique()[:4])
        if uniq > 4:
            sample += ", ..."
        print(f"  {col:<18s}  {str(df[col].dtype):<10s}  {uniq:>7d}  {sample}")

    # -- Overall pass / fail --
    print(f"\n{sub}")
    print("  Overall Pass / Fail")
    print(sub)
    vc = df["pass_fail"].value_counts()
    for val, cnt in vc.items():
        print(f"    {val:>5s}: {cnt:>6,d}  ({cnt / len(df) * 100:.1f}%)")

    # -- Per-field failure rates --
    input_cats = ("configuration", "randomization", "environment")
    input_fields = [f.name for f in SCHEMA if f.category in input_cats]

    print(f"\n{sub}")
    print("  Failure Rate by Input Field")
    print(sub)
    for field_name in input_fields:
        if field_name not in df.columns:
            continue
        n_unique = df[field_name].nunique()
        print(f"\n  [{field_name}]  (unique values: {n_unique})")

        if n_unique > 10:
            # Bin continuous numeric fields for readable output
            binned = pd.qcut(df[field_name], q=5, duplicates="drop")
            grp = df.groupby(binned, observed=True)["pass_fail"].apply(_fail_rate)
        else:
            grp = df.groupby(df[field_name], observed=True)["pass_fail"].apply(
                _fail_rate
            )
        for val, rate in grp.items():
            n_rows = (df[field_name] == val).sum() if n_unique <= 10 else "-"
            n_str = f"  (n={n_rows})" if isinstance(n_rows, int) else ""
            print(f"    {str(val):<35s}  fail_rate = {rate:.3f}{n_str}")

    # -- Error type distribution --
    print(f"\n{sub}")
    print("  Error Type Distribution")
    print(sub)
    ec = df["error_type"].value_counts()
    for val, cnt in ec.items():
        print(f"    {val:<15s}: {cnt:>6,d}  ({cnt / len(df) * 100:.1f}%)")

    # Sanity check: error_type should be "none" iff pass_fail == "pass"
    mismatch_pass = ((df["pass_fail"] == "pass") & (df["error_type"] != "none")).sum()
    mismatch_fail = ((df["pass_fail"] == "fail") & (df["error_type"] == "none")).sum()
    if mismatch_pass or mismatch_fail:
        print(f"\n  WARNING: Mismatches: {mismatch_pass} pass rows with error, "
              f"{mismatch_fail} fail rows with 'none'")
    else:
        print(f"\n    [OK] error_type consistent with pass_fail")

    # -- Error type x pass/fail cross-tab --
    print(f"\n{sub}")
    print("  Error Type x Pass/Fail")
    print(sub)
    ct = pd.crosstab(df["error_type"], df["pass_fail"])
    print(ct.to_string(col_space=8))

    # -- Execution time stats --
    print(f"\n{sub}")
    print("  Execution Time (ms)")
    print(sub)
    et = df["execution_time"]
    for label, val in [("Mean", et.mean()), ("Median", et.median()),
                       ("Std", et.std()), ("Min", et.min()),
                       ("Max", et.max())]:
        print(f"    {label:<8s}: {val:>8.1f}")

    # -- Throughput stats --
    print(f"\n{sub}")
    print("  Throughput (ops/s)")
    print(sub)
    tp = df["throughput"]
    for label, val in [("Mean", tp.mean()), ("Median", tp.median()),
                       ("Std", tp.std()), ("Min", tp.min()),
                       ("Max", tp.max())]:
        print(f"    {label:<8s}: {val:>8.0f}")

    # -- Quick rule-signal spot checks --
    print(f"\n{sub}")
    print("  Spot Checks (rule signal visibility)")
    print(sub)

    overall = _fail_rate(df["pass_fail"])

    # One spot check per planted failure rule.  Each is a label plus the mask
    # that isolates it, so retuning a rule means editing one line here.
    spot_checks = [
        ("queue_depth>=64 & concurrency>=16 & scheduler=static",
         lambda d: (d["queue_depth"] >= 64) & (d["concurrency"] >= 16) &
                   (d["scheduler"] == "static")),
        ("compression=zstd & payload_entropy>0.80 & cache=small",
         lambda d: (d["compression"] == "zstd") & (d["payload_entropy"] > 0.80) &
                   (d["cache_size"] == "small")),
        ("power_mode=turbo & temperature>75",
         lambda d: (d["power_mode"] == "turbo") & (d["temperature"] > 75.0)),
        ("ecc_mode=off & injection_rate>0.20",
         lambda d: (d["ecc_mode"] == "off") & (d["injection_rate"] > 0.20)),
        ("burst_length>200 & queue_depth<=4 & traffic=high",
         lambda d: (d["burst_length"] > 200) & (d["queue_depth"] <= 4) &
                   (d["traffic_pattern"] == "high")),
    ]

    print(f"\n    (overall fail_rate: {overall:.3f})")
    for label, build_mask in spot_checks:
        try:
            mask = build_mask(df)
        except KeyError:
            continue
        if not mask.any():
            continue
        rate = _fail_rate(df.loc[mask, "pass_fail"])
        print(f"\n    {label}")
        print(f"      fail_rate = {rate:.3f}  "
              f"(ratio: {rate / overall:.1f}x, n={mask.sum()})")

    print(f"\n{sep}")
    print("  Validation complete.")
    print(sep)


if __name__ == "__main__":
    main()
