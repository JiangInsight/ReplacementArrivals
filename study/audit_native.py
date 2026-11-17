





import argparse
from collections import Counter
from hashlib import sha256
from itertools import groupby
import json
from operator import itemgetter
import os
from pathlib import Path
import random
import struct
import subprocess
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
METHODS = ("repair", "scan", "history", "pairs", "eager", "unfiltered", "tglib", "dag", "equations")
CASCADE_METHODS = ("ordered", "cascade", "adaptive", "flatpairs")
COMPONENT_METHODS = ("mix", "global", "allpairs")
SEED = 190341
TRIPLE = struct.Struct("<iii")
COUNT = struct.Struct("<I")


def original_and_replacement_rows(events, source, start, deadline, withdrawn):

    def arrive(skip):
        first = {source: -1}
        for t, contacts in groupby(events, itemgetter(2)):
            if t > deadline:
                break
            discovered = {
                v for u, v, _, i in contacts
                if i >= start and i != skip and u in first and v not in first
            }
            for v in discovered:
                first[v] = t
        return first
    base = arrive(None)
    alternate = arrive(withdrawn)
    return sorted((v, t, alternate.get(v, -1)) for v, t in base.items()
                  if alternate.get(v) != t)


def bundled(cases, rng):
    tagged = []
    offset = 1
    for tag, (vertices, events) in enumerate(cases):
        tagged.append((0, offset, 1, tag))
        tagged.extend((u + offset, v + offset, t + 2, tag) for u, v, t in events)
        offset += vertices
    
    rng.shuffle(tagged)
    tagged.sort(key=itemgetter(2))
    per_case = [[] for _ in cases]
    for i, (u, v, t, tag) in enumerate(tagged):
        per_case[tag].append((u, v, t, i))
    requests = []
    for events in per_case:
        horizons = sorted({0, events[-1][2] + 1, *(e[2] for e in events)})
        for _, _, _, i in events:
            for h in horizons:
                requests.append((i, h, original_and_replacement_rows(events, 0, 0, h, i)))
    rng.shuffle(requests)
    return [(u, v, t) for u, v, t, _ in tagged], offset, 0, 0, requests


def individual(events, n, source, start, rng, sample=False):
    events.sort(key=itemgetter(2))
    numbered = [(*e, i) for i, e in enumerate(events)]
    hs = sorted({0, events[start][2], events[-1][2] + 1, *(t for _, _, t in events)})
    if sample:
        hs = sorted(set(hs[:3] + hs[-3:] + rng.sample(hs, min(4, len(hs)))))
    requests = [(i, h, original_and_replacement_rows(numbered, source, start, h, i))
                for i in range(len(events)) for h in hs]
    rng.shuffle(requests)
    return events, n, source, start, requests


def run_case(root, exe, cohort, task, stats, digest, methods):
    edges, n, source, start, requests = task
    contacts, queries = root / "contacts.bin", root / "queries.txt"
    contacts.write_bytes(b"".join(TRIPLE.pack(*e) for e in edges))
    queries.write_text("".join(f"{i} {h}\n" for i, h, _ in requests))
    expected = bytearray()
    counts = Counter()
    for i, h, rows in requests:
        expected.extend(COUNT.pack(len(rows)))
        for row in rows:
            expected.extend(TRIPLE.pack(*row))
            counts["unrecovered_rows" if row[2] == -1 else "recovered_rows"] += 1
        counts["queries"] += 1
        counts["nonempty_queries"] += bool(rows)
        counts["removed_before_release"] += i < start
        counts["removed_after_deadline"] += edges[i][2] > h
    metrics = {}
    for method in methods:
        stem = root / "actual"
        args = [exe, contacts, str(n), str(source), str(start), queries, method, stem, root / "metrics.json"]
        subprocess.run(args, check=True, capture_output=True)
        metrics[method] = json.loads((root / "metrics.json").read_text())
        observed = stem.with_suffix(".rows").read_bytes()
        if expected != observed:
            pos = 0
            for j, (i, h, rows) in enumerate(requests):
                if pos + COUNT.size > len(observed):
                    raise ValueError((method, cohort, j, "truncated header"))
                size, = COUNT.unpack_from(observed, pos)
                pos += COUNT.size
                actual = list(TRIPLE.iter_unpack(observed[pos:pos + size * TRIPLE.size]))
                pos += size * TRIPLE.size
                if actual != rows:
                    raise ValueError((method, cohort, source, start, i, h, rows[:8], actual[:8]))
            raise ValueError((method, cohort, "trailing bytes"))
    counts["native_input_blocks"] += 1
    stats[cohort].update(counts)
    digest.update(expected)
    return metrics


def cascade_boundaries(rng):
    
    
    
    depth = 96
    stream = [(v, v + 1, v) for v in range(depth)]
    paths = {
        97: [0],
        98: [90, 83, 75, 67, 59, 50, 42, 32, 16, 0],
        99: [],
        100: [90, 84, 75, 68, 59, 51, 42, 31, 15, 0],
        101: [90, 83, 75, 67, 59, 50, 42, 34],   
        102: [90, 83, 75, 67, 59, 50, 42, 33],   
        103: [91, 81, 71, 61, 51, 41, 0],       
    }
    for v, parents in paths.items():
        stream.append((depth, v, v))
        if v == 99:
            stream.append((depth, v, v))
        for j, parent in enumerate(parents):
            stream.append((parent, v, 110 + j))
    
    stream.extend([(0, 104, 9), (104, 105, 21), (105, 104, 25)])
    stream.sort(key=itemgetter(2))
    numbered = [(*contact, i) for i, contact in enumerate(stream)]
    requests = []
    for i, (_, _, t) in enumerate(stream):
        
        
        horizons = sorted({0, t - 1, t, 64, 95, 121, *range(96, 105), *range(109, 121)} - {-1})
        requests.extend((i, h, original_and_replacement_rows(numbered, 0, 0, h, i))
                        for h in horizons)
    rng.shuffle(requests)
    return stream, 106, 0, 0, requests


def component_mix(rng):
    
    
    
    
    stream = [(0,1,2)]
    stream.extend((v,v+1,2+v) for v in range(1,24))
    stream.append((0,25,1))
    stream.extend((v,v+1,2+v-25) for v in range(25,104))
    for j in range(32):
        leaf = 105+j
        stream.append((104,leaf,81+j%4))
        parents = [73,65,57,49,41,33,25,17,9,1] if j<3 else [10]
        for k,depth in enumerate(parents):
            stream.append((24+depth,leaf,90+k))
    
    
    stream.extend([(104,137,84),(104,137,84),(0,138,149)])
    stream.sort(key=itemgetter(2))
    numbered = [(*e,i) for i,e in enumerate(stream)]
    requests = []
    for i,(_,_,t) in enumerate(stream):
        horizons = sorted({0,1,24,80,81,83,84,89,90,94,99,148,149,180,t-1,t})
        requests.extend((i,h,original_and_replacement_rows(numbered,0,0,h,i)) for h in horizons)
    rng.shuffle(requests)
    
    
    copies = rng.choices(requests,k=8192-len(requests))
    requests.extend(copies)
    return stream,139,0,0,requests


def execute(exe, suite):
    rng = random.Random(SEED)
    stats = {key: Counter() for key in ("exhaustive", "random", "targeted", "release")}
    methods = {"base": METHODS, "cascade": CASCADE_METHODS, "component": COMPONENT_METHODS,
               "dom": ("frontier","dom","domfull")}[suite]
    checks = {}
    digest = sha256()
    with TemporaryDirectory(prefix="paper3-native-audit-") as td:
        root = Path(td)
        def check(cohort, task):
            return run_case(root, exe, cohort, task, stats, digest, methods)
        edges = [(u, v, t) for t in (0, 1) for u in range(3) for v in range(3) if u != v]
        for lo in range(0, 1 << len(edges), 64):
            cases = [(3, [e for bit, e in enumerate(edges) if mask & (1 << bit)])
                     for mask in range(lo, lo + 64)]
            check("exhaustive", bundled(cases, rng))
            stats["exhaustive"]["component_inputs"] += len(cases)
        for _ in range(4):
            cases = []
            for _ in range(32):
                n = rng.randint(2, 12)
                stream = [(rng.randrange(n), rng.randrange(n), rng.randrange(8))
                          for _ in range(rng.randint(1, 55))]
                stream.extend(rng.choices(stream, k=3))
                cases.append((n, stream))
            check("random", bundled(cases, rng))
            stats["random"]["component_inputs"] += len(cases)
        
        
        tie = [(0,1,0), (1,2,1), (2,3,1), (0,1,1), (2,3,2), (1,2,2),
               (1,4,1), (0,4,1), (1,4,1), (4,5,2), (3,5,3),
               (1,1,2), (5,0,3), (6,6,3)]
        for trial in range(6):
            rng.shuffle(tie)
            check("targeted", individual(tie.copy(), 7, 0, 0, rng))
        depth = 70
        deep = [(v, v+1, v) for v in range(depth)]
        deep.extend((depth, v, depth) for v in range(depth+1, depth+11))
        deep.extend((v, depth+1, depth*2-v) for v in reversed(range(depth)))
        deep.extend((0, v, depth*2+v) for v in range(1, depth+1))
        check("targeted", individual(deep, depth+11, 0, 0, rng, True))
        
        for source in (0, 2, 6):
            ordered = sorted(tie, key=itemgetter(2))
            for first in sorted({t for _, _, t in ordered})[1:]:
                start = next(i for i, e in enumerate(ordered) if e[2] == first)
                check("release", individual(ordered, 7, source, start, rng))
        if suite == "cascade":
            original_digest = digest.hexdigest()
            stats["cascade_boundaries"] = Counter()
            metrics = check("cascade_boundaries", cascade_boundaries(rng))
            assert metrics["adaptive"]["hard_sites"] == 3
            
            
            assert metrics["adaptive"]["catalog_keys"] > 31
            checks = {"common_oracle_sha256": original_digest,
                      "boundary_counts": {m:{k:metrics[m][k] for k in ("history","hard_sites","catalog_keys")}
                                          for m in methods},
                      "boundary_construction": "Three hard local histories of lengths 11, 11 and 9, a 9-entry depth-span-63 mask, an 8-entry wide short history, a same-time multi-entrance leaf and two distinct source branches."}
        if suite == "component":
            checks["common_oracle_sha256"] = digest.hexdigest()
            stats["component_cascade_boundaries"] = Counter()
            check("component_cascade_boundaries", cascade_boundaries(rng))
            task = component_mix(rng)
            checks["dispatch"] = {}
            for domain in ("dense", "sparse"):
                edges, n, src, start, qs = task
                if domain == "sparse":
                    
                    
                    padding = 32768
                    edges = [(0,0,0)] * padding + edges
                    start = padding
                    qs = [(i + padding,h,answer) for i,h,answer in qs] + [(0,180,[])]
                cohort = "three_encodings_" + domain
                stats[cohort] = Counter()
                observed = check(cohort, (edges,n,src,start,qs))
                assert observed["mix"]["components"] == [1,1,1]
                assert observed["allpairs"]["components"] == [3,0,0]
                assert max(observed["global"]["components"]) == 3
                checks["dispatch"][domain] = {
                    "contacts_in_file": len(edges), "release_record": start, "vertices": n,
                    "requests": len(qs), "max_output_rows": max(len(a) for _,_,a in qs),
                    "policies": {m:{k:observed[m][k] for k in ("components","pairs","index_bytes")}
                                 for m in methods}}
            checks["prefix_requests_checked"] = [1,16,256,4096,8192]
    all_counts = sum(stats.values(), Counter())
    sources = ["audit_native.py", "build.bat", "contact.hpp", "histories.hpp", "study.cpp",
               "dag.hpp", "equations.hpp"]
    if suite in ("cascade","component","dom"):
        sources.extend(["cascade.hpp", "dictionary.hpp"])
    if suite in ("component","dom"):
        sources.append("components.hpp")
    if suite=="dom":
        sources.append("dominator.hpp")
    return {"seed": SEED, "suite": suite, "methods": methods, **checks, "strict_rows_match_for_all_methods": True,
            "exe_sha256": sha256(exe.read_bytes()).hexdigest(),
            "source_sha256": {p.name: sha256(p.read_bytes()).hexdigest()
                              for p in (ROOT/"study"/s for s in sources)},
            "oracle_rows_sha256": digest.hexdigest(),
            "scope": "The 4096 labelled graphs use one fixed source before their first tick. All source roles occur by relabelling. Native launches isolate components through unique super-source contacts. Exhaustive claims apply to these three-vertex, two-tick inputs only.",
            "cohorts": stats, "totals": all_counts,
            "native_query_comparisons": len(methods) * all_counts["queries"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", choices=["base","cascade","component","dom"], default="base")
    ap.add_argument("--exe", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.exe is None:
        name = {"base":"study.exe","cascade":"release.exe","component":"component.exe","dom":"dom.exe"}[args.suite]
        cache=Path(os.environ.get("PAPER3_CACHE",Path(os.environ.get("LOCALAPPDATA","."))/"paper3-temporal-data"))
        args.exe = cache/name
    if args.out is None:
        name = "correctness.json" if args.suite == "base" else args.suite+"-correctness.json"
        args.out = ROOT / "results/full" / name
    result = execute(args.exe.resolve(), args.suite)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["totals"]))
