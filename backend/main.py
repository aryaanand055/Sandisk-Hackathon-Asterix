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
        "executive_summary": {
            "total_runs": 50000,
            "overall_fail_rate": 0.24,
            "model_auc": 0.88,
            "num_rules_discovered": 7,
            "failure_mode_distribution": [
                {"mode": "FIFO_OVERFLOW", "count": 2891},
                {"mode": "TIMEOUT", "count": 8014},
                {"mode": "ECC_UNCORRECTABLE", "count": 1976},
            ],
            "metrics": {
                "precision": 0.89,
                "recall": 0.85,
                "f1_score": 0.87
            }
        },
        "fingerprints": {
            "clusters": [
                {
                    "id": "c1",
                    "error_type": "PROTOCOL_VIOLATION",
                    "run_count": 804,
                    "determinism_score": 0.9988,
                    "is_deterministic": True,
                    "svd_x": 2.5,
                    "svd_y": -1.2
                },
                {
                    "id": "c2",
                    "error_type": "TIMEOUT",
                    "run_count": 3040,
                    "determinism_score": 0.0,
                    "is_deterministic": False,
                    "svd_x": -1.8,
                    "svd_y": 2.3
                }
            ]
        },
        "pareto": {
            "frontier": [
                {"throughput": 1200, "predicted_risk": 0.015, "label": "config1"},
                {"throughput": 1500, "predicted_risk": 0.020, "label": "config2"},
                {"throughput": 1800, "predicted_risk": 0.040, "label": "config3"},
            ],
            "peak_throughput": {"throughput": 1800, "predicted_risk": 0.040},
            "knee_point": {"throughput": 1500, "predicted_risk": 0.020},
            "best_safe_config": {"throughput": 1200, "predicted_risk": 0.015}
        },
        "recommendations": {
            "n_trials": 250,
            "max_risk": 0.02,
            "recommended_configs": [
                {"throughput": 1200, "predicted_risk": 0.015, "config_hash": "abc123def456"},
                {"throughput": 1180, "predicted_risk": 0.018, "config_hash": "xyz789uvw012"},
            ]
        },
        "config_diff": {
            "twin_divergence": [
                {"setting": "cache_policy", "failing_value": "Adaptive", "passing_value": "LRU", "divergence_rate": 0.95, "impact_level": "high"},
                {"setting": "queue_depth", "failing_value": "32", "passing_value": "16", "divergence_rate": 0.87, "impact_level": "high"},
                {"setting": "test_mode_enabled", "failing_value": "1", "passing_value": "0", "divergence_rate": 0.78, "impact_level": "medium"},
            ]
        },
        "runs": [
            {"run_id": "RUN-000001", "test_name": "Back_To_Back_Program", "status": "pass", "execution_time_ms": 412.7, "throughput_mbps": 1893.2},
            {"run_id": "RUN-000002", "test_name": "Back_To_Back_Program", "status": "fail", "execution_time_ms": 405.2, "throughput_mbps": 1850.1},
        ] + [{"run_id": f"RUN-{i:06d}", "test_name": "Test", "status": "pass" if i % 4 != 0 else "fail", "execution_time_ms": 400 + i % 100, "throughput_mbps": 1800 + i % 500} for i in range(3, 100)],
        "details": {
            "parse_stats": {
                "total_lines": 1015872,
                "malformed_blocks": 0,
                "parse_time_sec": 2.0
            },
            "stage_timing": {
                "parse": 2.0,
                "risk_model": 5.2,
                "fingerprints": 3.1,
                "pareto": 1.8,
                "recommender": 12.4,
                "config_diff": 2.5
            },
            "field_analysis": [
                {"field": "cache_policy", "fail_rate": 0.45, "lift": 4.19, "top_value": "Adaptive"},
                {"field": "test_mode_enabled", "fail_rate": 0.35, "lift": 3.16, "top_value": "1"},
                {"field": "queue_depth", "fail_rate": 0.38, "lift": 2.53, "top_value": "32"},
            ]
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
