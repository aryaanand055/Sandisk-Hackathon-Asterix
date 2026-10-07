# UVM Configuration Intelligence

Team Asterix, Sandisk Hackathon.

A web dashboard that takes UVM simulation logs (or CSV exports of verification
runs), and tells you which configuration settings make tests fail, which
failures are deterministic RTL bugs rather than seed noise, and which
configuration gives the most throughput while staying under a risk ceiling.

React front end, FastAPI back end, analysis on a worker thread with the UI
polling for progress. Full technical detail, including the log format, the
embedded failure rules and the API, is in [DASHBOARD.md](DASHBOARD.md).

---

## Quick start

Requires Python 3.11 (what the timings in DASHBOARD.md were measured on) and Node 18+ for Vite 5.

```bash
# Python dependencies
pip install -r requirements.txt
pip install python-dotenv google-genai   # backend imports dotenv at start-up; genai is for the AI Copilot

# 1. Generate the bundled log corpus (once: 50,000 runs, ~56 MB across 10 files)
python -m uvm_intel.generate_logs --n-runs 50000 --parts 10

# 2. Start the API on :8000
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 3. In another terminal, start the UI on :5173 (proxies /api to :8000)
cd frontend && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173), then either drop files on the upload zone or
click **Use bundled sample** to analyse the generated corpus.

The AI Copilot tab needs a Google Gemini API key, typed into the tab or set as
`GEMINI_API_KEY` in your environment or a `.env` file. Without one it still
answers with a rule-based summary.

---

## What you can upload

| Input                                                                                                   | Handled by                                                  |
| ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `.log` UVM simulation logs                                                                            | [`uvm_intel/log_parser.py`](uvm_intel/log_parser.py)       |
| `.csv` run tables, single or split by category (config, outcomes, telemetry, …) joined on `run_id` | [`uvm_intel/csv_parser.py`](uvm_intel/csv_parser.py)       |
| `.fsdb` / `.vcd` / `.wlf` waveforms, as companions to a log or CSV                                | [`uvm_intel/waveform_stub.py`](uvm_intel/waveform_stub.py) |

[`uvm_intel/ingest_multi.py`](uvm_intel/ingest_multi.py) routes each file to
its parser and merges the results into one run table. Uploads are capped at
512 MB per job.

Ready-made inputs live under `data/`: `data/datasets/` (four designs in
different formats), `data/test_samples/` and `data/nvme_logs/`.

---

## Analysis pipeline

```
uploaded files ──► ingest_multi ──► runs + errors frames
                                          │
      ┌───────────────┬───────────────────┼────────────────┬───────────────┐
      ▼               ▼                   ▼                ▼               ▼
 risk_model      fingerprints          pareto         config_diff     recommender
LightGBM+SHAP   TF-IDF+DBSCAN         frontier       twin diffing     Optuna TPE
```

Orchestrated by [`uvm_intel/pipeline.py`](uvm_intel/pipeline.py). Each stage
runs independently, so a failure in one is reported in the stage log and the
rest of the report still renders.

- **Risk model:** LightGBM trained on configuration knobs only (outcome
  columns and seed excluded to avoid leakage), with SHAP for global and
  per-value attribution.
- **Failure fingerprints:** error messages masked to seed-invariant templates,
  clustered with TF-IDF and DBSCAN, and scored for determinism. A cluster with
  one distinct trace across many seeds is flagged as a deterministic RTL bug.
- **Pareto:** throughput vs predicted risk frontier over grouped
  configurations, with peak, knee and best-safe operating points.
- **Recommender:** Optuna TPE maximising throughput subject to predicted risk
  of 2% or less (tunable).
- **Config diff:** pairs each failing run with its nearest passing twin and
  ranks the settings that differ.

---

## Dashboard tabs

| Tab                            | What it shows                                                                 |
| ------------------------------ | ----------------------------------------------------------------------------- |
| **Executive Summary**    | KPIs, pass/fail split, risk bands, SHAP drivers, failure modes, model metrics |
| **AI Copilot**           | Ask questions about the analysis in plain English (Google Gemini)             |
| **Failure Fingerprints** | Cluster map, determinism scores, masked template and raw trace per cluster    |
| **Tradeoff Matrix**      | Interactive Pareto scatter and frontier table                                 |
| **Recommendations**      | Optimiser results and search history                                          |
| **Config Diff**          | Twin-divergence ranking and a two-run diff viewer                             |
| **Run Explorer**         | Paged, filterable table of every parsed run                                   |
| **All Details**          | Parse stats, stage timings, failure rate by field, job metadata               |

---

## Repository layout

```
backend/main.py          FastAPI app: upload, job polling, results, diff, export, copilot
frontend/                React + Vite dashboard
uvm_intel/               Parsers, generators and analysis stages
  log_format.py            Shared log grammar used by generator and parser
  generate_logs.py         Synthetic UVM log corpus with embedded failure rules
  pipeline.py              Runs every analysis stage for a job
  copilot.py               Gemini-backed AI Copilot
tools/                   Generators and validators for the datasets under data/
data/                    Sample inputs and uvm_ground_truth.json
presentation/            Hackathon slide deck and its build script
```

The top-level scripts (`generate_dataset.py`, `train_baseline.py`,
`interaction_analysis.py`, `grade_against_ground_truth.py` and the
`synthetic_test_runs*.csv` / `*.json` outputs beside them) are the project's
first prototype: a synthetic CSV pipeline with a Random Forest baseline and
pairwise lift analysis. The dashboard does not use them.

---

## CLI without the dashboard

```bash
# Parse logs straight to CSV
python -m uvm_intel.log_parser "data/uvm_logs/*.log"

# Generate an NVMe-flavoured log set with waveform stubs
python -m uvm_intel.generate_nvme_logs --n-runs 1000 --output-dir data/nvme_logs
```
