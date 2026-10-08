"""FastAPI service wrapping the uvm_intel analysis pipeline.

Uploaded .log files are parsed by uvm_intel.log_parser and analysed by
uvm_intel.pipeline. Analysis runs on a worker thread; the UI polls /api/jobs.
"""

import glob
import json
import os
import shutil
import tempfile
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv()

from uvm_intel import generate_logs
from uvm_intel.copilot import query_gemini_copilot
from uvm_intel.ingest_multi import parse_files_multi
from uvm_intel.log_parser import parse_files
from uvm_intel.pipeline import run_analysis
from uvm_intel.sim_log_parser import METRIC_PREFIX

app = FastAPI(title="UVM Configuration Intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DIR = os.path.join(REPO_ROOT, "data", "uvm_logs")
GENERATED_DIR = os.path.join(REPO_ROOT, "data", "generated")
MAX_UPLOAD_BYTES = 512 * 1024 * 1024

# Columns surfaced in the Run Explorer table, in display order.
RUN_COLUMNS = [
    "run_id", "test_name", "pass_fail", "primary_error_tag",
    "execution_time_ms", "throughput_mbps", "cache_policy",
    "queue_depth", "test_mode_enabled", "clock_freq_mhz", "seed",
]

# Columns that describe what happened rather than how the run was configured.
# Split out in /diff so a config difference isn't confused with an outcome.
OUTCOME_COLUMNS = {
    "run_id", "seed", "execution_time_ms", "throughput_mbps", "cycles",
    "uvm_error_count", "uvm_fatal_count", "verdict", "pass_fail",
    "uvm_error_total", "uvm_fatal_total", "uvm_warning_total",
    "primary_error_tag", "distinct_error_tags", "trace_fingerprint",
    "error_trace", "sim_time_ns",
}

jobs: Dict[str, Dict[str, Any]] = {}


def sample_files() -> List[str]:
    return sorted(glob.glob(os.path.join(SAMPLE_DIR, "*.log")))


def _clean_obj(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        if np.isnan(val) or np.isinf(val):
            return None
        return val
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [_clean_obj(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): _clean_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_obj(x) for x in obj]
    if hasattr(obj, "item"):
        try:
            return _clean_obj(obj.item())
        except Exception:
            return str(obj)
    return obj


def _py(v: Any) -> Any:
    """Coerce numpy/pandas scalars to JSON-serialisable Python natives.

    DataFrame cells come back as numpy types, which FastAPI's encoder rejects.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "item"):  # numpy scalar
        try:
            return v.item()
        except (ValueError, AttributeError):
            return str(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _run_job(job_id: str, paths: List[str], params: Dict[str, Any],
             tmpdir: Optional[str]) -> None:
    job = jobs[job_id]
    try:
        job.update(status="running", progress=2, message="Parsing input files")

        runs, errors, stats, multi_meta = parse_files_multi(paths)
        if runs.empty:
            wf_avail = multi_meta.get("data_sources", {}).get("waveforms", False)
            if wf_avail and multi_meta.get("mode") != "multi" and not multi_meta.get("data_sources", {}).get("uvm_log", False):
                raise ValueError(
                    "Only waveform companion files (.fsdb, .vcd, .wlf) were uploaded. "
                    "Waveforms provide internal signal inspection and must be uploaded together with a .log or .csv verification file."
                )
            raise ValueError(
                "No valid runs parsed. Ensure input log or CSV files contain verification data."
            )

        job.update(progress=8, message=f"Parsed {len(runs):,} runs from {multi_meta['file_count']} file(s)")

        def progress(message: str, pct: int) -> None:
            job.update(progress=max(8, int(pct)), message=message)

        stats_dict = stats.as_dict() if hasattr(stats, "as_dict") else stats
        analysis = run_analysis(
            runs, errors, stats_dict,
            max_risk=params["max_risk"],
            n_trials=params["n_trials"],
            dbscan_eps=params["dbscan_eps"],
            enable_recommender=params["enable_recommender"],
            progress=progress,
        )

        clean_analysis = _clean_obj(analysis)
        job["runs_df"] = runs
        job["result"] = {
            "meta": {
                "job_id": job_id,
                "status": "done",
                "progress": 100,
                "message": "Complete",
                "files": job.get("files", []),
                "params": params,
                "created": job["created"],
                "elapsed": clean_analysis.get("total_seconds"),
                "error": None,
                "n_runs": int(len(runs)),
            },
            "analysis": clean_analysis,
        }
        job.update(status="completed", progress=100, message="Complete")

    except Exception as exc:  # surfaced to the UI rather than lost on a thread
        job.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _create_job(files: List[str], display_names: List[str],
                params: Dict[str, Any], tmpdir: Optional[str]) -> str:
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "files": display_names,
        "created": datetime.now().timestamp(),
        "error": None,
    }
    t = threading.Thread(target=_run_job, args=(job_id, files, params, tmpdir),
                         daemon=True)
    t.start()
    return job_id


def _params(max_risk: float, n_trials: int, dbscan_eps: float,
            enable_recommender: bool) -> Dict[str, Any]:
    return {
        "max_risk": max_risk,
        "n_trials": n_trials,
        "dbscan_eps": dbscan_eps,
        "enable_recommender": enable_recommender,
    }


def _require_done(job_id: str) -> Dict[str, Any]:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error"))
    if "result" not in job:
        raise HTTPException(status_code=202, detail="Job not yet complete")
    return job


@app.get("/api/health")
async def health():
    files = sample_files()
    return {
        "status": "ok",
        "bundled_sample_available": bool(files),
        "bundled_sample_files": len(files),
        "sample_dir": SAMPLE_DIR,
    }


@app.post("/api/analyze")
async def analyze(
    files: List[UploadFile] = File(...),
    max_risk: float = 0.02,
    n_trials: int = 150,
    dbscan_eps: float = 0.35,
    enable_recommender: bool = True,
):
    tmpdir = tempfile.mkdtemp(prefix="uvm_upload_")
    paths, names, total = [], [], 0
    try:
        for f in files:
            dest = os.path.join(tmpdir, os.path.basename(f.filename or "upload.log"))
            with open(dest, "wb") as out:
                while chunk := await f.read(1 << 20):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413,
                                            detail="Upload exceeds 512 MB cap")
                    out.write(chunk)
            paths.append(dest)
            names.append(os.path.basename(dest))
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise

    if not paths:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="No files uploaded")

    params = _params(max_risk, n_trials, dbscan_eps, enable_recommender)
    return {"job_id": _create_job(paths, names, params, tmpdir)}


@app.post("/api/analyze-sample")
async def analyze_sample(
    max_risk: float = 0.02,
    n_trials: int = 150,
    dbscan_eps: float = 0.35,
    enable_recommender: bool = True,
):
    paths = sample_files()
    if not paths:
        raise HTTPException(
            status_code=404,
            detail=("No bundled corpus. Generate one with: "
                    "python -m uvm_intel.generate_logs --n-runs 50000 --parts 10"),
        )
    params = _params(max_risk, n_trials, dbscan_eps, enable_recommender)
    names = [os.path.basename(p) for p in paths]
    return {"job_id": _create_job(paths, names, params, None)}


# ── Log generator ──────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    n_runs: int = Field(20000, ge=500, le=200000)
    seed: int = 42
    parts: int = Field(4, ge=1, le=50)
    extra_deterministic: bool = False
    build_fields: bool = False
    seeds_per_config: int = Field(1, ge=1, le=50)
    base_fail_prob: float = Field(generate_logs.BASE_FAIL_PROB, ge=0.0, le=0.5)
    rule_strength: float = Field(1.0, ge=0.0, le=3.0)


def _corpus_dir(corpus_id: str) -> str:
    path = os.path.join(GENERATED_DIR, corpus_id)
    if not corpus_id.isalnum() or not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Unknown corpus")
    return path


@app.get("/api/generator/defaults")
async def generator_defaults():
    """Default options plus every rule each switch would add, for the UI."""
    return {
        "options": GenerateRequest().model_dump(),
        "rules": {
            "base": generate_logs.RULES,
            "extra_deterministic": generate_logs.EXTRA_DETERMINISTIC_RULES,
            "build_fields": generate_logs.BUILD_RULES,
        },
    }


@app.post("/api/generate")
def generate_corpus(req: GenerateRequest):
    """Write a synthetic corpus to data/generated/<id>/ and return its
    ground truth. Runs synchronously: 200k runs takes well under a minute."""
    corpus_id = uuid.uuid4().hex[:12]
    out_dir = os.path.join(GENERATED_DIR, corpus_id)
    gt = generate_logs.generate(
        req.n_runs, req.seed, out_dir, req.parts,
        extra_deterministic=req.extra_deterministic,
        build_fields=req.build_fields,
        seeds_per_config=req.seeds_per_config,
        base_fail_prob=req.base_fail_prob,
        rule_strength=req.rule_strength,
    )
    for f in gt["files"]:
        f["path"] = os.path.basename(f["path"])
    with open(os.path.join(out_dir, "ground_truth.json"), "w") as fh:
        json.dump(gt, fh, indent=2)
    return {"corpus_id": corpus_id, **gt}


@app.get("/api/generate/{corpus_id}/download")
def download_corpus(corpus_id: str):
    path = _corpus_dir(corpus_id)
    archive = shutil.make_archive(path, "zip", path)
    return FileResponse(archive, filename=f"uvm_corpus_{corpus_id}.zip",
                        media_type="application/zip")


@app.post("/api/generate/{corpus_id}/analyze")
async def analyze_corpus(
    corpus_id: str,
    max_risk: float = 0.02,
    n_trials: int = 150,
    dbscan_eps: float = 0.35,
    enable_recommender: bool = True,
):
    paths = sorted(glob.glob(os.path.join(_corpus_dir(corpus_id), "*.log")))
    params = _params(max_risk, n_trials, dbscan_eps, enable_recommender)
    names = [os.path.basename(p) for p in paths]
    return {"job_id": _create_job(paths, names, params, None)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return {
        "status": job["status"],
        "progress": job.get("progress", 0),
        "message": job.get("message", ""),
        "error": job.get("error"),
    }


@app.get("/api/jobs/{job_id}/result")
async def get_result(job_id: str):
    return _require_done(job_id)["result"]


@app.get("/api/jobs/{job_id}/runs")
async def get_runs(job_id: str, page: int = 0, per_page: int = 50,
                   search: str = "", status: str = "all",
                   sort: str = "", desc: bool = False):
    job = _require_done(job_id)
    df: pd.DataFrame = job["runs_df"]

    base_cols = [c for c in RUN_COLUMNS if c in df.columns]
    extra_cols = [c for c in df.columns if c not in RUN_COLUMNS and c not in ("error_trace",)]
    cols = base_cols + extra_cols
    view = df[cols]

    if status in ("pass", "fail"):
        view = view[view["pass_fail"] == status]
    if search:
        needle = search.lower()
        mask = (view["run_id"].astype(str).str.lower().str.contains(needle, regex=False)
                | view["test_name"].astype(str).str.lower().str.contains(needle, regex=False))
        view = view[mask]
    if sort and sort in view.columns:
        view = view.sort_values(sort, ascending=not desc, kind="stable")

    per_page = max(1, min(per_page, 200))
    total = int(len(view))
    start = max(0, page) * per_page
    page_df = view.iloc[start:start + per_page]

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "n_pages": max(1, (total + per_page - 1) // per_page),
        "columns": cols,
        "runs": [{k: _py(v) for k, v in rec.items()}
                 for rec in page_df.to_dict("records")],
    }


@app.get("/api/jobs/{job_id}/diff")
async def get_diff(job_id: str, run_a: str, run_b: str):
    job = _require_done(job_id)
    df: pd.DataFrame = job["runs_df"]

    rows = df[df["run_id"].isin([run_a, run_b])]
    got = set(rows["run_id"])
    missing = [r for r in (run_a, run_b) if r not in got]
    if missing:
        raise HTTPException(status_code=404,
                            detail=f"Unknown run_id(s): {', '.join(missing)}")

    a = rows[rows["run_id"] == run_a].iloc[0]
    b = rows[rows["run_id"] == run_b].iloc[0]

    fields = []
    for col in df.columns:
        if col == "error_trace":
            continue
        va, vb = a[col], b[col]
        fields.append({
            "field": col,
            "kind": ("outcome" if col in OUTCOME_COLUMNS
                     or col.startswith(METRIC_PREFIX) else "config"),
            "run_a": _py(va),
            "run_b": _py(vb),
            "changed": bool(str(va) != str(vb)),
        })

    changed = [f for f in fields if f["changed"]]
    return {
        "run_a": run_a,
        "run_b": run_b,
        "n_changed": len(changed),
        "n_config_changed": sum(1 for f in changed if f["kind"] == "config"),
        "n_outcome_changed": sum(1 for f in changed if f["kind"] == "outcome"),
        "fields": fields,
        "trace_a": str(a.get("error_trace", "")),
        "trace_b": str(b.get("error_trace", "")),
    }


@app.get("/api/jobs/{job_id}/export")
async def export_job(job_id: str):
    return _require_done(job_id)["result"]


@app.post("/api/jobs/{job_id}/copilot")
@app.post("/api/copilot/query")
async def copilot_query(req: Dict[str, Any]):
    job_id = req.get("job_id")
    question = req.get("question", "").strip()
    api_key = req.get("api_key") or req.get("gemini_api_key")
    
    if not job_id:
        raise HTTPException(status_code=400, detail="Missing job_id parameter")
    if not question:
        raise HTTPException(status_code=400, detail="Missing question parameter")
    
    job = _require_done(job_id)
    analysis = job["result"]["analysis"]
    
    res = query_gemini_copilot(question, analysis, api_key=api_key)
    res["job_id"] = job_id
    res["question"] = question
    res["timestamp"] = datetime.now().isoformat()
    return res


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)
