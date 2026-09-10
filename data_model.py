"""
Data model schema definition for Configuration Intelligence.

All fields are defined via configuration objects. Adding a new field to SCHEMA
requires NO changes to generate_dataset.py's core sampling logic for
configuration, randomization, and environment fields.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class FieldSpec:
    """Specification for a single field in the dataset schema.

    Attributes:
        name:                Column name in the output CSV.
        category:            One of "configuration", "randomization",
                             "environment", "outcome".
        field_type:          One of "categorical", "boolean", "numeric".
        domain:              List of allowed values (categorical/boolean/discrete-
                             numeric), or a (min, max) tuple for continuous numeric.
        distribution:        Sampling distribution – "uniform", "norm
        al", or
                             "log_normal".
        distribution_params: Extra distribution parameters (e.g. mean, std,
                             base_fail_rate).
        is_integer:          If True, numeric values are cast to int.
        is_discrete_set:     If True, *domain* is a list of discrete numeric
                             values (sampled uniformly).
        decimal_places:      Rounding precision for float numeric fields.
                             None = no rounding.
    """

    name: str
    category: str
    field_type: str
    domain: Union[List[Any], Tuple[float, float]]
    distribution: str = "uniform"
    distribution_params: Optional[Dict[str, Any]] = None
    is_integer: bool = False
    is_discrete_set: bool = False
    decimal_places: Optional[int] = None


# ═══════════════════════════════════════════════════════════════════════════
# Schema Definition
# ═══════════════════════════════════════════════════════════════════════════

SCHEMA: List[FieldSpec] = [
    # ── Configuration Fields (10) ─────────────────────────────────────────
    FieldSpec(
        name="cache_size",
        category="configuration",
        field_type="categorical",
        domain=["small", "medium", "large"],
    ),
    FieldSpec(
        name="scheduler",
        category="configuration",
        field_type="categorical",
        domain=["static", "dynamic", "adaptive"],
    ),
    FieldSpec(
        name="feature_x",
        category="configuration",
        field_type="boolean",
        domain=["ON", "OFF"],
    ),
    FieldSpec(
        name="feature_y",
        category="configuration",
        field_type="boolean",
        domain=["ON", "OFF"],
    ),
    FieldSpec(
        name="memory_size",
        category="configuration",
        field_type="numeric",
        domain=[256, 512, 1024, 2048, 4096],
        is_discrete_set=True,
        is_integer=True,
    ),

    FieldSpec(
        name="prefetch_depth",
        category="configuration",
        field_type="numeric",
        domain=[0, 2, 4, 8, 16],
        is_discrete_set=True,
        is_integer=True,
    ),
    FieldSpec(
        name="compression",
        category="configuration",
        field_type="categorical",
        # "off" rather than "none": ingest.py treats "none" as a null token,
        # which would silently blank out a quarter of this column.
        domain=["off", "lz4", "zstd", "gzip"],
    ),
    FieldSpec(
        name="queue_depth",
        category="configuration",
        field_type="numeric",
        domain=[1, 4, 16, 32, 64, 128],
        is_discrete_set=True,
        is_integer=True,
    ),
    FieldSpec(
        name="power_mode",
        category="configuration",
        field_type="categorical",
        domain=["eco", "balanced", "turbo"],
    ),
    FieldSpec(
        name="ecc_mode",
        category="configuration",
        field_type="categorical",
        domain=["off", "parity", "sec_ded", "bch"],
    ),

    # ── Randomization Fields (10) ─────────────────────────────────────────
    FieldSpec(
        name="random_seed",
        category="randomization",
        field_type="numeric",
        domain=(0, 99999),
        is_integer=True,
    ),
    FieldSpec(
        name="workload",
        category="randomization",
        field_type="categorical",
        domain=["small", "medium", "large"],
    ),
    FieldSpec(
        name="traffic_pattern",
        category="randomization",
        field_type="categorical",
        domain=["low", "medium", "high"],
    ),
    FieldSpec(
        name="timing",
        category="randomization",
        field_type="categorical",
        domain=["early", "mid", "late"],
    ),
    FieldSpec(
        name="input_size",
        category="randomization",
        field_type="numeric",
        domain=(100, 10000),
        is_integer=True,
    ),

    FieldSpec(
        name="burst_length",
        category="randomization",
        field_type="numeric",
        domain=(1, 256),
        is_integer=True,
    ),
    FieldSpec(
        name="access_pattern",
        category="randomization",
        field_type="categorical",
        domain=["sequential", "random", "stride", "mixed"],
    ),
    FieldSpec(
        name="concurrency",
        category="randomization",
        field_type="numeric",
        domain=[1, 2, 4, 8, 16, 32],
        is_discrete_set=True,
        is_integer=True,
    ),
    FieldSpec(
        name="injection_rate",
        category="randomization",
        field_type="numeric",
        domain=(0.0, 0.30),
        decimal_places=3,
    ),
    FieldSpec(
        name="payload_entropy",
        category="randomization",
        field_type="numeric",
        domain=(0.0, 1.0),
        decimal_places=3,
    ),

    # ── Environment Fields (2) ────────────────────────────────────────────
    FieldSpec(
        name="temperature",
        category="environment",
        field_type="numeric",
        domain=(25.0, 95.0),
        distribution="normal",
        distribution_params={"mean": 55.0, "std": 12.0},
        decimal_places=1,
    ),
    FieldSpec(
        name="voltage",
        category="environment",
        field_type="numeric",
        domain=(0.80, 1.20),
        distribution="normal",
        distribution_params={"mean": 1.0, "std": 0.06},
        decimal_places=3,
    ),

    # ── Outcome Fields (4) ────────────────────────────────────────────────
    FieldSpec(
        name="pass_fail",
        category="outcome",
        field_type="boolean",
        domain=["pass", "fail"],
        distribution_params={"base_fail_rate": 0.15},
    ),
    FieldSpec(
        name="execution_time",
        category="outcome",
        field_type="numeric",
        domain=(10.0, 500.0),
        distribution="log_normal",
        distribution_params={"mean": 4.5, "std": 0.5},
        decimal_places=1,
    ),
    FieldSpec(
        name="throughput",
        category="outcome",
        field_type="numeric",
        domain=(100, 10000),
        distribution_params={"derived_from": "execution_time"},
    ),
    FieldSpec(
        name="error_type",
        category="outcome",
        field_type="categorical",
        domain=["none", "timeout", "overflow", "corruption", "assertion",
                "thermal", "ecc_uncorrectable"],
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════

def get_fields_by_category(category: str) -> List[FieldSpec]:
    """Return all FieldSpec objects for the given category."""
    return [f for f in SCHEMA if f.category == category]


def get_field_names_by_category(category: str) -> List[str]:
    """Return field names for the given category."""
    return [f.name for f in SCHEMA if f.category == category]


def get_all_field_names() -> List[str]:
    """Return all field names in schema order."""
    return [f.name for f in SCHEMA]


def get_field(name: str) -> FieldSpec:
    """Look up a single FieldSpec by name. Raises KeyError if not found."""
    for f in SCHEMA:
        if f.name == name:
            return f
    raise KeyError(f"No field named '{name}' in schema")
