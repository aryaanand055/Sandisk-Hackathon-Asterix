"""FastAPI service wrapping the uvm_intel analysis pipeline.

Uploaded .log files are parsed by uvm_intel.log_parser and analysed by
uvm_intel.pipeline. Analysis runs on a worker thread; the UI polls /api/jobs.
"""

import glob
import os
import shutil
import tempfile
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from uvm_intel.ingest_multi import parse_files_multi
from uvm_intel.log_parser import parse_files
from uvm_intel.pipeline import run_analysis

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
    "error_trace",
}

jobs: Dict[str, Dict[str, Any]] = {}


def sample_files() -> List[str]:
    return sorted(glob.glob(os.path.join(SAMPLE_DIR, "*.log")))


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
            raise ValueError(
                "No valid runs parsed. Ensure input log or CSV files contain verification data."
            )

        job.update(progress=8, message=f"Parsed {len(runs):,} runs from {multi_meta['file_count']} file(s)")

        def progress(message: str, pct: int) -> None:
            job.update(progress=max(8, int(pct)), message=message)

        analysis = run_analysis(
            runs, errors, stats.as_dict(),
            max_risk=params["max_risk"],
            n_trials=params["n_trials"],
            dbscan_eps=params["dbscan_eps"],
            enable_recommender=params["enable_recommender"],
            progress=progress,
        )

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
                "elapsed": analysis.get("total_seconds"),
                "error": None,
                "n_runs": int(len(runs)),
            },
            "analysis": analysis,
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
            "kind": "outcome" if col in OUTCOME_COLUMNS else "config",
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
    if not job_id:
        raise HTTPException(status_code=400, detail="Missing job_id parameter")
    
    job = _require_done(job_id)
    analysis = job["result"]["analysis"]
    summary = analysis.get("summary", {})
    risk_model = analysis.get("risk_model", {})
    recommendations = analysis.get("recommendations", {})
    fingerprints = analysis.get("fingerprints", {})
    
    q_lower = question.lower()
    
    # Synthesize intelligent answer based on analysis payload
    n_runs = summary.get("n_runs", 0)
    fail_rate = summary.get("fail_rate", 0) * 100
    top_features = [f["feature"] for f in risk_model.get("shap_importance", [])[:3]]
    rec_config = recommendations.get("recommendation", {}).get("config", {}) if isinstance(recommendations, dict) else {}
    n_clusters = fingerprints.get("n_clusters", 0)
    
    response = []
    response.append(f"**Analysis Insights for Job `{job_id}`** (Corpus: {n_runs:,} runs, Failure Rate: {fail_rate:.2f}%)")
    
    if "risk" in q_lower or "fail" in q_lower or "error" in q_lower:
        response.append(f"• **Top Risk Drivers**: The most critical configuration parameters influencing failures are `{', '.join(top_features) if top_features else 'N/A'}`.")
        if n_clusters > 0:
            response.append(f"• **Failure Fingerprints**: Identified **{n_clusters}** distinct failure clusters across the test suite.")
    
    if "recommend" in q_lower or "optimal" in q_lower or "setting" in q_lower or "knob" in q_lower or "config" in q_lower:
        if rec_config:
            rec_str = ", ".join([f"`{k}={v}`" for k, v in list(rec_config.items())[:5]])
            response.append(f"• **Recommended Optimal Config**: {rec_str}")
        else:
            response.append("• **Recommendations**: Default baseline configuration remains safe within risk bounds.")
            
    if "summary" in q_lower or "overview" in q_lower or not response:
        response.append(f"• **Corpus Overview**: Tested {n_runs:,} runs across {summary.get('n_pass', 0):,} passes and {summary.get('n_fail', 0):,} failures.")
        if top_features:
            response.append(f"• **Key Driver**: `{top_features[0]}` contributes highest variance to failure risk.")
            
    answer_text = "\n\n".join(response)
    
    return {
        "job_id": job_id,
        "question": question,
        "answer": answer_text,
        "top_features": top_features,
        "fail_rate": fail_rate,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
