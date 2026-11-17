
import argparse
import csv
import filecmp
import json
import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from prepare import BASE,CACHE,sha

OUT=BASE/"results/full"
METHODS=["scan","tglib","dag","equations","repair","eager","unfiltered","history","pairs"]
DETACHED=["ordered","cascade","adaptive","flatpairs"]
COMPONENT=["mix","global","allpairs"]
DOM=["frontier","dom","domfull"]
GRAPHS=["otc","college","email","math","ubuntu","coin","comment"]
BUDGET=300

def save(path,data):
    temp=path.with_suffix(".pending")
    temp.write_text(json.dumps(data,indent=2)+"\n")
    temp.replace(path)

def trial(graph,cohort,rep,method,exe,exe_hash,scratch):
    name=f"{graph}-{cohort}"
    raw=OUT/"runs"/name
    raw.mkdir(exist_ok=True,parents=True)
    dest=raw/f"{rep}-{method}.json"
    query=OUT/"workloads"/(name+".txt")
    spec=json.loads(query.with_suffix(".json").read_text())
    qsha=sha(query)
    assert qsha==spec["workload_sha256"]
    source=json.loads((OUT/"inputs"/(graph+".json")).read_text())
    identity=dict(binary=exe_hash,workload=qsha,input=source["packed_sha256"])
    if dest.exists():
        record=json.loads(dest.read_text())
        if record["identity"]!=identity:raise ValueError(f"stale run: {dest}")
        return
    log=dest.with_suffix(".csv")
    stem=scratch/"current"
    args=[str(exe),str(CACHE/(graph+".bin")),str(spec["vertices"]),str(spec["source"]),
          str(spec["release_row"]),str(query),method,str(stem),str(scratch/"metrics.json")]
    tick=time.perf_counter()
    try:
        p=subprocess.run(args,capture_output=True,timeout=BUDGET)
    except subprocess.TimeoutExpired:
        save(dest,dict(graph=graph,cohort=cohort,rep=rep,method=method,status="timeout",
                       budget_s=BUDGET,identity=identity))
        print("timeout",name,rep,method,flush=True)
        return
    wall=time.perf_counter()-tick
    if p.returncode: raise RuntimeError([args,p.returncode,p.stderr.decode(errors="replace")])
    wire=stem.with_suffix(".rows")
    digest=sha(wire)
    refs=CACHE/"answers"
    refs.mkdir(exist_ok=True)
    ref=refs/(name+"-"+qsha[:16]+".rows")
    if ref.exists():
        if not filecmp.cmp(wire,ref,shallow=False):raise ValueError(f"answer mismatch: {name} {method}")
    else:
        os.replace(wire,ref)
    entries=list(csv.DictReader(stem.with_suffix(".csv").open()))
    queries=[tuple(map(int,s.split())) for s in query.read_text().splitlines()]
    assert [(int(r["i"]),int(r["event"]),int(r["deadline"])) for r in entries]==[(i,*q) for i,q in enumerate(queries)]
    stats=json.loads((scratch/"metrics.json").read_text())
    stats.update(graph=graph,cohort=cohort,rep=rep,method=method,status="complete",identity=identity,
                 wall_s=wall,answer_sha256=digest,answer_bytes=ref.stat().st_size,requests=len(entries),
                 rows=sum(int(r["rows"]) for r in entries),nonempty=sum(int(r["rows"])>0 for r in entries),
                 query_s=sum(int(r["query_ns"]) for r in entries)*1e-9,
                 encode_s=sum(int(r["encode_ns"]) for r in entries)*1e-9)
    shutil.copyfile(stem.with_suffix(".csv"),log)
    save(dest,stats)
    print(name,rep,method,round(wall,3),stats["rows"],flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--graphs",nargs="+",default=GRAPHS)
    ap.add_argument("--cohorts",nargs="+",type=int,default=[0,1,2,3])
    ap.add_argument("--reps",nargs="+",type=int,default=[0,1,2])
    ap.add_argument("--methods",nargs="+",choices=METHODS+DETACHED+COMPONENT+DOM)
    ap.add_argument("--detached",action="store_true",help="use the source-independent reporting build")
    ap.add_argument("--component",action="store_true",help="use the component-selection build")
    ap.add_argument("--dom",action="store_true",help="use the topological-dominator build")
    args=ap.parse_args()
    exe=CACHE/("dom.exe" if args.dom else "component.exe" if args.component else "release.exe" if args.detached else "study.exe")
    methods=args.methods or (DOM if args.dom else COMPONENT if args.component else DETACHED if args.detached else METHODS)
    exe_hash=sha(exe)
    
    for graph in args.graphs:
        meta=json.loads((OUT/"inputs"/(graph+".json")).read_text())
        assert sha(CACHE/(graph+".bin"))==meta["packed_sha256"]
    with tempfile.TemporaryDirectory(dir=CACHE) as td:
        for graph in args.graphs:
            for cohort in args.cohorts:
                for rep in args.reps:
                    order=list(methods)
                    random.Random(f"temporal/711/{graph}/{cohort}/{rep}").shuffle(order)
                    for method in order:trial(graph,cohort,rep,method,exe,exe_hash,Path(td))

if __name__=="__main__":
    main()

