# UVM Configuration Intelligence Dashboard

Upload UVM simulation logs, get a parsed, modelled and clustered analysis back.

React + FastAPI. Analysis runs on a worker thread; the UI polls for progress.

---

## Quick start

Three terminals (or run the first two in the background).

**1. Generate the log corpus** (once — 50,000 runs, ~56 MB across 10 files):

```bash
python -m uvm_intel.generate_logs --n-runs 50000 --parts 10
```

**2. Start the API:**

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**3. Start the UI:**

```bash
cd frontend && npm install && npm run dev
```

Open <http://localhost:5173>. Drop `.log` files on the dropzone, or click
**Use bundled sample** to analyse the generated corpus without uploading.

---

## Pipeline

```
raw .log  ──►  log_parser  ──►  runs + errors frames
                                      │
        ┌─────────────────────────────┼──────────────────────────────┐
        ▼               ▼             ▼              ▼               ▼
   risk_model     fingerprints     pareto      config_diff     recommender
  LightGBM+SHAP   TF-IDF+DBSCAN   frontier    twin diffing    Optuna TPE
```

Each stage is wrapped independently — if one fails, the rest of the report
still renders and the failure is reported in the stage log rather than
killing the job.

---

## Phase 1 — data & ingestion

### Log format

Defined once in [`uvm_intel/log_format.py`](uvm_intel/log_format.py) and shared
by the generator and the parser, so the two cannot drift apart.

```
================================================================
UVM SIMULATION LOG :: RUN-000001
================================================================
[CONFIG]
{"run_id":"RUN-000001","test_name":"Back_To_Back_Program",...}
[/CONFIG]
UVM_INFO  @ 0 ns: reporter [RNTST] Running test ...
UVM_ERROR @ 45210 ns: uvm_test_top.env.sb [FIFO_OVERFLOW] Write to full FIFO: ...
[METRICS]
{"execution_time_ms":412.7,"throughput_mbps":1893.2,...}
[/METRICS]
--- UVM Report Summary ---
UVM_ERROR   :    3
** TEST FAILED **
```

The parser is a single pass with `startswith` guards before any regex. The full
50,000-run corpus — 1,015,872 lines — parses in **2.0 s** with zero malformed
blocks and zero unparsed lines.

### Embedded failure rules

Written to `data/uvm_ground_truth.json` so a pipeline can be graded on whether
it rediscovers them. Observed lift at 50,000 runs:

| Rule | Condition | Effect | Runs | Fail rate | Lift |
|---|---|---|---:|---:|---:|
| R1 | `test_name=Back_To_Back_Program` + `cache_policy=Adaptive` | set 0.85, FIFO_OVERFLOW | 2,891 | 0.851 | 4.19× |
| R2 | `test_mode_enabled=1` | +0.35 | 13,999 | 0.473 | 3.16× |
| R3 | `queue_depth≥32` + `ecc_mode=Disabled` | +0.35, ECC_UNCORRECTABLE | 1,976 | 0.574 | 2.53× |
| R4 | `temperature_c>85` + `voltage_mv<1100` | +0.30, RETENTION_FAIL | 281 | 0.559 | 2.34× |
| R5 | `num_planes=4` + `burst_length=64` + `scrambler_enable=1` | set 0.98, **deterministic** | 815 | 0.987 | 4.33× |
| R6 | `clock_freq_mhz≥1000` + `prefetch_depth>8` | +0.30, TIMEOUT | 8,014 | 0.475 | 2.43× |
| R7 | `cache_policy=Disabled` + `queue_depth≥16` | +0.30, DATA_MISMATCH | 2,800 | 0.493 | 2.19× |

R1 and R2 are the two rules from the brief. R5 is the planted deterministic RTL
bug — it emits a byte-identical trace on every hit, which is what the
fingerprinting tab is built to isolate.

Base failure probability is **0.012**, deliberately: a clean configuration has
to sit below the 2% ceiling the recommender optimises against, otherwise that
constraint is unsatisfiable by construction. Overall failure rate is 24%.

---

## Phase 2 — analytics

**Risk model** — LightGBM on configuration knobs only. Outcome columns
(`execution_time_ms`, `throughput_mbps`, `error_type`, …) are excluded to
prevent label leakage, as is `seed`. SHAP `TreeExplainer` gives global
importance plus per-value attribution for categoricals. Typical ROC-AUC 0.88.

**Failure fingerprinting** — every error message is masked to a seed-invariant
template (`0x0004a2c0` → `<ADDR>`, `32` → `<N>`), TF-IDF is fitted over the
*distinct templates* rather than every run (a 50k corpus collapses to ~7
templates, keeping DBSCAN's pairwise work trivial), and each run inherits its
template's cluster.

The key output is a determinism score:

```
determinism = 1 − (distinct raw traces ÷ runs in cluster)
```

A cluster with byte-identical text across many seeds scores near 1.0 and is
flagged a deterministic RTL bug. On the bundled corpus:

```
c1  n=804   PROTOCOL_VIOLATION  det=0.9988  seeds=804   raw=1     deterministic RTL bug
c2  n=3040  TIMEOUT             det=0.0000  seeds=3040  raw=3040  seed-dependent / random
```

804 runs, 804 different seeds, **one** distinct trace — exactly the separation
the brief asks for.

> `min_samples=1` is intentional. Every distinct template is already a real
> failure mode; a template seen once is a rare bug, not noise to discard. `eps`
> still merges templates that are only wording variants of each other.

**Pareto** — frontier over throughput vs predicted risk. Points are grouped
over the top-4 SHAP-ranked *discrete* settings, not the raw config: continuous
readings like `voltage_mv` are unique per run, so including them would make
every run its own "configuration" and compare 10,000 singletons with a
meaningless observed rate. Grouping gives 318 configs with 3–109 runs each,
and predicted risk tracks observed failure closely (0.139 vs 0.139).

---

## Phase 3 — recommendation & diffing

**Recommender** — Optuna TPE over two surrogates: the risk classifier and a
throughput regressor fitted on *passing runs only* (so the objective is
"throughput when it works", not throughput averaged with degraded failures).
Maximises throughput subject to predicted risk ≤ 2%, expressed as a penalty so
TPE still learns the shape of the constraint. If the ceiling is unreachable the
response says so and falls back to the lowest-risk configs found.

**Config diff** — two views, both scoped to identical test sequences:

- *Aggregate delta*: how each setting's distribution shifts between passing and
  failing runs.
- *Nearest-twin*: each failing run paired with its most similar **passing** run,
  recording exactly which settings differ. Numeric fields only count as changed
  when they move ≥ 0.5 SD — otherwise `voltage_mv` and `temperature_c` differ
  between any two runs and rank at ~100%, burying the settings that matter.

---

## Dashboard tabs

| Tab | Contents |
|---|---|
| **Executive Summary** | KPI strip, pass/fail donut, risk-band histogram, global SHAP chart, failure-mode distribution, ROC curve, metrics, confusion matrix, timing by failure mode |
| **Failure Fingerprints** | Cluster map (SVD scatter), cluster table with determinism scores, drill-down with masked template + raw trace, hand-off to the diff viewer |
| **Tradeoff Matrix** | Interactive Pareto scatter, peak / knee / best-safe operating points, full frontier table |
| **Recommendations** | Optuna results, optimisation history, derived search space |
| **Config Diff** | Twin-divergence ranking, interactive two-run log-diff viewer, closest failing/passing pairs, aggregate deltas per sequence |
| **Run Explorer** | Paged, filterable, searchable table of every parsed run |
| **All Details** | Parse stats, per-stage timing log, failure rate by field with lift, metric distributions, highest-risk runs, job metadata, column inventory |

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness + bundled-sample availability |
| `POST` | `/api/analyze` | Upload `.log` files, start a job |
| `POST` | `/api/analyze-sample` | Analyse the bundled corpus |
| `GET` | `/api/jobs/{id}` | Status + progress |
| `GET` | `/api/jobs/{id}/result` | Full analysis payload |
| `GET` | `/api/jobs/{id}/runs` | Paged run table (filter/search/sort) |
| `GET` | `/api/jobs/{id}/diff` | Field-by-field diff of two runs |
| `GET` | `/api/jobs/{id}/export` | Download payload as JSON |
| `DELETE` | `/api/jobs/{id}` | Drop a job |

Tunable per job: `max_risk`, `n_trials`, `dbscan_eps`, `enable_recommender`.

---

## CLI

```bash
# Generate logs
python -m uvm_intel.generate_logs --n-runs 50000 --parts 10

# Parse to CSV without the dashboard
python -m uvm_intel.log_parser "data/uvm_logs/*.log"
```

---

## Performance

Measured on the bundled corpus (Python 3.11, 8 cores):

| Runs | Parse | Full analysis |
|---:|---:|---:|
| 5,000 | ~0.6 s | 9.6 s |
| 10,000 | ~1.2 s | 27 s |

Upload cap is 512 MB.

---

## Not built

The **RAG copilot** (ChromaDB + LangChain natural-language Q&A) from Phase 4 is
not implemented — it was listed as a bonus and needs an LLM endpoint and key,
which is a separate decision. Everything else in the plan is in place.
