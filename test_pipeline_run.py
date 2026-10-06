import glob
from uvm_intel.ingest_multi import parse_files_multi
from uvm_intel.pipeline import run_analysis

files = sorted(glob.glob("data/uvm_logs/*.log"))
print(f"Found {len(files)} log files.")
runs, errors, stats, meta = parse_files_multi(files[:2])
print(f"Parsed {len(runs)} runs, {len(errors)} errors.")

res = run_analysis(runs, errors, stats.as_dict() if hasattr(stats, "as_dict") else stats, enable_recommender=True)

print("\nPipeline Stage Results:")
for s in res.get("stage_log", []):
    print(f"  [{s['status'].upper()}] {s['stage']} ({s.get('seconds', 0)}s)")

recs = res.get("recommendations", {}).get("recommendations", [])
print(f"\nRecommended Configurations Generated: {len(recs)}")
if recs:
    print("Top Recommended Config:")
    print(recs[0])
