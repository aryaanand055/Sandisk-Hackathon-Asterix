#!/usr/bin/env python3
"""
Test Sample Generator for SanDisk Verification Analytics Platform.

Generates realistic verification data across diverse designs and formats:
1. Design 1 (NVMe SSD Controller): Single .log file (UVM simulation log grammar)
2. Design 2 (DDR5 Memory Controller & PHY): Single .log file (High-bandwidth memory architecture)
3. Design 3 (APB Peripheral Subsystem):
   - Single .log file (sandisk_apb_periph.log)
   - Single .csv file (sandisk_apb_periph_runs.csv)
   - Multi-file CSV folder (apb_peripheral_csv/) with aliased columns
4. Design 4 (UFS 4.0 Mobile Storage Controller):
   - Single .log file (sandisk_ufs40_mobile.log)
   - Single .csv file (sandisk_ufs40_mobile_runs.csv)
   - Multi-file CSV folder (ufs40_mobile_storage_csv/) with missing optional tables
5. Waveform Companion Files (.fsdb, .vcd, .wlf) for multi-modal verification testing
"""

import json
import os
import shutil
import numpy as np
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "data", "test_samples")

RUN_SEPARATOR = "=" * 64
BANNER = "UVM SIMULATION LOG :: "
CONFIG_OPEN, CONFIG_CLOSE = "[CONFIG]", "[/CONFIG]"
METRICS_OPEN, METRICS_CLOSE = "[METRICS]", "[/METRICS]"
SUMMARY_HEADER = "--- UVM Report Summary ---"
VERDICT_PASS = "** TEST PASSED **"
VERDICT_FAIL = "** TEST FAILED **"


def _pick(rng, values, weights, n):
    p = np.asarray(weights, float) / np.sum(weights) if weights else None
    return rng.choice(values, size=n, p=p)


# ==============================================================================
# 1. DESIGN: SanDisk PCIe Gen5 NVMe SSD Controller (.log format)
# ==============================================================================
def generate_nvme_log(n_runs=300, seed=101):
    rng = np.random.default_rng(seed)
    tests = [
        "Back_To_Back_Program", "Random_Read", "Sequential_Write",
        "Erase_Suspend", "Mixed_RW_Stress", "Power_Loss_Recovery", "Wear_Leveling_Sweep"
    ]
    cache_policies = ["Adaptive", "WriteThrough", "WriteBack", "Disabled"]
    ecc_modes = ["LDPC", "BCH", "Disabled"]

    lines = []
    for i in range(1, n_runs + 1):
        run_id = f"RUN-{i:06d}"
        test = str(_pick(rng, tests, [0.22, 0.18, 0.18, 0.12, 0.12, 0.10, 0.08], 1)[0])
        cache = str(_pick(rng, cache_policies, [0.35, 0.25, 0.25, 0.15], 1)[0])
        qd = int(_pick(rng, [4, 8, 16, 32, 64], [0.15, 0.25, 0.30, 0.20, 0.10], 1)[0])
        ecc = str(_pick(rng, ecc_modes, [0.55, 0.35, 0.10], 1)[0])
        num_channels = int(_pick(rng, [2, 4, 8], [0.25, 0.50, 0.25], 1)[0])
        num_planes = int(_pick(rng, [1, 2, 4], [0.30, 0.45, 0.25], 1)[0])
        burst_len = int(_pick(rng, [8, 16, 32, 64], [0.20, 0.35, 0.30, 0.15], 1)[0])
        clk_mhz = int(_pick(rng, [600, 800, 1000, 1200], [0.20, 0.35, 0.30, 0.15], 1)[0])
        scrambler = int(_pick(rng, [0, 1], [0.35, 0.65], 1)[0])
        temp_c = round(float(rng.normal(65, 14)), 1)
        volt_mv = round(float(rng.normal(1150, 40)), 1)

        fail = False
        error_tag = None
        error_msg = None
        comp = "uvm_test_top.env.sb"

        if test == "Back_To_Back_Program" and cache == "Adaptive" and rng.random() < 0.82:
            fail = True
            error_tag = "FIFO_OVERFLOW"
            error_msg = f"Write to full FIFO: fifo_id={rng.integers(0, 4)} wr_ptr=0x{rng.integers(128, 256):02x} rd_ptr=0x04"
            comp = "uvm_test_top.env.nand_sb"
        elif qd >= 32 and ecc == "Disabled" and rng.random() < 0.78:
            fail = True
            error_tag = "ECC_UNCORRECTABLE"
            error_msg = f"Uncorrectable multi-bit ECC error: sector=0x{rng.integers(1000, 99999):08x} syndrome=0xdead"
            comp = "uvm_test_top.env.ecc_mon"
        elif temp_c > 82 and volt_mv < 1120 and rng.random() < 0.75:
            fail = True
            error_tag = "RETENTION_FAIL"
            error_msg = f"NAND charge retention failed: die_temp={temp_c}C vdd={volt_mv}mV raw_ber=0.0452"
            comp = "uvm_test_top.env.nand_model"
        elif num_planes == 4 and burst_len == 64 and scrambler == 1 and rng.random() < 0.85:
            fail = True
            error_tag = "PROTOCOL_VIOLATION"
            error_msg = f"AXI4 burst violation on plane 3: beat=64 expected_ack=1 observed_ack=0"
            comp = "uvm_test_top.env.axi_agent.protocol_chk"
        elif rng.random() < 0.04:
            fail = True
            error_tag = "TIMEOUT"
            error_msg = f"Watchdog timeout waiting for completion on queue {rng.integers(0, 4)}"
            comp = "uvm_test_top.env.axi_agent.mon"

        exec_time_ms = round(float(rng.uniform(150, 450) if not fail else rng.uniform(80, 220)), 2)
        tp_mbps = round(float(rng.uniform(2200, 4800) if not fail else rng.uniform(400, 1500)), 2)
        cycles = int(exec_time_ms * clk_mhz * 1000)

        cfg_obj = {
            "run_id": run_id,
            "design": "SanDisk_PCIe_Gen5_NVMe_SSD",
            "test_name": test,
            "cache_policy": cache,
            "queue_depth": qd,
            "ecc_mode": ecc,
            "num_channels": num_channels,
            "num_planes": num_planes,
            "burst_length": burst_len,
            "clock_freq_mhz": clk_mhz,
            "scrambler_enable": scrambler,
            "temperature_c": temp_c,
            "voltage_mv": volt_mv,
        }
        metric_obj = {
            "execution_time_ms": exec_time_ms,
            "throughput_mbps": tp_mbps,
            "sim_cycles": cycles,
        }

        lines.append(RUN_SEPARATOR)
        lines.append(f"{BANNER}{run_id}")
        lines.append(RUN_SEPARATOR)
        lines.append(CONFIG_OPEN)
        lines.append(json.dumps(cfg_obj))
        lines.append(CONFIG_CLOSE)
        lines.append(f"UVM_INFO @ 0 ns: reporter [RNTST] Running test {test}...")
        lines.append(f"UVM_INFO @ 1200 ns: uvm_test_top.env.axi_agent [CFG_SYNC] PCIe Gen5 link trained x4 @ 32.0 GT/s")

        if fail:
            err_time = int(rng.integers(15000, 120000))
            lines.append(f"UVM_ERROR @ {err_time} ns: {comp} [{error_tag}] {error_msg}")
            lines.append(f"UVM_FATAL @ {err_time + 50} ns: uvm_test_top [TEST_ABORT] Run terminated due to fatal error condition")

        lines.append(METRICS_OPEN)
        lines.append(json.dumps(metric_obj))
        lines.append(METRICS_CLOSE)
        lines.append(SUMMARY_HEADER)
        lines.append(f"UVM_INFO    :   {rng.integers(14, 25)}")
        lines.append(f"UVM_WARNING :   {1 if rng.random() < 0.2 else 0}")
        lines.append(f"UVM_ERROR   :   {1 if fail else 0}")
        lines.append(f"UVM_FATAL   :   {1 if fail else 0}")
        lines.append(VERDICT_FAIL if fail else VERDICT_PASS)
        lines.append("")

    out_file = os.path.join(OUTPUT_DIR, "sandisk_nvme_gen5_ssd.log")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated {n_runs} runs: {out_file}")


# ==============================================================================
# 2. DESIGN: SanDisk DDR5 Memory Controller & DFI 5.0 PHY (.log format)
# ==============================================================================
def generate_ddr5_log(n_runs=300, seed=202):
    rng = np.random.default_rng(seed)
    tests = [
        "Ddr5_Bank_Interleave_Stress", "Refresh_Under_Heavy_Write",
        "ODT_Switching_Sweep", "Dfi_Protocol_Verify",
        "Ecc_Bitflip_Recovery", "PowerDown_Exit_Timing"
    ]
    dram_freqs = [3200, 4800, 5600, 6400]
    cas_latencies = [32, 36, 40]
    refresh_modes = ["Normal", "FineGranularity", "AllBank"]
    odt_values = [34, 40, 48]

    lines = []
    for i in range(1, n_runs + 1):
        run_id = f"RUN-{i:06d}"
        test = str(_pick(rng, tests, [0.24, 0.22, 0.18, 0.14, 0.12, 0.10], 1)[0])
        freq = int(_pick(rng, dram_freqs, [0.15, 0.35, 0.30, 0.20], 1)[0])
        cl = int(_pick(rng, cas_latencies, [0.35, 0.40, 0.25], 1)[0])
        ref_mode = str(_pick(rng, refresh_modes, [0.45, 0.35, 0.20], 1)[0])
        odt = int(_pick(rng, odt_values, [0.30, 0.45, 0.25], 1)[0])
        bank_groups = int(_pick(rng, [4, 8], [0.40, 0.60], 1)[0])
        burst_len = int(_pick(rng, [16, 32], [0.60, 0.40], 1)[0])
        ecc_mode = str(_pick(rng, ["OnDie_ECC", "Sideband_ECC", "Disabled"], [0.50, 0.40, 0.10], 1)[0])
        temp_c = round(float(rng.normal(68, 12)), 1)
        volt_vdd = round(float(rng.normal(1100, 35)), 1)

        fail = False
        error_tag = None
        error_msg = None
        comp = "uvm_test_top.env.dfi_agent.mon"

        if freq >= 5600 and volt_vdd < 1080 and rng.random() < 0.84:
            fail = True
            error_tag = "ODT_TIMING_FAULT"
            error_msg = f"DFI write leveling ODT target impedance {odt}ohm failed eye margin check at {freq} MT/s"
            comp = "uvm_test_top.env.dfi_phy_mon"
        elif test == "Refresh_Under_Heavy_Write" and ref_mode == "Normal" and freq >= 4800 and rng.random() < 0.80:
            fail = True
            error_tag = "tRFC_REFRESH_VIOLATION"
            error_msg = f"Bank refresh collision: tRFC=410ns violated under burst write queue pressure"
            comp = "uvm_test_top.env.ddr_protocol_chk"
        elif bank_groups == 8 and burst_len == 32 and test == "Ddr5_Bank_Interleave_Stress" and rng.random() < 0.75:
            fail = True
            error_tag = "BURST_CHIPSELECT_GLITCH"
            error_msg = f"Command collision on CS_n: tCCD_L timing violated across bank group 6 and 7"
            comp = "uvm_test_top.env.ddr_sb"
        elif temp_c > 85 and test == "ODT_Switching_Sweep" and rng.random() < 0.72:
            fail = True
            error_tag = "THERMAL_THROTTLE_ABORT"
            error_msg = f"DRAM junction temp {temp_c}C exceeded maximum operating ceiling (85.0C)"
            comp = "uvm_test_top.env.pmu_mon"
        elif rng.random() < 0.035:
            fail = True
            error_tag = "TRAINING_LOCK_FAIL"
            error_msg = f"CA training locked out after 2048 preamble cycles on channel A"
            comp = "uvm_test_top.env.dfi_agent.mon"

        exec_time_ms = round(float(rng.uniform(180, 520) if not fail else rng.uniform(60, 200)), 2)
        tp_mbps = round(float((freq * 64 / 8) * (0.85 if not fail else 0.25) * rng.uniform(0.9, 1.05)), 2)
        cycles = int(exec_time_ms * (freq / 2) * 1000)

        cfg_obj = {
            "run_id": run_id,
            "design": "SanDisk_DDR5_Memory_Controller_PHY",
            "test_name": test,
            "dram_freq_mhz": freq,
            "cas_latency": cl,
            "refresh_mode": ref_mode,
            "odt_impedance_ohm": odt,
            "bank_groups": bank_groups,
            "burst_length": burst_len,
            "ecc_mode": ecc_mode,
            "temperature_c": temp_c,
            "voltage_vdd_mv": volt_vdd,
        }
        metric_obj = {
            "execution_time_ms": exec_time_ms,
            "throughput_mbps": tp_mbps,
            "sim_cycles": cycles,
        }

        lines.append(RUN_SEPARATOR)
        lines.append(f"{BANNER}{run_id}")
        lines.append(RUN_SEPARATOR)
        lines.append(CONFIG_OPEN)
        lines.append(json.dumps(cfg_obj))
        lines.append(CONFIG_CLOSE)
        lines.append(f"UVM_INFO @ 0 ns: reporter [RNTST] Running test {test}...")
        lines.append(f"UVM_INFO @ 800 ns: uvm_test_top.env.dfi_agent [DFI_INIT] DFI 5.0 PHY phase aligned at {freq} MT/s")

        if fail:
            err_time = int(rng.integers(12000, 95000))
            lines.append(f"UVM_ERROR @ {err_time} ns: {comp} [{error_tag}] {error_msg}")
            lines.append(f"UVM_FATAL @ {err_time + 40} ns: uvm_test_top [TEST_ABORT] DDR5 command sequencer terminated")

        lines.append(METRICS_OPEN)
        lines.append(json.dumps(metric_obj))
        lines.append(METRICS_CLOSE)
        lines.append(SUMMARY_HEADER)
        lines.append(f"UVM_INFO    :   {rng.integers(18, 30)}")
        lines.append(f"UVM_WARNING :   {1 if rng.random() < 0.15 else 0}")
        lines.append(f"UVM_ERROR   :   {1 if fail else 0}")
        lines.append(f"UVM_FATAL   :   {1 if fail else 0}")
        lines.append(VERDICT_FAIL if fail else VERDICT_PASS)
        lines.append("")

    out_file = os.path.join(OUTPUT_DIR, "sandisk_ddr5_memory_controller.log")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated {n_runs} runs: {out_file}")


# ==============================================================================
# 3. DESIGN: SanDisk APB Peripheral Subsystem (Single .log, Single .csv, & Multi-CSV)
# ==============================================================================
def generate_apb_datasets(n_runs=250, seed=303):
    rng = np.random.default_rng(seed)
    bundle_dir = os.path.join(OUTPUT_DIR, "apb_peripheral_csv")
    os.makedirs(bundle_dir, exist_ok=True)

    tests = ["Reg_Sweep", "Uart_Loopback", "Dma_Burst", "Irq_Storm", "Backpressure"]
    configs = []
    outcomes = []
    telemetry = []
    transactions = []
    merged_runs = []
    log_lines = []

    for i in range(1, n_runs + 1):
        run_id = f"RUN-{i:06d}"
        test = str(_pick(rng, tests, [0.25, 0.25, 0.20, 0.15, 0.15], 1)[0])
        baud = int(_pick(rng, [115200, 230400, 460800, 921600], [0.30, 0.25, 0.25, 0.20], 1)[0])
        parity = str(_pick(rng, ["none", "even", "odd"], [0.40, 0.30, 0.30], 1)[0])
        fifo_depth = int(_pick(rng, [4, 8, 16, 32], [0.20, 0.35, 0.30, 0.15], 1)[0])
        dma_en = int(_pick(rng, [0, 1], [0.35, 0.65], 1)[0])
        irq_mode = str(_pick(rng, ["edge", "level"], [0.50, 0.50], 1)[0])
        arb = str(_pick(rng, ["static", "round_robin"], [0.45, 0.55], 1)[0])
        psel_count = int(_pick(rng, [4, 8, 12], [0.30, 0.45, 0.25], 1)[0])
        temp_c = round(float(rng.normal(55, 12)), 1)
        volt_mv = round(float(rng.normal(1200, 30)), 1)

        fail = False
        err_class = "NONE"
        err_code = "OK"
        err_msg = ""
        comp = "uvm_test_top.env.apb_agent.mon"

        if arb == "static" and psel_count >= 8 and rng.random() < 0.80:
            fail = True
            err_class = "BUS_STARVATION"
            err_code = "B_ARB_0x12"
            err_msg = f"Master 2 starved for {rng.integers(600, 3500)} cycles on static priority APB arbiter"
            comp = "uvm_test_top.env.apb_agent.arb_mon"
        elif baud >= 921600 and parity == "none" and rng.random() < 0.78:
            fail = True
            err_class = "FRAMING_ERROR"
            err_code = "B_UART_0x24"
            err_msg = f"UART framing error: stop bit missing at {baud} baud byte=0x{rng.integers(0, 256):02x}"
            comp = "uvm_test_top.env.uart_agent.mon"
        elif dma_en == 1 and fifo_depth <= 8 and rng.random() < 0.72:
            fail = True
            err_class = "FIFO_UNDERRUN"
            err_code = "B_DMA_0x31"
            err_msg = f"DMA stream underrun on channel 0: requested burst exceeds FIFO depth {fifo_depth}"
            comp = "uvm_test_top.env.dma_sb"
        elif rng.random() < 0.04:
            fail = True
            err_class = "ASSERTION_FAIL"
            err_code = "B_ASRT_0x81"
            err_msg = f"Assertion 'a_penable_stable' failed during backpressure phase"
            comp = "uvm_test_top.dut_wrapper"

        exec_ms = round(float(rng.uniform(45, 120) if not fail else rng.uniform(20, 60)), 3)
        tp_mbps = round(float(rng.uniform(35, 95) if not fail else rng.uniform(5, 20)), 2)
        cycles = int(exec_ms * 100 * 1000)

        # 1. Multi-file CSV components
        configs.append({
            "runId": run_id,
            "testcase": test,
            "baud_rate": baud,
            "parity_mode": parity,
            "fifo_depth": fifo_depth,
            "dma_enable": dma_en,
            "irq_mode": irq_mode,
            "arbitration_scheme": arb,
            "psel_count": psel_count,
            "vendor_ip_rev": "r2p1_sandisk",
        })

        outcomes.append({
            "runId": run_id,
            "result": "FAIL" if fail else "PASS",
            "failure_class": err_class,
            "err_code": err_code,
            "exec_time_ms": exec_ms,
            "throughput_mbps": tp_mbps,
            "uvm_error_count": 1 if fail else 0,
        })

        telemetry.append({
            "simulation_id": run_id,
            "temperature_c": temp_c,
            "voltage_mv": volt_mv,
            "power_mode": "low_power" if temp_c < 50 else "nominal",
            "sim_cycles": cycles,
        })

        n_tx = rng.integers(3, 7)
        for tx in range(n_tx):
            is_tx_err = fail and (tx == n_tx - 1)
            transactions.append({
                "Run_ID": run_id,
                "transaction_id": f"TXN_{tx:04d}",
                "addr": f"0x{rng.integers(0, 4096):04x}",
                "data": f"0x{rng.integers(0, 2**32):08x}",
                "latency_cycles": rng.integers(2, 12),
                "checker_result": "MISMATCH" if is_tx_err else "MATCH",
            })

        # 2. Merged Single-File CSV row
        merged_runs.append({
            "run_id": run_id,
            "test_name": test,
            "pass_fail": "fail" if fail else "pass",
            "primary_error_tag": err_class,
            "baud_rate": baud,
            "parity_mode": parity,
            "fifo_depth": fifo_depth,
            "dma_enable": dma_en,
            "irq_mode": irq_mode,
            "arbitration_scheme": arb,
            "psel_count": psel_count,
            "temperature_c": temp_c,
            "voltage_mv": volt_mv,
            "execution_time_ms": exec_ms,
            "throughput_mbps": tp_mbps,
            "sim_cycles": cycles,
        })

        # 3. Single .log representation
        log_cfg = {
            "run_id": run_id,
            "design": "SanDisk_APB_Peripheral_Subsystem",
            "test_name": test,
            "baud_rate": baud,
            "parity_mode": parity,
            "fifo_depth": fifo_depth,
            "dma_enable": dma_en,
            "irq_mode": irq_mode,
            "arbitration_scheme": arb,
            "psel_count": psel_count,
            "temperature_c": temp_c,
            "voltage_mv": volt_mv,
        }
        log_metrics = {
            "execution_time_ms": exec_ms,
            "throughput_mbps": tp_mbps,
            "sim_cycles": cycles,
        }
        log_lines.append(RUN_SEPARATOR)
        log_lines.append(f"{BANNER}{run_id}")
        log_lines.append(RUN_SEPARATOR)
        log_lines.append(CONFIG_OPEN)
        log_lines.append(json.dumps(log_cfg))
        log_lines.append(CONFIG_CLOSE)
        log_lines.append(f"UVM_INFO @ 0 ns: reporter [RNTST] Running test {test}...")
        log_lines.append(f"UVM_INFO @ 500 ns: uvm_test_top.env.apb_agent [APB_INIT] Bus frequency 100 MHz, PSEL count {psel_count}")
        if fail:
            err_time = int(rng.integers(5000, 45000))
            log_lines.append(f"UVM_ERROR @ {err_time} ns: {comp} [{err_class}] {err_msg}")
            log_lines.append(f"UVM_FATAL @ {err_time + 30} ns: uvm_test_top [TEST_ABORT] APB bridge halted on error")
        log_lines.append(METRICS_OPEN)
        log_lines.append(json.dumps(log_metrics))
        log_lines.append(METRICS_CLOSE)
        log_lines.append(SUMMARY_HEADER)
        log_lines.append(f"UVM_INFO    :   {rng.integers(10, 18)}")
        log_lines.append(f"UVM_WARNING :   0")
        log_lines.append(f"UVM_ERROR   :   {1 if fail else 0}")
        log_lines.append(f"UVM_FATAL   :   {1 if fail else 0}")
        log_lines.append(VERDICT_FAIL if fail else VERDICT_PASS)
        log_lines.append("")

    # Write files
    pd.DataFrame(configs).to_csv(os.path.join(bundle_dir, "config.csv"), index=False)
    pd.DataFrame(outcomes).to_csv(os.path.join(bundle_dir, "outcomes.csv"), index=False)
    pd.DataFrame(telemetry).to_csv(os.path.join(bundle_dir, "telemetry.csv"), index=False)
    pd.DataFrame(transactions).to_csv(os.path.join(bundle_dir, "transactions.csv"), index=False)

    merged_csv_path = os.path.join(OUTPUT_DIR, "sandisk_apb_periph_runs.csv")
    pd.DataFrame(merged_runs).to_csv(merged_csv_path, index=False)

    log_path = os.path.join(OUTPUT_DIR, "sandisk_apb_periph.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"Generated APB Multi-CSV ({n_runs} runs): {bundle_dir}")
    print(f"Generated APB Single CSV: {merged_csv_path}")
    print(f"Generated APB Single Log: {log_path}")


# ==============================================================================
# 4. DESIGN: SanDisk UFS 4.0 Mobile Storage Controller (Single .log, Single .csv, Multi-CSV)
# ==============================================================================
def generate_ufs_datasets(n_runs=200, seed=404):
    rng = np.random.default_rng(seed)
    bundle_dir = os.path.join(OUTPUT_DIR, "ufs40_mobile_storage_csv")
    os.makedirs(bundle_dir, exist_ok=True)

    tests = ["Ufs_Gear5_Burst_RW", "UniPro_Link_PowerDown", "RPMB_Auth_Write", "HS_Series_Switch", "Command_Queue_Stress"]
    configs = []
    outcomes = []
    transactions = []
    merged_runs = []
    log_lines = []

    for i in range(1, n_runs + 1):
        run_id = f"RUN-{i:06d}"
        test = str(_pick(rng, tests, [0.30, 0.20, 0.20, 0.15, 0.15], 1)[0])
        mphy_gear = str(_pick(rng, ["GEAR4", "GEAR5"], [0.45, 0.55], 1)[0])
        lanes = int(_pick(rng, [1, 2], [0.35, 0.65], 1)[0])
        hs_series = str(_pick(rng, ["Rate_A", "Rate_B"], [0.50, 0.50], 1)[0])
        qd = int(_pick(rng, [16, 32], [0.40, 0.60], 1)[0])
        rpmb = int(_pick(rng, [0, 1], [0.70, 0.30], 1)[0])

        fail = False
        err_type = "NONE"
        err_code = "0x00"
        err_msg = ""
        comp = "uvm_test_top.env.ufs_agent.mon"

        if mphy_gear == "GEAR5" and hs_series == "Rate_B" and lanes == 2 and rng.random() < 0.75:
            fail = True
            err_type = "MPHY_PLL_UNLOCK"
            err_code = "E_MPHY_0x42"
            err_msg = f"MIPI M-PHY Gear5 Rate_B clock recovery lost lock on lane 1"
            comp = "uvm_test_top.env.mphy_mon"
        elif test == "RPMB_Auth_Write" and rpmb == 0 and rng.random() < 0.85:
            fail = True
            err_type = "RPMB_MAC_MISMATCH"
            err_code = "E_SEC_0x99"
            err_msg = f"RPMB authenticated data frame rejected: SHA-256 MAC signature mismatch"
            comp = "uvm_test_top.env.security_checker"
        elif qd == 32 and mphy_gear == "GEAR5" and test == "Ufs_Gear5_Burst_RW" and rng.random() < 0.70:
            fail = True
            err_type = "HS_BURST_CRC_ERROR"
            err_code = "E_CRC_0x17"
            err_msg = f"UniPro PACP data frame CRC-16 check failed during high-speed burst"
            comp = "uvm_test_top.env.unipro_link_chk"
        elif rng.random() < 0.04:
            fail = True
            err_type = "PA_INIT_TIMEOUT"
            err_code = "E_TMO_0x08"
            err_msg = f"PACount handshake timeout during link powerdown exit sequence"
            comp = "uvm_test_top.env.ufs_agent.mon"

        exec_ms = round(float(rng.uniform(80, 220) if not fail else rng.uniform(30, 90)), 2)
        tp_mbps = round(float(rng.uniform(1800, 4200) if not fail else rng.uniform(250, 800)), 2)
        cycles = int(exec_ms * 400 * 1000)

        # Multi-file CSV tables
        configs.append({
            "run_id": run_id,
            "test_name": test,
            "mphy_gear": mphy_gear,
            "num_lanes": lanes,
            "hs_series": hs_series,
            "cmd_queue_depth": qd,
            "rpmb_enabled": rpmb,
            "unipro_version": "v2.0",
        })

        outcomes.append({
            "run_id": run_id,
            "pass_fail": "fail" if fail else "pass",
            "failure_type": err_type,
            "error_code": err_code,
            "execution_time_ms": exec_ms,
            "throughput_mbps": tp_mbps,
        })

        n_tx = rng.integers(3, 6)
        for tx in range(n_tx):
            is_err = fail and (tx == n_tx - 1)
            transactions.append({
                "run_id": run_id,
                "txn_id": f"PACP_{tx:03d}",
                "pacp_frame_type": "DATA" if tx % 2 == 0 else "CTRL",
                "mphy_lane": tx % lanes,
                "packet_size_bytes": 1024 if tx % 2 == 0 else 64,
                "transfer_latency_ns": rng.integers(80, 400),
                "checker_result": "MISMATCH" if is_err else "PASS",
            })

        # Merged CSV row
        merged_runs.append({
            "run_id": run_id,
            "test_name": test,
            "pass_fail": "fail" if fail else "pass",
            "primary_error_tag": err_type,
            "mphy_gear": mphy_gear,
            "num_lanes": lanes,
            "hs_series": hs_series,
            "cmd_queue_depth": qd,
            "rpmb_enabled": rpmb,
            "unipro_version": "v2.0",
            "execution_time_ms": exec_ms,
            "throughput_mbps": tp_mbps,
            "sim_cycles": cycles,
        })

        # Single .log representation
        log_cfg = {
            "run_id": run_id,
            "design": "SanDisk_UFS40_Mobile_Storage_Controller",
            "test_name": test,
            "mphy_gear": mphy_gear,
            "num_lanes": lanes,
            "hs_series": hs_series,
            "cmd_queue_depth": qd,
            "rpmb_enabled": rpmb,
            "unipro_version": "v2.0",
        }
        log_metrics = {
            "execution_time_ms": exec_ms,
            "throughput_mbps": tp_mbps,
            "sim_cycles": cycles,
        }
        log_lines.append(RUN_SEPARATOR)
        log_lines.append(f"{BANNER}{run_id}")
        log_lines.append(RUN_SEPARATOR)
        log_lines.append(CONFIG_OPEN)
        log_lines.append(json.dumps(log_cfg))
        log_lines.append(CONFIG_CLOSE)
        log_lines.append(f"UVM_INFO @ 0 ns: reporter [RNTST] Running test {test}...")
        log_lines.append(f"UVM_INFO @ 400 ns: uvm_test_top.env.ufs_agent [UFS_READY] UniPro v2.0 established link on {lanes} lane(s) in {mphy_gear}")
        if fail:
            err_time = int(rng.integers(8000, 70000))
            log_lines.append(f"UVM_ERROR @ {err_time} ns: {comp} [{err_type}] {err_msg}")
            log_lines.append(f"UVM_FATAL @ {err_time + 40} ns: uvm_test_top [TEST_ABORT] UFS link reset required")
        log_lines.append(METRICS_OPEN)
        log_lines.append(json.dumps(log_metrics))
        log_lines.append(METRICS_CLOSE)
        log_lines.append(SUMMARY_HEADER)
        log_lines.append(f"UVM_INFO    :   {rng.integers(12, 22)}")
        log_lines.append(f"UVM_WARNING :   0")
        log_lines.append(f"UVM_ERROR   :   {1 if fail else 0}")
        log_lines.append(f"UVM_FATAL   :   {1 if fail else 0}")
        log_lines.append(VERDICT_FAIL if fail else VERDICT_PASS)
        log_lines.append("")

    pd.DataFrame(configs).to_csv(os.path.join(bundle_dir, "config.csv"), index=False)
    pd.DataFrame(outcomes).to_csv(os.path.join(bundle_dir, "outcomes.csv"), index=False)
    pd.DataFrame(transactions).to_csv(os.path.join(bundle_dir, "transactions.csv"), index=False)

    merged_csv_path = os.path.join(OUTPUT_DIR, "sandisk_ufs40_mobile_runs.csv")
    pd.DataFrame(merged_runs).to_csv(merged_csv_path, index=False)

    log_path = os.path.join(OUTPUT_DIR, "sandisk_ufs40_mobile.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"Generated UFS 4.0 Multi-CSV ({n_runs} runs): {bundle_dir}")
    print(f"Generated UFS 4.0 Single CSV: {merged_csv_path}")
    print(f"Generated UFS 4.0 Single Log: {log_path}")


# ==============================================================================
# 5. WAVEFORMS: .fsdb, .vcd, .wlf waveform files
# ==============================================================================
def generate_waveform_files():
    wave_dir = os.path.join(OUTPUT_DIR, "waveforms")
    os.makedirs(wave_dir, exist_ok=True)

    fsdb_path = os.path.join(wave_dir, "RUN-000001.fsdb")
    with open(fsdb_path, "wb") as f:
        f.write(b"\x00FSDB\x01\x00\x00\x00\x02\x00\x00\x00SanDisk_NVMe_AXI_Controller\x00")
        f.write(b"\x00" * 2048)

    vcd_path = os.path.join(wave_dir, "RUN-000002.vcd")
    with open(vcd_path, "w", encoding="utf-8") as f:
        f.write("$date\n   Oct 06, 2026 11:15:00\n$end\n")
        f.write("$version\n   SanDisk Asterix Waveform Generator v1.0\n$end\n")
        f.write("$timescale 1ps $end\n")
        f.write("$scope module tb_top $end\n")
        f.write("$var wire 1 ! clk $end\n")
        f.write("$var wire 1 \" rst_n $end\n")
        f.write("$var wire 64 # axi_awaddr [63:0] $end\n")
        f.write("$var wire 1 $ axi_awvalid $end\n")
        f.write("$var wire 1 % axi_awready $end\n")
        f.write("$upscope $end\n$enddefinitions $end\n")
        f.write("#0\n0!\n0\"\nb0 #\n0$\n0%\n#1000\n1\"\n#2000\n1!\n1$\n")

    wlf_path = os.path.join(wave_dir, "RUN-000003.wlf")
    with open(wlf_path, "wb") as f:
        f.write(b"WLF2\x00\x00\x01\x00ModelSim/QuestaSim WLF File - SanDisk APB\x00")
        f.write(b"\x00" * 1024)

    fsdb_path4 = os.path.join(wave_dir, "RUN-000004.fsdb")
    with open(fsdb_path4, "wb") as f:
        f.write(b"\x00FSDB\x01\x00\x00\x00\x02\x00\x00\x00SanDisk_DDR5_Memory_Controller\x00")
        f.write(b"\x00" * 2048)

    vcd_path5 = os.path.join(wave_dir, "RUN-000005.vcd")
    with open(vcd_path5, "w", encoding="utf-8") as f:
        f.write("$date\n   Oct 06, 2026 11:15:00\n$end\n")
        f.write("$version\n   SanDisk UFS4.0 M-PHY Waveform $end\n")
        f.write("$timescale 1ps $end\n$scope module ufs_top $end\n$var wire 1 ! mphy_tx_clk $end\n$upscope $end\n$enddefinitions $end\n#0\n0!\n#500\n1!\n")

    print(f"Generated 5 waveform files in: {wave_dir}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Generating comprehensive multi-design, multi-format verification logs...")
    generate_nvme_log(n_runs=300, seed=101)
    generate_ddr5_log(n_runs=300, seed=202)
    generate_apb_datasets(n_runs=250, seed=303)
    generate_ufs_datasets(n_runs=200, seed=404)
    generate_waveform_files()
    print("All test samples successfully generated in data/test_samples/")


if __name__ == "__main__":
    main()
