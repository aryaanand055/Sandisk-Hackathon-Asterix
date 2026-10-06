#!/usr/bin/env python3
"""
Synthetic UVM log & FSDB waveform generator for SanDisk Enterprise NVMe SSD Controller Core.

Generates simulation runs (.log) with NVMe/PCIe parameter spaces and embedded failure rules,
as well as corresponding waveform stub files (.fsdb) for waveform integration testing.

Usage:
    python -m uvm_intel.generate_nvme_logs --n-runs 1000 --output-dir data/nvme_logs
"""

import argparse
import json
import os
import random
import numpy as np

# UVM Log formatting templates
BANNER = "================================================================\nUVM SIMULATION LOG :: "
RUN_SEP = "================================================================"

TEST_NAMES = [
    "NVMe_Sequential_Read", "NVMe_Random_4K_Write", "NVMe_Flush_Cache",
    "NVMe_Deallocate_Trim", "NVMe_Thermal_Throttle_Stress", "NVMe_Power_State_Transition",
    "NVMe_FDP_Placement_Test", "PCIe_Link_Retrain_Stress"
]

CONFIG_SPACE = {
    "test_name": (TEST_NAMES, [0.18, 0.18, 0.14, 0.12, 0.12, 0.10, 0.08, 0.08]),
    "pcie_gen_speed": (["Gen3_8GTs", "Gen4_16GTs", "Gen5_32GTs"], [0.20, 0.40, 0.40]),
    "pcie_lanes": ([1, 2, 4], [0.15, 0.35, 0.50]),
    "nvme_queue_depth": ([16, 64, 256, 1024, 4096], [0.10, 0.20, 0.35, 0.25, 0.10]),
    "lba_format_bytes": ([512, 4096], [0.30, 0.70]),
    "ftl_wear_leveling": (["Dynamic", "Static", "Aggressive", "Disabled"], [0.35, 0.35, 0.20, 0.10]),
    "hmb_enabled": ([0, 1], [0.25, 0.75]),
    "power_state": (["PS0_MaxPerformance", "PS1_Balanced", "PS2_LowPower", "PS3_ThermalThrottle"], [0.45, 0.30, 0.15, 0.10]),
}

def generate_nvme_corpus(n_runs: int = 1000, output_dir: str = "data/nvme_logs", generate_fsdb: bool = True):
    os.makedirs(output_dir, exist_ok=True)
    log_file_path = os.path.join(output_dir, "sandisk_nvme_ssd_runs.log")
    
    np.random.seed(42)
    
    with open(log_file_path, "w", encoding="utf-8") as f_log:
        for i in range(1, n_runs + 1):
            run_id = f"RUN-NVME-{i:06d}"
            seed = random.randint(10000000, 99999999)
            
            test_name = np.random.choice(CONFIG_SPACE["test_name"][0], p=CONFIG_SPACE["test_name"][1])
            pcie_gen = np.random.choice(CONFIG_SPACE["pcie_gen_speed"][0], p=CONFIG_SPACE["pcie_gen_speed"][1])
            pcie_lanes = int(np.random.choice(CONFIG_SPACE["pcie_lanes"][0], p=CONFIG_SPACE["pcie_lanes"][1]))
            qd = int(np.random.choice(CONFIG_SPACE["nvme_queue_depth"][0], p=CONFIG_SPACE["nvme_queue_depth"][1]))
            lba_size = int(np.random.choice(CONFIG_SPACE["lba_format_bytes"][0], p=CONFIG_SPACE["lba_format_bytes"][1]))
            ftl_mode = np.random.choice(CONFIG_SPACE["ftl_wear_leveling"][0], p=CONFIG_SPACE["ftl_wear_leveling"][1])
            hmb = int(np.random.choice(CONFIG_SPACE["hmb_enabled"][0], p=CONFIG_SPACE["hmb_enabled"][1]))
            power_state = np.random.choice(CONFIG_SPACE["power_state"][0], p=CONFIG_SPACE["power_state"][1])
            
            voltage_mv = round(float(np.random.uniform(1050.0, 1300.0)), 1)
            temp_c = round(float(np.random.uniform(30.0, 105.0)), 1)
            
            cfg = {
                "run_id": run_id,
                "test_name": test_name,
                "pcie_gen_speed": pcie_gen,
                "pcie_lanes": pcie_lanes,
                "nvme_queue_depth": qd,
                "lba_format_bytes": lba_size,
                "ftl_wear_leveling": ftl_mode,
                "hmb_enabled": hmb,
                "power_state": power_state,
                "voltage_mv": voltage_mv,
                "temperature_c": temp_c,
                "seed": seed
            }
            
            # Rule injection logic for NVMe Controller Bugs
            fail_prob = 0.015
            err_tag = None
            err_msg = ""
            err_comp = "uvm_test_top.env.nvme_agent"
            
            # Rule 1: PCIe Gen5 + 4096 Queue Depth + HMB Disabled -> NVME_COMMAND_TIMEOUT
            if pcie_gen == "Gen5_32GTs" and qd >= 4096 and hmb == 0:
                fail_prob = 0.85
                err_tag = "NVME_COMMAND_TIMEOUT"
                err_msg = f"NVMe Submission Queue {qd} starved host memory buffer (HMB=0) at address 0x{seed:08x}"
                err_comp = "uvm_test_top.env.nvme_sub_queue"
                
            # Rule 2: Temp > 95C + Aggressive FTL Wear Leveling -> NAND_RETENTION_CORRUPTION
            elif temp_c > 95.0 and ftl_mode == "Aggressive":
                fail_prob = 0.75
                err_tag = "NAND_RETENTION_CORRUPTION"
                err_msg = f"NAND die junction temperature {temp_c}C caused block erase retention failure"
                err_comp = "uvm_test_top.env.ftl_engine"
                
            # Rule 3: PS3_ThermalThrottle + PCIe_Link_Retrain_Stress -> PCIE_AER_PROTOCOL_ERROR
            elif power_state == "PS3_ThermalThrottle" and test_name == "PCIe_Link_Retrain_Stress":
                fail_prob = 0.90
                err_tag = "PCIE_AER_PROTOCOL_ERROR"
                err_msg = "PCIe Advanced Error Reporting: Link retrain framing error during power transition"
                err_comp = "uvm_test_top.env.pcie_phy"

            is_fail = np.random.rand() < fail_prob
            
            # Write run log block
            f_log.write(f"{RUN_SEP}\n")
            f_log.write(f"UVM SIMULATION LOG :: {run_id}\n")
            f_log.write(f"{RUN_SEP}\n")
            f_log.write("[CONFIG]\n")
            f_log.write(json.dumps(cfg) + "\n")
            f_log.write("[/CONFIG]\n")
            f_log.write(f"UVM_INFO @ 0 ns: reporter [RNTST] Running {test_name}...\n")
            f_log.write(f"UVM_INFO @ 500 ns: uvm_test_top.env [BUILD] PCIe={pcie_gen} QD={qd} FTL={ftl_mode}\n")
            
            if is_fail:
                time_ns = random.randint(10000, 500000)
                tag = err_tag or "NVME_INTERNAL_ERROR"
                msg = err_msg or f"Controller state machine deadlock at cycle 0x{seed:08x}"
                f_log.write(f"UVM_ERROR @ {time_ns} ns: {err_comp} [{tag}] {msg}\n")
                f_log.write(f"UVM_FATAL @ {time_ns + 50} ns: uvm_test_top [TEST_ABORT] Test sequence terminated\n")
            else:
                f_log.write("UVM_INFO @ 450000 ns: uvm_test_top.env.sb [SB_OK] All NVMe completion queue entries verified\n")
                
            exec_time = round(random.uniform(50.0, 600.0), 2)
            throughput = round(random.uniform(1500.0, 7200.0), 2)
            cycles = int(exec_time * 100000)
            
            metrics = {
                "execution_time_ms": exec_time,
                "throughput_mbps": throughput,
                "cycles": cycles,
                "uvm_error_count": 1 if is_fail else 0,
                "uvm_fatal_count": 1 if is_fail else 0
            }
            f_log.write("[METRICS]\n")
            f_log.write(json.dumps(metrics) + "\n")
            f_log.write("[/METRICS]\n")
            f_log.write("--- UVM Report Summary ---\n")
            f_log.write(f"UVM_INFO    :    {3 if not is_fail else 2}\n")
            f_log.write("UVM_WARNING :    0\n")
            f_log.write(f"UVM_ERROR   :    {1 if is_fail else 0}\n")
            f_log.write(f"UVM_FATAL   :    {1 if is_fail else 0}\n")
            f_log.write(f"{'** TEST FAILED **' if is_fail else '** TEST PASSED **'}\n\n")
            
            # Optionally generate FSDB file stub
            if generate_fsdb and i <= 20: # Create FSDB stub files for first 20 runs
                fsdb_path = os.path.join(output_dir, f"{run_id}.fsdb")
                with open(fsdb_path, "wb") as f_fsdb:
                    # Write FSDB binary header signature
                    f_fsdb.write(b"$FSDB-VERDI-V2.0\x00\x01\x00\x00")
                    f_fsdb.write(f"// Synopsys Verdi Waveform Database for SanDisk NVMe {run_id}\n".encode("utf-8"))
                    f_fsdb.write(f"// Scope: uvm_test_top.env.nvme_agent\n".encode("utf-8"))

    print(f"[OK] Generated {n_runs} NVMe simulation logs in: {log_file_path}")
    if generate_fsdb:
        print(f"[OK] Generated FSDB waveform files (.fsdb) in: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-runs", type=int, default=1000)
    parser.add_argument("--output-dir", type=str, default="data/nvme_logs")
    args = parser.parse_args()
    generate_nvme_corpus(args.n_runs, args.output_dir)
