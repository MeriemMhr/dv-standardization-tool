import yaml, sys, pathlib

base = pathlib.Path("schemas")
clusters = yaml.safe_load(open(base/"thematic_clusters.yaml"))["clusters"]
cluster_ids = {c["id"] for c in clusters}

dvs = yaml.safe_load(open(base/"standard_dv_mapping.yaml"))["dvs"]
unknown = [(d["id"], d["cluster"]) for d in dvs if d["cluster"] not in cluster_ids]

if unknown:
    print("Unknown cluster IDs:", unknown); sys.exit(1)
print("OK: all DVs reference valid clusters")
