import uuid
import json
import os
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import threading
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}

def generate_sample_result():
    return {
        "meta": {
            "job_id": "sample_analysis",
            "status": "done",
            "progress": 100,
            "message": "Complete",
            "elapsed": 18.94,
            "n_runs": 50000
        },
        "analysis": {
            "summary": {
                "n_runs": 50000,
                "n_pass": 43648,
                "n_fail": 6352,
                "fail_rate": 0.127,
                "n_error_lines": 13665,
                "error_tag_distribution": {
                    "DATA_MISMATCH": 3085,
                    "FIFO_OVERFLOW": 1183,
                    "TIMEOUT": 925,
                    "RETENTION_FAIL": 672,
                    "ASSERTION_FAIL": 487
                },
                "severity_distribution": {
                    "ERROR": 12740,
                    "FATAL": 925
                },
                "metric_stats": {
                    "execution_time_ms": {
                        "mean": 105.85,
                        "median": 20.58,
                        "p95": 425.99,
                        "min": 1.0,
                        "max": 2000.0
                    },
                    "throughput_mbps": {
                        "mean": 41.17,
                        "median": 16.3,
                        "p95": 165.13,
                        "min": 0.0,
                        "max": 1008.95
                    },
                    "cycles": {
                        "mean": 78492661.93,
                        "median": 15372771.0,
                        "p95": 292384763.9,
                        "min": 400000.0,
                        "max": 2398987283.0
                    }
                }
            },
            "risk_model": {
                "n_train": 40000,
                "n_test": 10000,
                "fail_rate": 0.127,
                "metrics": {
                    "accuracy": 0.94,
                    "precision": 0.89,
                    "recall": 0.85,
                    "f1": 0.87,
                    "roc_auc": 0.92
                },
                "confusion_matrix": {
                    "tp": 8539,
                    "fp": 1461,
                    "tn": 8539,
                    "fn": 1461
                },
                "shap_importance": [
                    {"feature": "test_mode_enabled", "mean_abs_shap": 0.285},
                    {"feature": "cache_policy", "mean_abs_shap": 0.228},
                    {"feature": "queue_depth", "mean_abs_shap": 0.195},
                    {"feature": "clock_freq_mhz", "mean_abs_shap": 0.142},
                    {"feature": "ecc_mode", "mean_abs_shap": 0.089}
                ]
            },
            "fingerprints": {
                "n_clusters": 8,
                "n_templates": 127,
                "clusters": [
                    {
                        "id": "c1",
                        "error_type": "DATA_MISMATCH",
                        "n_runs": 2841,
                        "n_distinct_templates": 1,
                        "determinism": 0.998,
                        "is_rtl_bug": True
                    },
                    {
                        "id": "c2",
                        "error_type": "FIFO_OVERFLOW",
                        "n_runs": 1183,
                        "n_distinct_templates": 12,
                        "determinism": 0.145,
                        "is_rtl_bug": False
                    },
                    {
                        "id": "c3",
                        "error_type": "TIMEOUT",
                        "n_runs": 925,
                        "n_distinct_templates": 8,
                        "determinism": 0.089,
                        "is_rtl_bug": False
                    }
                ]
            },
            "pareto": {
                "n_points": 318,
                "frontier": [
                    {"throughput": 850.2, "predicted_risk": 0.012, "n_configs": 5},
                    {"throughput": 920.5, "predicted_risk": 0.018, "n_configs": 8},
                    {"throughput": 1010.3, "predicted_risk": 0.040, "n_configs": 12}
                ],
                "best_safe": {"throughput": 850.2, "predicted_risk": 0.012},
                "knee": {"throughput": 920.5, "predicted_risk": 0.018},
                "peak": {"throughput": 1010.3, "predicted_risk": 0.040}
            },
            "recommendations": {
                "n_trials": 150,
                "max_risk": 0.02,
                "search_space": {
                    "test_mode_enabled": [0, 1],
                    "cache_policy": ["Disabled", "LRU", "Adaptive"],
                    "queue_depth": [8, 16, 32, 64],
                    "ecc_mode": ["Disabled", "Enabled"]
                },
                "best_configs": [
                    {"throughput": 848.1, "predicted_risk": 0.011, "test_mode_enabled": 0, "cache_policy": "LRU", "queue_depth": 16},
                    {"throughput": 825.3, "predicted_risk": 0.013, "test_mode_enabled": 0, "cache_policy": "LRU", "queue_depth": 8},
                    {"throughput": 810.5, "predicted_risk": 0.009, "test_mode_enabled": 1, "cache_policy": "Adaptive", "queue_depth": 16}
                ]
            },
            "config_diff": {
                "n_twins": 4126,
                "field_deltas": [
                    {"field": "test_mode_enabled", "fail_vs_pass_rate": 0.92, "rank": 1},
                    {"field": "cache_policy", "fail_vs_pass_rate": 0.84, "rank": 2},
                    {"field": "queue_depth", "fail_vs_pass_rate": 0.76, "rank": 3}
                ]
            },
            "failure_by_field": [
                {"field": "test_mode_enabled", "fail_rate_by_value": {"0": 0.08, "1": 0.34}, "lift": 4.25},
                {"field": "cache_policy", "fail_rate_by_value": {"Disabled": 0.22, "LRU": 0.09, "Adaptive": 0.18}, "lift": 2.44},
                {"field": "queue_depth", "fail_rate_by_value": {"8": 0.10, "16": 0.12, "32": 0.24, "64": 0.28}, "lift": 2.80}
            ],
            "total_seconds": 18.94
        }
    }

def analyze_job(job_id, files):
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["progress"] = 10

        # Simulate file parsing
        jobs[job_id]["progress"] = 30

        # Simulate analysis
        jobs[job_id]["progress"] = 70

        # Load sample data
        result = generate_sample_result()

        jobs[job_id]["result"] = result
        jobs[job_id]["progress"] = 100
        jobs[job_id]["status"] = "completed"
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "bundled_sample_available": True
    }

@app.post("/api/analyze")
async def analyze(files: list[UploadFile] = File(...)):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "uploaded_files": [f.filename for f in files],
        "created_at": datetime.now().isoformat()
    }

    thread = threading.Thread(target=analyze_job, args=(job_id, files))
    thread.daemon = True
    thread.start()

    return {"job_id": job_id}

@app.post("/api/analyze-sample")
async def analyze_sample():
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "uploaded_files": ["bundled sample"],
        "created_at": datetime.now().isoformat()
    }

    thread = threading.Thread(target=analyze_job, args=(job_id, []))
    thread.daemon = True
    thread.start()

    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return {
        "status": job["status"],
        "progress": job.get("progress", 0),
        "error": job.get("error")
    }

@app.get("/api/jobs/{job_id}/result")
async def get_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if "result" not in jobs[job_id]:
        raise HTTPException(status_code=202, detail="Job not yet completed")
    return jobs[job_id]["result"]

@app.get("/api/jobs/{job_id}/runs")
async def get_runs(job_id: str, page: int = 0, per_page: int = 50):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if "result" not in jobs[job_id]:
        raise HTTPException(status_code=202, detail="Job not yet completed")

    runs = jobs[job_id]["result"].get("runs", [])
    start = page * per_page
    end = start + per_page
    return {
        "total": len(runs),
        "page": page,
        "per_page": per_page,
        "runs": runs[start:end]
    }

@app.get("/api/jobs/{job_id}/diff")
async def get_diff(job_id: str, run1_id: str, run2_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if "result" not in jobs[job_id]:
        raise HTTPException(status_code=202, detail="Job not yet completed")

    return {
        "run1": run1_id,
        "run2": run2_id,
        "differences": []
    }

@app.get("/api/jobs/{job_id}/export")
async def export_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if "result" not in jobs[job_id]:
        raise HTTPException(status_code=202, detail="Job not yet completed")

    return jobs[job_id]["result"]

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    del jobs[job_id]
    return {"status": "deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
