



import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


GRAPHS = ("math", "coin", "flight")
SEEDS = (17, 91, 2027)
METHODS = ("mix", "allpairs", "repair")


def quantile99(observations):
    return sorted(observations)[(99 * (len(observations) - 1) + 99) // 100]


def bucket(q):
    for upper, label in [(0, "0"), (1, "1"), (15, "2-15"), (255, "16-255"),
                         (4095, "256-4095"), (float("inf"), "4096+")]:
        if q <= upper:
            return label


def read_json(path):
    return json.loads(path.read_text())


def read_ledger(directory, repeat, method):
    path = directory / f"{repeat}-{method}.csv"
    with path.open(newline="") as stream:
        records = [{key: int(value) for key, value in row.items()}
                   for row in csv.DictReader(stream)]
    native = read_json(path.with_suffix(".json"))
    assert len(records) == native["requests"] == 2048
    assert sum(row["rows"] for row in records) == native["rows"]
    assert [r["i"] for r in records] == list(range(len(records)))
    for clock in ("query", "encode"):
        ns = sum(r[clock + "_ns"] for r in records)
        assert abs(ns - native[clock + "_s"] * 1e9) < 0.1
    ids = tuple((r["event"], r["deadline"], r["rows"]) for r in records)
    return records, (ids, native["answer_sha256"], native["identity"]["input"],
                     native["identity"]["workload"])


def analyze(results):
    response = {}
    histogram = Counter()
    totals = defaultdict(lambda: defaultdict(Counter))
    bin_counts = defaultdict(Counter)
    for g in GRAPHS:
        for c, seed in enumerate(SEEDS, 4):
            name = f"{g}-{seed}"
            folder = results / "full" / "runs" / f"{g}-{c}"
            times = {}
            ident = None
            for rep in range(3):
                for m in METHODS:
                    records, key = read_ledger(folder, rep, m)
                    if ident is None:
                        ident = key
                    assert ident == key
                    times[rep, m] = [r["query_ns"] for r in records]
                    for rec in records:
                        q, ns = rec["rows"], rec["query_ns"]
                        b = bucket(q)
                        totals[b][rep][m] += ns
                        if m == "mix":
                            histogram[ns] += 1
                            if rep == 0:
                                bin_counts[b]["queries"] += 1
                                bin_counts[b]["rows"] += q
            ids = ident[0]
            pos = [i for i, (_, _, q) in enumerate(ids) if q]
            pct = [quantile99([times[rep, "mix"][i] for i in pos]) for rep in range(3)]
            threshold = median(pct)
            ties = [(rep, i) for rep in range(3) if pct[rep] == threshold
                    for i in pos if times[rep, "mix"][i] == threshold]
            response[name] = {
                "positive": len(pos),
                "p99_ns": threshold,
                "rank_matches": len(ties),
                "rank_match_details": [
                    {"rep": rep, "ordinal": i, "q": ids[i][2],
                     "index_ns_across_repeats": [times[k, "mix"][i] for k in range(3)]}
                    for rep, i in ties],
                "index_p99_by_rep_ns": pct,
                "q_range": [min(ids[i][2] for rep, i in ties),
                            max(ids[i][2] for rep, i in ties)],
                "median_matched_ns": {m: median(times[rep, m][i] for rep, i in ties)
                                      for m in METHODS},
                "own_p99_ns": {m: median(quantile99([times[rep, m][i] for i in pos])
                                         for rep in range(3)) for m in METHODS},
                "roster_q99": quantile99([ids[i][2] for i in pos]),
            }
    bins = {}
    for b, counts in bin_counts.items():
        ns = {m: median(totals[b][rep][m] for rep in range(3)) for m in METHODS}
        bins[b] = {**counts,
                   "ns_per_request": {m: t/counts["queries"] for m, t in ns.items()},
                   "ns_per_row": {m: t/counts["rows"] for m, t in ns.items()}
                   if counts["rows"] else None}
    endpoint = {}
    fingerprints = set()
    for variant in ("contacts", "vertices"):
        key = f"scale-coin-{variant}-100"
        spec = read_json(results / "expansion" / "workloads" / (key + ".json"))
        vals = []
        for rep in range(3):
            r = read_json(results / "expansion" / "runs" / key / f"{rep}-mix.json")
            fingerprints.add((r["identity"]["input"], r["identity"]["queries"],
                              r["identity"]["binary"], r["identity"]["answer"],
                              spec["source"], spec["release_row"]))
            vals.append(r["build_s"])
        endpoint[variant] = vals
    assert len(fingerprints) == 1
    return {"tail": response, "bins": bins, "clock_observations": {
        "index_queries_including_repeats": sum(histogram.values()),
        "zero_intervals": histogram[0], "gcd_ns": math.gcd(*histogram.keys()),
        "minimum_positive_ns": min(t for t in histogram if t > 0)},
        "coin_full_build_s": endpoint}


def follow_up(measurements, results):
    meta = read_json(measurements)
    orig = read_json(results/"expansion/runs/scale-coin-contacts-100/0-mix.json")
    assert meta["original_identity"] == orig["identity"]
    orders = [tuple(p["order"]) for p in meta["pairs"]]
    assert Counter(orders) == {("contacts", "vertices"): 4, ("vertices", "contacts"): 4}
    by_label = defaultdict(list)
    ratios = []
    for pair in meta["pairs"]:
        assert [t["label"] for t in pair["trials"]] == pair["order"]
        t = {r["label"]: r["build_s"] for r in pair["trials"]}
        ratios.append(t["vertices"] / t["contacts"])
        for key, seconds in t.items():
            by_label[key].append(seconds)
    medians = {key: median(values) for key, values in by_label.items()}
    assert len(meta["clock"]) == 3 and all(s["n"] == 1000000 for s in meta["clock"])
    return {"clock": meta["clock"], "median_build_s": medians,
            "ratio_of_medians": medians["vertices"] / medians["contacts"],
            "paired_median_ratio": median(ratios),
            "paired_range": [min(ratios), max(ratios)],
            "pairs_favoring_vertex_label": sum(r < 1 for r in ratios)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--measurements", type=Path,
                        default=Path(__file__).with_name("latency_measurements.json"))
    args = parser.parse_args()
    output = analyze(args.results)
    if args.measurements.exists():
        output["follow_up"] = follow_up(args.measurements, args.results)
    print(json.dumps(output, indent=2))
