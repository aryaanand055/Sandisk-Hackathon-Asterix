"""
Canonical UVM simulation-log format.

This module is the single source of truth for the log grammar. The generator
writes it and the parser reads it, so the two can never drift apart.

Layout of one run block
-----------------------
    ================================================================
    UVM SIMULATION LOG :: RUN-000001
    ================================================================
    [CONFIG]
    {"run_id": "RUN-000001", "test_name": "...", ...}
    [/CONFIG]
    UVM_INFO @ 0 ns: reporter [RNTST] Running test ...
    UVM_ERROR @ 45210 ns: uvm_test_top.env.sb [FIFO_OVERFLOW] Write to full ...
    UVM_FATAL @ 45230 ns: uvm_test_top [TEST_ABORT] Unrecoverable ...
    [METRICS]
    {"execution_time_ms": 412.7, "throughput_mbps": 1893.2, ...}
    [/METRICS]
    --- UVM Report Summary ---
    UVM_INFO    :   12
    UVM_WARNING :    0
    UVM_ERROR   :    3
    UVM_FATAL   :    1
    ** TEST FAILED **

Many run blocks are concatenated into one .log file. Files are plain UTF-8.
"""

import re

RUN_SEPARATOR = "=" * 64
BANNER = "UVM SIMULATION LOG :: "

CONFIG_OPEN, CONFIG_CLOSE = "[CONFIG]", "[/CONFIG]"
METRICS_OPEN, METRICS_CLOSE = "[METRICS]", "[/METRICS]"
SUMMARY_HEADER = "--- UVM Report Summary ---"

VERDICT_PASS = "** TEST PASSED **"
VERDICT_FAIL = "** TEST FAILED **"


# ── Regexes ────────────────────────────────────────────────────────────────

# UVM_ERROR @ 45210 ns: uvm_test_top.env.sb [FIFO_OVERFLOW] Write to full FIFO...
RE_UVM_LINE = re.compile(
    r"^UVM_(?P<severity>INFO|WARNING|ERROR|FATAL)\s+@\s+(?P<time_ns>\d+)\s+ns:\s+"
    r"(?P<component>\S+)\s+\[(?P<tag>[A-Z0-9_]+)\]\s+(?P<message>.*)$"
)

RE_BANNER = re.compile(r"^" + re.escape(BANNER) + r"(?P<run_id>\S+)\s*$")
RE_VERDICT = re.compile(r"^\*\* TEST (?P<verdict>PASSED|FAILED) \*\*\s*$")
RE_SUMMARY_COUNT = re.compile(
    r"^UVM_(?P<severity>INFO|WARNING|ERROR|FATAL)\s*:\s*(?P<count>\d+)\s*$"
)

# Volatile tokens inside an error message: hex addresses, decimal ids, cycles.
# Masked out when building a failure fingerprint so that two runs hitting the
# same RTL bug with different seeds collapse onto the same template.
RE_HEX = re.compile(r"0x[0-9a-fA-F]+")
RE_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")


# ── Error taxonomy ─────────────────────────────────────────────────────────

ERROR_TAGS = [
    "FIFO_OVERFLOW",
    "ECC_UNCORRECTABLE",
    "TIMEOUT",
    "DATA_MISMATCH",
    "PROTOCOL_VIOLATION",
    "ASSERTION_FAIL",
    "RETENTION_FAIL",
]

# Components that raise each tag - kept realistic per error class.
ERROR_COMPONENT = {
    "FIFO_OVERFLOW":      "uvm_test_top.env.sb",
    "ECC_UNCORRECTABLE":  "uvm_test_top.env.ecc_mon",
    "TIMEOUT":            "uvm_test_top.env.agent.mon",
    "DATA_MISMATCH":      "uvm_test_top.env.sb",
    "PROTOCOL_VIOLATION": "uvm_test_top.env.agent.protocol_chk",
    "ASSERTION_FAIL":     "uvm_test_top.dut_wrapper",
    "RETENTION_FAIL":     "uvm_test_top.env.nand_model",
}


def fingerprint(message: str) -> str:
    """Collapse an error message to its seed-invariant template.

    Hex addresses become <ADDR> and bare numbers become <N>, so
    'wr_ptr=0x1f depth=32' and 'wr_ptr=0x04 depth=16' share a fingerprint.
    """
    masked = RE_HEX.sub("<ADDR>", message)
    masked = RE_NUM.sub("<N>", masked)
    return " ".join(masked.split())
