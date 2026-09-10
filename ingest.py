#!/usr/bin/env python3
"""
Tolerant ingestion layer for heterogeneous test-run logs.

`preprocess.py` already auto-detects column roles, so arbitrary *field names*
work downstream without any mapping.  What it cannot survive is raw log text
instead of a CSV, NaN in numeric predictors (sklearn raises), a verdict column
whose vocabulary it does not recognise, one value spelled four ways, or a
mid-cardinality column that explodes into hundreds of dummies.

This module closes exactly those gaps and hands `preprocess.py` a clean frame.

    raw logs (any shape) -> read_any -> normalize -> DataFrame / CSV
                                                          |
                                                          v
                                         preprocess.py -> train_baseline.py

Usage
-----
    python ingest.py --input raw_logs.log --output runs.csv
    python train_baseline.py --input runs.csv

Library mode
------------
    from ingest import ingest
    df, report = ingest("raw_logs.log")
    report.print_summary()
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Imported rather than redefined so both layers agree on what counts as text
# and what counts as an identifier; drift between them would be a silent bug.
from preprocess import _ID_PATTERNS, _is_text_dtype


# =========================================================================
# Vocabulary
# =========================================================================

# Verdict synonyms.  This is the one place a built-in dictionary is justified:
# the pass/fail vocabulary is domain-general, and `preprocess._is_binary_target`
# only recognises a narrow slice of it (it misses SUCCESS/FAILURE, OK/CRASH).
_PASS_WORDS = {
    "pass", "passed", "passing", "success", "successful", "ok", "okay",
    "good", "clean", "green", "true", "1", "yes", "y", "complete",
    "completed", "done",
}
_FAIL_WORDS = {
    "fail", "failed", "failing", "failure", "error", "errored", "crash",
    "crashed", "bad", "red", "false", "0", "no", "n", "abort", "aborted",
    "timeout", "timedout", "fatal",
}

# Sentinel written into categorical columns where a value was absent, so that
# missingness survives one-hot encoding as its own signal instead of silently
# becoming an all-zero row.
MISSING_LABEL = "__missing__"
OTHER_LABEL = "__other__"

_NULLISH = {"", "na", "n/a", "nan", "none", "null", "nil", "-", "--", "?",
            "unknown", "unspecified", "<none>"}


# =========================================================================
# Report
# =========================================================================

@dataclass
class IngestReport:
    """What the ingester saw, guessed, and changed."""
    source_format: str = "unknown"
    records_parsed: int = 0
    rows_final: int = 0

    target_column: Optional[str] = None
    target_values_before: Dict[str, int] = field(default_factory=dict)
    target_rows_dropped: int = 0

    value_merges: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    numeric_filled: Dict[str, int] = field(default_factory=dict)
    categorical_filled: Dict[str, int] = field(default_factory=dict)
    columns_dropped: List[Tuple[str, str]] = field(default_factory=list)
    cardinality_capped: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    coerced_to_numeric: List[str] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)

    def print_summary(self) -> None:
        line = "=" * 64
        print(f"\n{line}\n  INGEST REPORT\n{line}")
        print(f"  Detected format      : {self.source_format}")
        print(f"  Records parsed       : {self.records_parsed:,}")
        print(f"  Rows after cleaning  : {self.rows_final:,}")

        print(f"\n  Target column        : {self.target_column or '(not found)'}")
        if self.target_values_before:
            shown = ", ".join(
                f"{k}={v:,}" for k, v in
                sorted(self.target_values_before.items(), key=lambda x: -x[1])[:6]
            )
            print(f"    raw values         : {shown}")
        if self.target_rows_dropped:
            print(f"    rows dropped (no verdict): {self.target_rows_dropped:,}")

        if self.coerced_to_numeric:
            print(f"\n  Coerced to numeric   : {', '.join(self.coerced_to_numeric)}")

        if self.value_merges:
            print(f"\n  Value variants merged:")
            for col, groups in list(self.value_merges.items())[:8]:
                for canon, variants in list(groups.items())[:4]:
                    print(f"    {col}: {' / '.join(variants)} -> {canon}")

        if self.numeric_filled or self.categorical_filled:
            print(f"\n  Missing values filled:")
            for col, n in sorted(self.numeric_filled.items(), key=lambda x: -x[1])[:8]:
                print(f"    {col:28s} {n:>7,}  (median)")
            for col, n in sorted(self.categorical_filled.items(), key=lambda x: -x[1])[:8]:
                print(f"    {col:28s} {n:>7,}  ('{MISSING_LABEL}')")

        if self.cardinality_capped:
            print(f"\n  Cardinality capped:")
            for col, (before, after) in self.cardinality_capped.items():
                print(f"    {col:28s} {before:,} -> {after:,} levels")

        if self.columns_dropped:
            print(f"\n  Columns dropped:")
            for col, why in self.columns_dropped:
                print(f"    {col:28s} {why}")

        if self.warnings:
            print(f"\n  Warnings ({len(self.warnings)}):")
            for w in self.warnings[:10]:
                print(f"    ! {w}")

        print(line)


# =========================================================================
# Readers -- get any shape of input into a DataFrame
# =========================================================================

_KV_RE = re.compile(r"^\s*([A-Za-z_][\w .\-/]{0,60}?)\s*[:=]\s*(.*?)\s*$")
_JSON_OBJ_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def _read_text(source: str) -> str:
    """Accept a path or a raw string."""
    try:
        p = Path(source)
        if len(source) < 4096 and p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pass
    return source


def _try_json_array(text: str) -> Optional[List[Dict]]:
    stripped = text.lstrip()
    if not stripped.startswith("["):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list) and data and all(isinstance(d, dict) for d in data):
        return data
    return None


def _try_jsonl(text: str) -> Optional[List[Dict]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    objs, tried = [], 0
    for ln in lines:
        if not ln.startswith("{"):
            continue
        tried += 1
        try:
            d = json.loads(ln)
            if isinstance(d, dict):
                objs.append(d)
        except json.JSONDecodeError:
            pass
    # Require JSON objects to dominate, so a CSV with one stray brace does not
    # get misread as JSONL.
    if objs and len(objs) >= max(1, int(0.5 * len(lines))):
        return objs
    return None


def _flatten(d: Dict, prefix: str = "") -> Dict[str, Any]:
    """Flatten one level of nesting: {'config': {'a': 1}} -> {'a': 1}."""
    out: Dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, prefix=""))
        elif isinstance(v, (list, tuple)):
            out[key] = " | ".join(str(x) for x in v)
        else:
            out[key] = v
    return out


def _find_banner(lines: List[str]) -> Optional[Tuple[re.Pattern, str]]:
    """Find a repeating record-separator line, e.g. 'RUN :: <id>'.

    A banner is a line shape that recurs many times with a varying tail.  This
    is what lets one parser handle UVM-style blocks, '=== TEST n ===' headers,
    and anything else with a repeating delimiter, instead of hard-coding each.
    """
    shape_counts: Dict[str, int] = {}
    for ln in lines:
        s = ln.strip()
        if not s or len(s) > 200:
            continue
        # Replace digits/hex-ish ids with a placeholder to get the line "shape".
        shape = re.sub(r"[0-9]+", "#", s)
        shape = re.sub(r"\b[0-9a-fA-F]{6,}\b", "#", shape)
        shape_counts[shape] = shape_counts.get(shape, 0) + 1

    if not shape_counts:
        return None
    shape, count = max(shape_counts.items(), key=lambda kv: kv[1])
    # Needs to recur, and must not be a pure separator like '======'.
    if count < 2 or not re.search(r"[A-Za-z]", shape):
        return None
    if len(set(shape.replace(" ", ""))) <= 2:
        return None
    prefix = shape.split("#")[0].strip()
    if len(prefix) < 3:
        return None
    # Digit-masking makes the prefix absorb any literal id stem ('... :: RUN-'),
    # so hand that stem back to the caller: an id of 'RUN-0007' traces to the
    # source log, whereas a bare '0007' is just a row counter.
    stem = re.search(r"([A-Za-z_\-]*)$", prefix).group(1)
    return re.compile(r"^\s*" + re.escape(prefix) + r"\s*(.*)$"), stem


def _parse_blocks(text: str) -> Optional[List[Dict]]:
    """Tolerant block parser.

    Splits on a detected banner, then harvests *whatever it finds* inside each
    block -- embedded JSON objects, key:value lines, and a verdict word.  One
    tolerant pass beats four rigid format-specific parsers.
    """
    lines = text.splitlines()
    found = _find_banner(lines)
    if found is None:
        return None
    banner, stem = found

    records: List[Dict] = []
    current: Optional[Dict] = None
    buf: List[str] = []

    def flush() -> None:
        if current is None:
            return
        body = "\n".join(buf)
        rec = dict(current)
        # (a) embedded JSON objects
        for m in _JSON_OBJ_RE.finditer(body):
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict):
                    rec.update(_flatten(obj))
            except json.JSONDecodeError:
                pass
        # (b) key: value lines
        for ln in body.splitlines():
            if ln.strip().startswith("{") or ln.strip().startswith("}"):
                continue
            m = _KV_RE.match(ln)
            if m:
                k, v = m.group(1).strip(), m.group(2).strip()
                if k and v and k not in rec:
                    rec[k] = v
        # (c) verdict word anywhere in the block
        if not any(_looks_like_verdict_key(k) for k in rec):
            verdict = _scan_verdict(body)
            if verdict:
                rec["verdict"] = verdict
        if len(rec) > 1:
            records.append(rec)

    for ln in lines:
        m = banner.match(ln)
        if m:
            flush()
            rid = m.group(1).strip() if m.lastindex else ""
            # Named 'row_id' so preprocess._is_identifier always excludes it from
            # the feature matrix -- otherwise a numeric-looking id is treated as
            # a predictor and leaks row order into the model.
            current = {"row_id": f"{stem}{rid}" or f"rec_{len(records) + 1}"}
            buf = []
        elif current is not None:
            buf.append(ln)

    flush()
    return records or None


def _looks_like_verdict_key(k: str) -> bool:
    kl = str(k).lower()
    return any(w in kl for w in
               ("verdict", "pass_fail", "passfail", "result", "status", "outcome"))


def _scan_verdict(body: str) -> Optional[str]:
    """Find a standalone PASS/FAIL-ish word in free text."""
    for m in re.finditer(r"\b([A-Za-z]{2,12})\b", body):
        w = m.group(1).lower()
        if w in _FAIL_WORDS and w not in ("no", "n", "0", "false"):
            return w
    for m in re.finditer(r"\b([A-Za-z]{2,12})\b", body):
        w = m.group(1).lower()
        if w in _PASS_WORDS and w not in ("yes", "y", "1", "true", "done"):
            return w
    return None


def _parse_kv_records(text: str) -> Optional[List[Dict]]:
    """Key:value lines, records separated by blank lines or a repeating key."""
    lines = text.splitlines()
    kv_hits = sum(1 for ln in lines if ln.strip() and _KV_RE.match(ln))
    non_blank = sum(1 for ln in lines if ln.strip())
    if not non_blank or kv_hits < 0.5 * non_blank:
        return None

    records: List[Dict] = []
    cur: Dict[str, Any] = {}

    def flush() -> None:
        nonlocal cur
        if cur:
            records.append(cur)
            cur = {}

    for ln in lines:
        if not ln.strip():
            flush()
            continue
        m = _KV_RE.match(ln)
        if not m:
            continue
        k, v = m.group(1).strip(), m.group(2).strip()
        if k in cur:          # repeating key => new record
            flush()
        cur[k] = v
    flush()
    return records or None


def _read_delimited(text: str) -> Optional[pd.DataFrame]:
    """CSV/TSV/pipe-delimited, delimiter sniffed by the python engine."""
    from io import StringIO
    try:
        df = pd.read_csv(StringIO(text), sep=None, engine="python")
    except Exception:
        try:
            df = pd.read_csv(StringIO(text))
        except Exception:
            return None
    if df.shape[1] < 2:
        return None
    return df


def read_any(source: str, report: Optional[IngestReport] = None) -> pd.DataFrame:
    """Read logs of unknown shape into a DataFrame.

    Tries, in order: JSON array, JSONL, banner-delimited blocks, key:value
    records, delimited text.
    """
    rep = report or IngestReport()
    text = _read_text(source)
    if not text.strip():
        raise ValueError("Input is empty.")

    for name, fn in (
        ("json_array", _try_json_array),
        ("jsonl", _try_jsonl),
        ("blocks", _parse_blocks),
        ("key_value", _parse_kv_records),
    ):
        recs = fn(text)
        if recs:
            rep.source_format = name
            rep.records_parsed = len(recs)
            return pd.DataFrame([_flatten(r) for r in recs])

    df = _read_delimited(text)
    if df is not None:
        rep.source_format = "delimited"
        rep.records_parsed = len(df)
        return df

    raise ValueError(
        "Could not parse input as JSON, JSONL, block, key:value, or delimited "
        "text. Pass a DataFrame directly, or convert to CSV first."
    )


# =========================================================================
# Normalisation
# =========================================================================

def _norm_token(v: Any) -> str:
    """Casefold + collapse separators, so SMALL / Small / small_ / 'small '
    all land on the same token."""
    s = str(v).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _is_nullish(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and np.isnan(v):
        return True
    return str(v).strip().lower() in _NULLISH


def _blank_nullish(df: pd.DataFrame) -> pd.DataFrame:
    """Turn 'NA', 'null', '-', '' etc. into real NaN so one code path handles
    every flavour of missing."""
    for col in df.columns:
        if _is_text_dtype(df[col]):
            df[col] = df[col].map(lambda v: np.nan if _is_nullish(v) else v)
    return df


def _coerce_numeric(df: pd.DataFrame, report: IngestReport,
                    threshold: float = 0.95) -> pd.DataFrame:
    """Text readers make everything a string.  Promote columns back to numeric
    when nearly all non-null values parse as numbers."""
    for col in df.columns:
        if not _is_text_dtype(df[col]):
            continue
        nn = df[col].dropna()
        if nn.empty:
            continue
        conv = pd.to_numeric(nn, errors="coerce")
        if conv.notna().mean() >= threshold:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            report.coerced_to_numeric.append(col)
    return df


def detect_target(df: pd.DataFrame, explicit: Optional[str] = None
                  ) -> Optional[str]:
    """Find the verdict column.

    Prefers a name that reads like a verdict; otherwise takes any column whose
    values are drawn from the pass/fail vocabulary.
    """
    if explicit:
        if explicit not in df.columns:
            raise KeyError(f"target column '{explicit}' not in data: "
                           f"{list(df.columns)[:15]}")
        return explicit

    def vocab_score(col: str) -> float:
        vals = df[col].dropna()
        if vals.empty:
            return 0.0
        toks = vals.map(_norm_token)
        known = toks.isin(_PASS_WORDS | _FAIL_WORDS)
        # Needs both classes present to be a usable target.
        has_pass = toks.isin(_PASS_WORDS).any()
        has_fail = toks.isin(_FAIL_WORDS).any()
        return float(known.mean()) if (has_pass and has_fail) else 0.0

    scored = [(c, vocab_score(c)) for c in df.columns]
    named = [(c, s) for c, s in scored if s >= 0.9 and _looks_like_verdict_key(c)]
    if named:
        return max(named, key=lambda x: x[1])[0]
    any_col = [(c, s) for c, s in scored if s >= 0.9]
    if any_col:
        return max(any_col, key=lambda x: x[1])[0]
    return None


def normalize_target(df: pd.DataFrame, target: str,
                     report: IngestReport) -> pd.DataFrame:
    """Map the verdict vocabulary onto the literal 'pass'/'fail' that
    `preprocess.encode_target` expects, and drop unlabelled rows."""
    raw_counts = df[target].astype(str).value_counts().to_dict()
    report.target_values_before = {str(k): int(v) for k, v in raw_counts.items()}

    def to_verdict(v: Any) -> Optional[str]:
        if _is_nullish(v):
            return None
        t = _norm_token(v)
        if t in _FAIL_WORDS:
            return "fail"
        if t in _PASS_WORDS:
            return "pass"
        return None

    mapped = df[target].map(to_verdict)
    unmapped = mapped.isna() & df[target].notna()
    if unmapped.any():
        bad = sorted(set(df.loc[unmapped, target].astype(str)))[:8]
        report.warnings.append(
            f"target '{target}': {int(unmapped.sum()):,} rows with unrecognised "
            f"verdicts dropped ({', '.join(bad)}). Pass --target-pass/--target-fail "
            f"to map them."
        )

    before = len(df)
    df = df.loc[mapped.notna()].copy()
    df[target] = mapped.loc[mapped.notna()].values
    report.target_rows_dropped = before - len(df)
    report.target_column = target
    return df


def canonicalize_values(df: pd.DataFrame, target: str,
                        report: IngestReport) -> pd.DataFrame:
    """Merge spelling variants of the same categorical value.

    Only case/whitespace/separator variants are merged -- that is provably the
    same token.  Genuine abbreviations (S -> small, 256 -> small) need domain
    knowledge and are left alone; use `value_overrides` for those.
    """
    for col in df.columns:
        if col == target or not _is_text_dtype(df[col]):
            continue
        if _ID_PATTERNS.match(str(col).lower()):
            continue                       # join keys keep their exact spelling
        vals = df[col].dropna()
        if vals.empty:
            continue

        groups: Dict[str, List[str]] = {}
        for v in vals.unique():
            groups.setdefault(_norm_token(v), []).append(str(v))

        merged = {c: vs for c, vs in groups.items() if len(vs) > 1}
        if merged:
            report.value_merges[col] = merged

        df[col] = df[col].map(lambda v: _norm_token(v) if pd.notna(v) else v)
    return df


def apply_overrides(df: pd.DataFrame,
                    column_overrides: Optional[Dict[str, str]],
                    value_overrides: Optional[Dict[str, Dict[str, str]]],
                    report: IngestReport) -> pd.DataFrame:
    """Optional user-supplied renames and value maps, applied after
    auto-normalisation so overrides are written against tidy tokens."""
    if column_overrides:
        present = {k: v for k, v in column_overrides.items() if k in df.columns}
        missing = set(column_overrides) - set(present)
        if missing:
            report.warnings.append(
                f"column_overrides referenced absent columns: {sorted(missing)}")
        df = df.rename(columns=present)

    if value_overrides:
        for col, mapping in value_overrides.items():
            if col not in df.columns:
                report.warnings.append(
                    f"value_overrides referenced absent column '{col}'")
                continue
            norm_map = {_norm_token(k): v for k, v in mapping.items()}
            df[col] = df[col].map(
                lambda v: norm_map.get(_norm_token(v), v) if pd.notna(v) else v)
    return df


def cap_cardinality(df: pd.DataFrame, target: str, report: IngestReport,
                    max_levels: int = 40,
                    drop_ratio: float = 0.9) -> pd.DataFrame:
    """Keep one-hot encoding bounded.

    Division of labour with `preprocess.py`: it already excludes identifiers
    from the feature matrix, but only above 95% uniqueness, so a column sitting
    at 60-90% unique slips through and explodes into hundreds of dummies.  That
    middle band is what gets handled here.

      * ID-named columns  -- left untouched, so predictions can still be joined
                             back; preprocess drops them from features anyway.
      * near-unique       -- dropped as junk (a per-row value teaches nothing).
      * merely wide       -- top levels kept, tail bucketed into `__other__`,
                             which preserves signal instead of losing the column.
    """
    n = len(df)
    if n == 0:
        return df

    for col in list(df.columns):
        if col == target or not _is_text_dtype(df[col]):
            continue
        if _ID_PATTERNS.match(str(col).lower()):
            continue
        nun = df[col].nunique(dropna=True)
        if nun <= 1:
            df = df.drop(columns=[col])
            report.columns_dropped.append((col, "constant - no signal"))
            continue
        if nun / n > drop_ratio:
            df = df.drop(columns=[col])
            report.columns_dropped.append(
                (col, f"near-unique ({nun:,}/{n:,} distinct) - no signal"))
            continue
        if nun > max_levels:
            keep = set(df[col].value_counts().nlargest(max_levels - 1).index)
            df[col] = df[col].map(lambda v: v if v in keep or pd.isna(v)
                                  else OTHER_LABEL)
            report.cardinality_capped[col] = (int(nun), int(df[col].nunique()))
    return df


def handle_missing(df: pd.DataFrame, target: str,
                   report: IngestReport,
                   max_missing_ratio: float = 0.6) -> pd.DataFrame:
    """Make the frame sklearn-safe.

    This is the fix that actually unblocks the pipeline: `preprocess.py` passes
    numeric predictors through untouched, so a single NaN makes
    RandomForestClassifier.fit raise. Numerics get the median; categoricals get
    an explicit missing level, because absence is often itself predictive.
    """
    n = len(df)
    if n == 0:
        return df

    for col in list(df.columns):
        if col == target:
            continue
        miss = int(df[col].isna().sum())
        if miss == 0:
            continue
        if miss / n > max_missing_ratio:
            df = df.drop(columns=[col])
            report.columns_dropped.append(
                (col, f"{miss / n:.0%} missing (> {max_missing_ratio:.0%})"))
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            med = df[col].median()
            if pd.isna(med):
                df = df.drop(columns=[col])
                report.columns_dropped.append((col, "all values missing"))
                continue
            df[col] = df[col].fillna(med)
            report.numeric_filled[col] = miss
        else:
            df[col] = df[col].fillna(MISSING_LABEL)
            report.categorical_filled[col] = miss

    return df


# =========================================================================
# Orchestration
# =========================================================================

def ingest(
    source: Any,
    target: Optional[str] = None,
    column_overrides: Optional[Dict[str, str]] = None,
    value_overrides: Optional[Dict[str, Dict[str, str]]] = None,
    max_levels: int = 40,
    max_missing_ratio: float = 0.6,
) -> Tuple[pd.DataFrame, IngestReport]:
    """Read heterogeneous logs and return a frame `preprocess.py` can consume.

    Parameters
    ----------
    source            path, raw log text, or a DataFrame
    target            verdict column name; auto-detected when omitted
    column_overrides  {old_name: new_name}, applied after auto-normalisation
    value_overrides   {column: {raw_value: canonical}} for domain abbreviations
    max_levels        cap on distinct levels per categorical column
    max_missing_ratio drop a column above this fraction of missing values
    """
    report = IngestReport()

    if isinstance(source, pd.DataFrame):
        df = source.copy()
        report.source_format = "dataframe"
        report.records_parsed = len(df)
    else:
        df = read_any(source, report)

    if df.empty:
        raise ValueError("Parsed zero records from input.")

    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    df = _blank_nullish(df)
    df = _coerce_numeric(df, report)

    tgt = detect_target(df, target)
    if tgt is None:
        raise ValueError(
            "Could not identify a verdict column. Every column either lacked "
            "pass/fail-style values or had only one class present. "
            f"Columns seen: {list(df.columns)[:20]}. "
            "Pass target='<column>' to name it explicitly."
        )

    df = normalize_target(df, tgt, report)
    if df.empty:
        raise ValueError(f"No rows left after dropping unlabelled verdicts in '{tgt}'.")

    df = canonicalize_values(df, tgt, report)
    df = apply_overrides(df, column_overrides, value_overrides, report)
    tgt = (column_overrides or {}).get(tgt, tgt)
    report.target_column = tgt

    df = cap_cardinality(df, tgt, report, max_levels=max_levels)
    df = handle_missing(df, tgt, report, max_missing_ratio=max_missing_ratio)

    counts = df[tgt].value_counts()
    if len(counts) < 2:
        raise ValueError(
            f"Target '{tgt}' has a single class after cleaning ({counts.to_dict()}). "
            "Both passing and failing runs are needed to train.")
    minority = int(counts.min())
    if minority < 20:
        report.warnings.append(
            f"only {minority} rows in the minority class - metrics will be noisy "
            f"and the train/test split may be unstable")

    predictors = [c for c in df.columns if c != tgt]
    if not predictors:
        raise ValueError("No predictor columns survived cleaning.")

    report.rows_final = len(df)
    return df.reset_index(drop=True), report


# =========================================================================
# CLI
# =========================================================================

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Normalise heterogeneous test logs into a CSV that "
                    "preprocess.py / train_baseline.py can consume.")
    ap.add_argument("--input", required=True,
                    help="Log file in any supported shape")
    ap.add_argument("--output", default="ingested_runs.csv",
                    help="Output CSV (default: ingested_runs.csv)")
    ap.add_argument("--target", default=None,
                    help="Verdict column name (default: auto-detect)")
    ap.add_argument("--overrides", default=None,
                    help="JSON file with 'columns' and/or 'values' override maps")
    ap.add_argument("--max-levels", type=int, default=40,
                    help="Max distinct levels per categorical column (default: 40)")
    ap.add_argument("--max-missing", type=float, default=0.6,
                    help="Drop columns above this missing fraction (default: 0.6)")
    args = ap.parse_args()

    col_ov = val_ov = None
    if args.overrides:
        with open(args.overrides) as fh:
            ov = json.load(fh)
        col_ov = ov.get("columns")
        val_ov = ov.get("values")

    try:
        df, report = ingest(
            args.input,
            target=args.target,
            column_overrides=col_ov,
            value_overrides=val_ov,
            max_levels=args.max_levels,
            max_missing_ratio=args.max_missing,
        )
    except ValueError as exc:
        print(f"\nIngest failed: {exc}\n", file=sys.stderr)
        sys.exit(1)

    report.print_summary()
    df.to_csv(args.output, index=False)
    print(f"\n  -> {args.output}  ({len(df):,} rows x {df.shape[1]} cols)")
    print(f"\n  Next: python train_baseline.py --input {args.output}\n")


if __name__ == "__main__":
    main()
