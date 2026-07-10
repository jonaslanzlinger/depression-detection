"""Cohort comparison against a SHARED reference baseline.

The pipeline auto-computes a per-user baseline once a user is past the learning period, so
each user is z-scored against themselves -> scores ~0 and cohorts are not comparable. For
a real "depressed vs healthy" check, both cohorts must be scored against ONE baseline: the
healthy cohort's distribution. This script:

  1. computes a baseline from the healthy cohort's raw_metrics,
  2. writes it as the (computed_from_data) baseline for BOTH users, so the analysis layer's
     maybe_compute_baseline finds it and does not overwrite with a per-user one,
  3. re-runs analyze + derive for both,
  4. prints the indicator scores side by side (expect depressed > healthy).

Run after the stack is up and both cohorts have been ingested + aggregated/contextualized.
Requires the analysis layer on PYTHONPATH (for compute_baseline_partitions).

Usage:
    PYTHONPATH=analysis_layer python scripts/cohort_compare.py \
        --depressed 900001 --healthy 900002 \
        --mongo mongodb://localhost:27017 --db iotsensing_dataset \
        --analysis http://localhost:8083
"""
import argparse
from datetime import datetime, timezone

import requests
from pymongo import MongoClient

from core.services.compute_baseline import compute_baseline_partitions


def _raw(coll, uid):
    return list(coll.find({"user_id": uid}, {"_id": 0, "metric_name": 1, "metric_value": 1, "timestamp": 1}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depressed", type=int, required=True)
    ap.add_argument("--healthy", type=int, required=True)
    ap.add_argument("--mongo", default="mongodb://localhost:27017")
    ap.add_argument("--db", default="iotsensing_dataset")
    ap.add_argument("--analysis", default="http://localhost:8083")
    ap.add_argument("--min-samples", type=int, default=5)
    args = ap.parse_args()

    db = MongoClient(args.mongo)[args.db]
    raw, base, scores = db["raw_metrics"], db["baseline"], db["indicator_scores"]

    # 1. shared reference baseline = the healthy cohort's distribution
    partitions = compute_baseline_partitions(_raw(raw, args.healthy), min_samples=args.min_samples)
    n_metrics = len(partitions.get("general", {}).get("metrics", {}))
    print(f"shared baseline computed from healthy cohort {args.healthy}: {n_metrics} metrics")

    # 2. write it for BOTH users (source=computed_from_data => maybe_compute_baseline skips)
    base.delete_many({"user_id": {"$in": [args.depressed, args.healthy]}})
    for uid in (args.depressed, args.healthy):
        base.insert_one({
            "user_id": uid,
            "timestamp": datetime.now(timezone.utc),
            "schema_version": 2,
            "source": "computed_from_data",
            "context_partitions": partitions,
            "system_mode": "dataset",
        })

    # 3. clear + re-run analyze/derive for both
    for coll in ("analyzed_metrics", "indicator_scores"):
        db[coll].delete_many({"user_id": {"$in": [args.depressed, args.healthy]}})
    for uid in (args.depressed, args.healthy):
        requests.get(f"{args.analysis}/analyze_metrics", params={"user_id": uid}, timeout=120)
        requests.get(f"{args.analysis}/derive_indicator_scores", params={"user_id": uid}, timeout=120)

    # 4. compare latest scores
    def latest(uid):
        docs = list(scores.find({"user_id": uid}).sort("timestamp", -1).limit(1))
        return docs[0] if docs else None

    d, h = latest(args.depressed), latest(args.healthy)
    if not d or not h:
        print("ERROR: no scores produced"); return
    keys = sorted(d["indicator_scores"])
    print(f"\n{'indicator':<48}{'depressed':>10}{'healthy':>10}{'  diff':>8}")
    dsum = hsum = 0.0
    for k in keys:
        dv = d["indicator_scores"].get(k) or 0.0
        hv = h["indicator_scores"].get(k) or 0.0
        dsum += dv; hsum += hv
        mark = "  <--" if dv > hv + 1e-6 else ""
        print(f"{k:<48}{dv:>10.3f}{hv:>10.3f}{dv-hv:>8.3f}{mark}")
    print(f"{'SUM':<48}{dsum:>10.3f}{hsum:>10.3f}{dsum-hsum:>8.3f}")
    print(f"\nmdd_signal: depressed={d.get('mdd_signal')} healthy={h.get('mdd_signal')}")
    print("RESULT:", "PASS (depressed > healthy)" if dsum > hsum else "INCONCLUSIVE (depressed <= healthy)")


if __name__ == "__main__":
    main()
