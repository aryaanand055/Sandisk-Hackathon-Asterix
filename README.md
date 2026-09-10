# Configuration Intelligence - Feature Interaction Discovery

A comprehensive system for discovering and analyzing hidden feature interactions in test run data through synthetic dataset generation, baseline model training, and interaction analysis.

## 🎯 Project Overview

This project implements an intelligent pipeline to:
- **Generate synthetic test data** with configurable schemas and hidden interaction rules
- **Train baseline models** to identify feature importances and relationships
- **Discover feature interactions** that reveal risky configuration combinations
- **Validate predictions** against ground truth rules

Configuration Intelligence helps identify non-obvious dependencies and interactions between system configuration parameters that significantly impact outcomes like pass/fail rates, execution time, and error types.

## 📋 Dataset Schema

The project uses a flexible, configuration-driven data model with four categories:

### Configuration Fields (System Settings)
- `cache_size`: small, medium, large
- `scheduler`: static, dynamic, adaptive
- `feature_x`, `feature_y`: ON/OFF toggles
- `memory_size`: 256, 512, 1024, 2048, 4096 MB

### Randomization Fields (Run Variability)
- `random_seed`: 0–99,999
- `workload`: small, medium, large
- `traffic_pattern`: low, medium, high
- `timing`: early, mid, late
- `input_size`: 100–10,000 units

### Environment Fields (External Conditions)
- `temperature`: 25°C–95°C (normally distributed)
- `voltage`: 0.80–1.20V (normally distributed)

### Outcome Fields (Results)
- `pass_fail`: pass or fail
- `execution_time`: 10–500 seconds (log-normal distribution)
- `throughput`: derived from execution_time
- `error_type`: none, timeout, overflow, corruption, assertion

## 🔧 Core Components

### 1. `data_model.py`
Defines the schema using `FieldSpec` dataclass. Fields automatically support:
- Categorical, boolean, and numeric types
- Custom distributions (uniform, normal, log-normal)
- Discrete sets and continuous ranges

**Key functions:**
- `get_fields_by_category()` — retrieve fields by role
- `get_field_names_by_category()` — get field names only
- `get_all_field_names()` — return schema in order

### 2. `generate_dataset.py`
Generates synthetic test-run data with injected interaction rules.

**Features:**
- Vectorized NumPy sampling for performance
- Data-driven rule engine with three effect types:
  - `failure_multiplier`: increases failure probability
  - `exec_time_multiplier`: scales execution time
  - `value_bias`: biases specific field values
- Two rule phases: sampling (alters inputs) and outcome (alters results)

**Usage:**
```bash
python generate_dataset.py --n-runs 1000 --seed 42 --output data.csv
```

**Output files:**
- `synthetic_test_runs.csv` — main dataset
- `ground_truth_rules.json` — injected rules

### 3. `train_baseline.py`
Trains a Random Forest classifier to identify feature importances.

**Workflow:**
1. Loads synthetic test runs
2. Builds a classification model (pass vs. fail)
3. Extracts feature importances
4. Computes feature lineage (parent/child relationships)

**Output:**
- `model_results.json` — feature importances and lineage

### 4. `interaction_analysis.py`
Discovers pairwise and 3-way feature combinations associated with failures.

**Algorithm:**
1. Selects top-K most important features
2. Enumerates pairwise and 3-way combinations
3. Computes failure rate **lift** (observed vs. baseline)
4. Filters low-support combinations (min 10 rows)
5. Ranks by lift metric

**Output:**
- `discovered_interactions.json` — ranked risky combinations
- Console report with top interactions

### 5. `grade_against_ground_truth.py`
Validates discovered interactions against ground truth rules.

**Metrics:**
- Precision: % of discovered interactions with corresponding ground truth rules
- Recall: % of ground truth rules identified by the discovery process
- Overlap: % of discovered interactions in top-N that match rules

**Output:**
- `grading_report.json` — precision, recall, F1 score

### 6. `preprocess.py`
Cleans and prepares raw data for analysis.

**Operations:**
- Missing value handling
- Outlier detection and treatment
- Feature normalization
- Data validation

### 7. `validate_dataset.py`
Ensures dataset integrity and schema compliance.

**Checks:**
- Field presence and correct types
- Value domain validation
- Category distribution checks

## 📊 Interaction Rules

The ground truth contains 7 predefined interaction rules covering:

1. **Dynamic scheduler + high traffic + small cache** → 3× failure multiplier (timeout bias)
2. **Small cache + large workload** → 2× execution time multiplier
3. **Feature X enabled + high temperature** → 2.5× failure multiplier (corruption bias)
4. **Low random seed** → 70% probability of large workload selection
5. **Low voltage + large memory** → 2× failure multiplier (corruption bias)
6. **Feature Y + adaptive scheduler + large input** → 2× failure multiplier (overflow bias)
7. **Late timing + elevated temperature** → 1.5× execution time multiplier

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

**Dependencies:**
- numpy >= 1.24
- pandas >= 2.0
- scikit-learn >= 1.3

### Generate Data

```bash
python generate_dataset.py --n-runs 10000 --seed 42
```

### Train Model

```bash
python train_baseline.py --input synthetic_test_runs.csv
```

### Discover Interactions

```bash
python interaction_analysis.py --input synthetic_test_runs.csv --results model_results.json --top-k 20
```

### Validate Against Ground Truth

```bash
python grade_against_ground_truth.py --discovered discovered_interactions.json --ground-truth ground_truth_rules.json
```

## 📁 File Structure

```
.
├── data_model.py                          # Schema definition
├── generate_dataset.py                    # Dataset generation
├── train_baseline.py                      # Model training
├── interaction_analysis.py                # Interaction discovery
├── grade_against_ground_truth.py          # Validation & grading
├── preprocess.py                          # Data preprocessing
├── validate_dataset.py                    # Dataset validation
├── requirements.txt                       # Python dependencies
│
├── synthetic_test_runs.csv                # Generated dataset
├── synthetic_test_runs_with_predictions.csv  # Predictions added
├── ground_truth_rules.json                # Injected rules
├── model_results.json                     # Feature importances
├── discovered_interactions.json           # Top risky combinations
├── feature_lineage.json                   # Feature relationships
└── grading_report.json                    # Validation metrics
```

## 🔍 Key Concepts

### Feature Importance
Measures how much a feature contributes to model predictions. Derived from Random Forest via Gini importance or permutation importance.

### Feature Lineage
Tracks parent-child relationships between features, revealing which features are derived from or dependent on others.

### Lift
The ratio of observed failure rate within a subgroup to the overall baseline:
```
Lift = P(fail | combination) / P(fail | all data)
```
- Lift = 2.0 means 2× higher failure rate in this combination
- Used to rank interaction severity

### Support
The number of rows in the dataset matching a specific feature combination. Low-support combinations are filtered out (min 10 rows).

## 🎓 Use Cases

- **Configuration Testing**: Identify dangerous setting combinations
- **Reliability Engineering**: Discover failure-prone scenarios
- **Performance Analysis**: Analyze execution time dependencies
- **Environmental Testing**: Study temperature/voltage effects
- **Predictive Maintenance**: Forecast failures based on config interactions

## 📈 Output Examples

### discovered_interactions.json
```json
[
  {
    "features": ["scheduler", "traffic_pattern", "cache_size"],
    "values": ["dynamic", "high", "small"],
    "failure_rate": 0.45,
    "baseline_rate": 0.15,
    "lift": 3.0,
    "support": 142
  }
]
```

### grading_report.json
```json
{
  "total_discovered": 15,
  "total_ground_truth": 7,
  "matched": 6,
  "precision": 0.40,
  "recall": 0.86,
  "f1_score": 0.54
}
```

## 🏗️ Architecture Highlights

- **Vectorized Sampling**: All field sampling uses NumPy arrays for performance
- **Schema-Driven**: Add new fields to `SCHEMA` in `data_model.py`—no changes to generation logic
- **Data-Driven Rules**: Rules defined as JSON dictionaries, easily extensible
- **Two-Phase Injection**: Sampling phase modifies inputs; outcome phase modifies results

## 🤝 Contributing

To extend this project:

1. **Add a new field**: Update `SCHEMA` in `data_model.py`
2. **Add a new rule**: Append to `RULES` in `generate_dataset.py` with conditions and effects
3. **Modify analysis**: Edit `interaction_analysis.py` to change binning, top-K selection, or ranking

## 📝 License

This project is part of the Sandisk Hackathon initiative.

## 👥 Authors

Configuration Intelligence Team

---

**Last Updated:** September 9, 2026
