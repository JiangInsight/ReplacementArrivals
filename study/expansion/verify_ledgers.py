







import argparse
import csv
import hashlib
import json
import math
import os
import struct
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
GRAPHS = ("otc", "college", "email", "math", "ubuntu", "higgs", "coin", "comment", "flight")
SMALL = GRAPHS[:6]
SOURCE_GRAPHS = ("college", "email", "math")
CITIES = ("bordeaux", "detroit", "sydney", "winnipeg")
DIRECT = ("incident", "calendar", "tglib", "decremental", "repair", "mix")
ARMS = {
    "direct": DIRECT, "direct128": DIRECT,
    "ablation": ("mix", "global", "allpairs", "without-explicit", "without-direct",
                 "without-catalog", "without-uniform", "without-prune", "without-links"),
    "conditioned": ("mix", "without-prune", "decremental", "repair"),
    "size": ("mix", "without-prune", "decremental", "repair"),
    "scale": ("mix", "dom", "decremental"), "sources": ("mix", "decremental", "repair"),
}
CITY_ARMS = ("mix", "global", "allpairs", "csa")


def require(condition, context):
    if not condition:
        raise ValueError(str(context))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_queries(path):
    return [tuple(map(int, line.split())) for line in path.read_text().splitlines()]


def expected_standard():
    cases = {f"direct-{g}": "direct" for g in GRAPHS}
    cases.update({f"direct128-{g}": "direct128" for g in SMALL})
    cases.update({f"positive-{g}": "conditioned" for g in GRAPHS})
    cases.update({f"size-{g}": "size" for g in GRAPHS})
    cases.update({f"abl-{g}-{c}": "ablation" for g in GRAPHS for c in (0, 2)})
    for g in ("shared1024", "stairs256", "sparse2048", "mixed2048"):
        cases[f"abl-{g}-0"] = "ablation"
    cases.update({f"scale-{g}-{a}-{p}": "scale" for g in ("math", "coin")
                  for a in ("contacts", "vertices") for p in (20, 40, 60, 80, 100)})
    return cases


def verify_sources(cases, cache, input_dir):
    import numpy as np

    sections = {}
    for graph in SOURCE_GRAPHS:
        info = read(input_dir / (graph + ".json"))
        n = info["vertices"]
        samples = np.random.default_rng(5071).choice(n, 100, replace=False)
        graph_cases = [s for s in cases if s["graph"] == graph]
        require(len(graph_cases) == 110, (graph, "source settings"))
        freq = None
        if cache is not None:
            edges = np.memmap(cache / (graph + ".bin"), dtype="<i4", mode="r").reshape(-1, 3)
            require(len(edges) == info["rows"], (graph, "input size"))
            freq = np.bincount(edges[:, 0], minlength=n)
            top = np.lexsort((np.arange(n), -freq))[:10]
        lanes = {}
        for lane, count in (("uniform", 100), ("high", 10)):
            cohort = [s for s in graph_cases if s["sampling"] == lane]
            ids = {s["source"] for s in cohort}
            require(len(cohort) == len(ids) == count, (graph, lane, "source count"))
            if lane == "uniform" or freq is not None:
                expected = samples if lane == "uniform" else top
                require(ids == set(map(int, expected)), (graph, lane, "source IDs"))
            for s in cohort:
                v = s["source"]
                require(s["key"] == f"source-{graph}-{lane}-{v}" and 0 <= v < n,
                        (s["key"], "source identifier"))
                require(s["vertices"] == n and s["release_row"] == 0 and s["requests"] == 32,
                        (s["key"], "source contract"))
                if freq is not None:
                    require(s["outgoing"] == int(freq[v]), (s["key"], "outgoing count"))
            lanes[lane] = ids
        sections[graph] = {"uniform": 100, "high": 10,
                           "overlap": len(lanes["uniform"] & lanes["high"]),
                           "outdegrees_checked_against_contacts": freq is not None}
    require(len(cases) == 330, "source settings outside frozen graph set")
    return sections


def ordered_counts(path):
    data = path.read_bytes()
    off = 0
    counts = []
    while off < len(data):
        n, = struct.unpack_from("<I", data, off)
        off += 4 + 12*n
        require(off <= len(data), (path.name, "truncated answer"))
        counts.append(n)
    return counts


def check_size_grid(s, workload_dir, queries, counts, cache, answer_digest):
    from bisect import bisect_right
    labels = ("1", "2-3", "4-15", "16-63", "64-255", "256+")
    cuts = (2, 4, 16, 64, 256)
    key, graph = s["key"], s["graph"]
    lanes = read(workload_dir / (key+".lanes"))
    require(len(lanes)==len(queries) and counts is not None, (key, "missing size-grid observations"))
    groups = defaultdict(dict)
    for ((event,h), (label,phase), n) in zip(queries,lanes,counts):
        require(label in labels and phase in ("at-contact","midpoint","end") and phase not in groups[event],
                (key,event,"unexpected lane or repeat"))
        groups[event][phase] = (h,n,label)
    drawn = Counter()
    for eid, phases in groups.items():
        require(set(phases)=={"at-contact","midpoint","end"}, (key,eid,"missing deadline"))
        a,b,c = (phases[k] for k in ("at-contact","midpoint","end"))
        require(a[2]==b[2]==c[2]==labels[bisect_right(cuts,c[1])] and c[1]>0,
                (key,eid,"full-roster bin"))
        require(a[0]<=b[0]<=c[0] and b[0]==(a[0]+c[0])//2 and a[1]<=b[1]<=c[1],
                (key,eid,"deadline or row counts"))
        drawn[a[2]] += 1
    populations = s["bin_population"]
    require(len(populations)==6 and [drawn[label] for label in labels]==s["drawn_per_bin"]==
            [min(24,n) for n in populations], (key,"stratum populations"))
    if cache is not None:
        import numpy as np
        packed = np.memmap(cache/(graph+".bin"),dtype="<i4",mode="r").reshape(-1,3)
        baseline = (cache/"census-answers"/f"{graph}-0-end.rows").read_bytes()
        off, pops, selected = 0, [0]*6, {}
        while off<len(baseline):
            eid,n = struct.unpack_from("<ii",baseline,off)
            stop = off+8+12*n
            require(n>0 and stop<=len(baseline), (key,"census format"))
            pops[bisect_right(cuts,n)]+=1
            if eid in groups:
                selected[eid] = list(struct.iter_unpack("<iii",memoryview(baseline)[off+8:stop]))
            off=stop
        require(pops==populations and set(selected)==set(groups), (key,"census population or sample"))
        wire_hash = hashlib.sha256()
        for (eid,h),n in zip(queries,counts):
            require(groups[eid]["at-contact"][0]==int(packed[eid,2]) and
                    groups[eid]["end"][0]==int(packed[-1,2]), (key,eid,"physical timestamp rank"))
            wire_hash.update(struct.pack("<I",n))
            seen=0
            for v,t,alt in selected[eid]:
                if t<=h:
                    wire_hash.update(struct.pack("<iii",v,t,alt if alt<=h else -1))
                    seen+=1
            require(seen==n,(key,eid,h,"census-derived row count"))
        require(wire_hash.hexdigest()==answer_digest,(key,"census-derived row content"))
    return {label:drawn[label] for label in labels}


def check_csv(path, queries, record):
    counts, query_ns, encode_ns, timings = [], 0, 0, []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for j, r in enumerate(csv.DictReader(stream)):
            require(j < len(queries) and int(r["i"]) == j and
                    (int(r["event"]), int(r["deadline"])) == queries[j], (path.name, j, "query"))
            n, q_ns, e_ns = (int(r[k]) for k in ("rows", "query_ns", "encode_ns"))
            require(min(n, q_ns, e_ns) >= 0, (path.name, j, "negative result"))
            counts.append(n)
            query_ns += q_ns
            encode_ns += e_ns
            timings.append(q_ns)
    require(len(counts) == record["requests"] == len(queries) and
            sum(counts) == record["rows"] and sum(n > 0 for n in counts) == record["nonempty"],
            (path.name, "request or output totals"))
    
    
    for k, ns in (("query_s", query_ns), ("encode_s", encode_ns)):
        require(abs(record[k]*1e9 - ns) < 0.5, (path.name, k, ns))
    timings.sort()
    for p in (95, 99):
        h = (len(timings)-1)*p/100
        a, b = timings[math.floor(h)], timings[math.ceil(h)]
        expected = a + (h-math.floor(h))*(b-a)
        require(math.isclose(record[f"p{p}_ns"], expected, rel_tol=1e-10, abs_tol=0.005),
                (path.name, f"p{p}"))
    return counts


def check_status(path, r):
    status = r["status"]
    previous = path.with_name(f"{r['rep']-1}-{r['method']}.json")
    prior = read(previous)["status"] if r["rep"] else None
    if status == "not-repeated-after-timeout":
        require(prior in ("timeout", "not-repeated-after-timeout") and "wall_s" not in r,
                (path, "skipped without a prior timeout"))
    else:
        require(prior in (None, "complete") and r["wall_s"] > 0, (path, "invalid observed run"))
    if status != "complete":
        require(status in ("timeout", "not-repeated-after-timeout") and
                not path.with_suffix(".csv").exists() and
                not ({"rows", "requests", "query_s", "encode_s"} & set(r)),
                (path, "censored run has metrics or CSV"))
    return status


def audit_contact(base, cache, sample):
    out = base / "results/expansion"
    raw, workloads, inputs = out/"runs", out/"workloads", base/"results/full/inputs"
    
    
    available = sorted(raw.glob("*/*.json"))
    if sample:
        available = [p for p in available if p.with_suffix(".csv").is_file()][:sample]
    require(available, "no contact ledgers")
    by_key = defaultdict(list)
    for path in available:
        by_key[path.parent.name].append(path)
    specs, grand, size_grid = [], Counter(), {}
    seen_csv, builds = set(), set()
    by_group = defaultdict(Counter)
    for key, records in by_key.items():
        s = read(workloads / (key+".json"))
        specs.append(s)
        group, g = s["group"], s["graph"]
        qfile = workloads / (key+".txt")
        queries = read_queries(qfile)
        require(key == s["key"] and group in ARMS and digest(qfile) == s["query_sha256"],
                (key, "workload identity"))
        require(len(queries) == s["requests"] and len(set(i for i,h in queries)) == s["distinct_events"],
                (key, "query cardinality"))
        if group != "scale" or s["target_pct"] == 100:
            require(s["input_sha256"] == read(inputs/(g+".json"))["packed_sha256"],
                    (key, "input differs from full input manifest"))
        identities, shared_counts = set(), None
        slots = set()
        for path in records:
            r = read(path)
            m, rep = r["method"], r["rep"]
            require(r["key"] == key and r["group"] == group and m in ARMS[group] and
                    path.name == f"{rep}-{m}.json", (path, "unexpected method/slot"))
            require((rep, m) not in slots, (key, rep, m, "duplicate slot"))
            slots.add((rep, m))
            identity = r["identity"]
            require(identity["input"] == s["input_sha256"] and identity["queries"] == s["query_sha256"],
                    (path, "input/query identity"))
            for name in ("input", "queries", "binary", "answer"):
                require(len(identity[name]) == 64 and int(identity[name], 16) >= 0, (path, "digest", name))
            builds.add(identity["binary"])
            identities.add(identity["answer"])
            status = check_status(path, r)
            grand[status] += 1
            by_group[group][status] += 1
            if status == "complete":
                csv_path = path.with_suffix(".csv")
                counts = check_csv(csv_path, queries, r)
                seen_csv.add(csv_path)
                if shared_counts is None:
                    shared_counts = counts
                require(counts == shared_counts, (key, "different per-request counts"))
                grand["complete_csv_rows"] += len(counts)
                grand["recipient_rows_including_repeats"] += sum(counts)
        require(len(identities) == 1, (key, "different answer hashes"))
        if group == "size":
            size_grid[g] = check_size_grid(s,workloads,queries,shared_counts,cache,next(iter(identities)))
        if group == "conditioned" and shared_counts is not None:
            require(len(queries) == 2000 and sum(n>0 for n in shared_counts) == 1000 and
                    len({q[0] for q,n in zip(queries, shared_counts) if n}) == s["distinct_positive"],
                    (key, "conditioned sample"))
        if cache is not None:
            if group in ("ablation", "direct128"):
                cohort = int(key.split("-")[-1]) if group == "ablation" else 0
                wire = cache/"answers"/f"{g}-{cohort}-{s['query_sha256'][:16]}.rows"
            else:
                wire = cache/"expansion-answers"/(key+".rows")
            require(digest(wire) in identities and
                    (shared_counts is None or ordered_counts(wire) == shared_counts),
                    (key, "reference answer bytes"))
        if not sample:
            reps = 1 if group == "sources" else 3
            require(slots == {(rep,m) for rep in range(reps) for m in ARMS[group]},
                    (key, "incomplete frozen matrix"))
    source_audit = {}
    if not sample:
        standard = expected_standard()
        require({s["key"]: s["group"] for s in specs if s["group"] != "sources"} == standard,
                "standard case matrix differs from protocol")
        source_audit = verify_sources([s for s in specs if s["group"] == "sources"], cache, inputs)
        require({s["key"] for s in specs} == {p.stem for p in workloads.glob("*.json")} ==
                {p.stem for p in workloads.glob("*.txt")}, "orphan workload or missing run directory")
        require({p.stem for p in workloads.glob("*.lanes")} == {"size-"+g for g in GRAPHS},
                "unexpected or missing size-grid lane manifest")
        require(seen_csv == set(raw.glob("*/*.csv")), "extra or missing CSV")
        require(len(builds)==1, "multiple contact executables")
    result = {"cases": len(by_key), "ledger_slots":len(available),
              "observed_processes": grand["complete"]+grand["timeout"],
              "complete":grand["complete"], "timeout":grand["timeout"],
              "skipped_after_timeout":grand["not-repeated-after-timeout"],
              "complete_csv_files":len(seen_csv), "complete_csv_rows":grand["complete_csv_rows"],
              "recipient_rows_including_repeats":grand["recipient_rows_including_repeats"],
              "groups":dict(sorted(by_group.items())), "source_sampling":source_audit,
              "size_grid_distinct_events_by_full_deadline_bin":size_grid,"binaries":sorted(builds)}
    return result


def sparse_city_wire(path, queries):
    data = path.read_bytes()
    off, prev, positive, rows, recovered = 0, -1, 0, 0, 0
    while off < len(data):
        i, n = struct.unpack_from("<ii", data, off)
        end = off+8+12*n
        require(prev < i < queries and n > 0 and end <= len(data), (path.name, "invalid block"))
        for _, _, after in struct.iter_unpack("<iii", memoryview(data)[off+8:end]):
            recovered += after != -1
        positive += 1
        rows += n
        prev, off = i, end
    return positive, rows, recovered


def audit_cities(base, cache):
    out = base / "results/expansion/timetables"
    seen, cases, bins = set(), {}, set()
    for city in CITIES:
        n = read(out/f"{city}-input.json")["rows"]
        for case in range(3):
            spec = read(out/f"{city}-{case}.json")
            qs = out/f"{city}-{case}.txt"
            require(digest(qs) == spec["query_sha256"] and len(read_queries(qs)) == 256, (city,case))
            for suite in (("online","census") if case==0 else ("online",)):
                key = f"{city}-{case}-{suite}"
                signatures = set()
                expected = n if suite=="census" else 256
                for rep in range(1 if suite=="census" else 3):
                    for arm in CITY_ARMS:
                        path = out/"runs"/f"{key}-{rep}-{arm}.json"
                        r = read(path)
                        require((r["city"],r["case"],r["suite"],r["rep"],r["method"],r["requests"])
                                == (city,case,suite,rep,arm,expected), (path, "invalid city run"))
                        require(r["wall_s"]>0 and 0<=r["positive"]<=min(expected,r["rows"]) and
                                0<=r["recovered"]<=r["rows"], (path,"city counts"))
                        bins.add(r["binary"])
                        signatures.add(tuple(r[k] for k in ("sha256","positive","rows","recovered")))
                        seen.add(path)
                require(len(signatures)==1, (key, "city implementations disagree"))
                h, positive, rows, recovered = signatures.pop()
                if cache is not None:
                    wire = cache/"timetable-answers"/(key+".rows")
                    require(h==digest(wire) and (positive,rows,recovered)==sparse_city_wire(wire,expected),
                            (key,"city binary output"))
                if suite=="census":
                    cases[city] = dict(requests=expected,positive=positive,rows=rows,recovered=recovered,sha256=h)
    require(len(bins)==1 and seen==set((out/"runs").glob("*.json")), "city executable or run matrix")
    return {"complete":len(seen), "census":cases, "binary":next(iter(bins))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=BASE)
    ap.add_argument("--cache", type=Path,
                    help="measurement cache for raw answer hashes and sender frequency verification")
    ap.add_argument("--sample", type=int, default=0, help="check this many completed contact runs without writing")
    args = ap.parse_args()
    require(args.sample >= 0, "negative sample")
    cache = args.cache
    if cache is None and os.environ.get("PAPER3_CACHE"):
        cache = Path(os.environ["PAPER3_CACHE"])
    result = {"scope":"sample" if args.sample else "complete frozen matrix",
              "binary_answer_files_checked":cache is not None,
              "contact":audit_contact(args.base,cache,args.sample)}
    if args.sample:
        print(json.dumps(result,indent=2))
        return
    result["timetables"] = audit_cities(args.base,cache)
    path = args.base/"results/expansion/independent-audit.json"
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    pending.replace(path)
    print(path, result["contact"]["complete"], result["timetables"]["complete"])


if __name__ == "__main__":
    main()
