import yaml
import sys
import pathlib

# Base path for schema files
base = pathlib.Path("schemas")

# Load clusters
with open(base / "thematic_clusters.yaml", "r") as f:
    clusters = yaml.safe_load(f)["clusters"]
cluster_ids = {c["id"] for c in clusters}

# Load DVs
with open(base / "standard_dv_mapping.yaml", "r") as f:
    dvs = yaml.safe_load(f)["dvs"]

# Validate
unknown = [(d["id"], d["cluster"]) for d in dvs if d["cluster"] not in cluster_ids]

if unknown:
    print("❌ Unknown cluster IDs found:")
    for dv_id, cluster in unknown:
        print(f"  DV: {dv_id} → Invalid cluster: {cluster}")
    sys.exit(1)
else:
    print("All DVs reference valid clusters")
    sys.exit(0)
