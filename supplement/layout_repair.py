
import argparse,csv,os,subprocess
from pathlib import Path
from layout_audit import BASE,CACHE,GRAPHS,HERE,OUT,STUDY,WORK,metadata,sha,save,write

RAW=OUT/"repair-peak-runs.csv"
def measure():
    checkout=Path(os.environ.get("PAPER3_TGLIB",HERE.parent/"vendor/tglib"))
    assert (checkout/"tglib_cpp/src/algorithms/TemporalDistances.h").exists()
    executable=WORK/"memory-controls.exe"
    subprocess.run([STUDY/"build.bat",checkout,executable,HERE/"layout_repair.cpp"],check=True)
    save(dict(binary=sha(executable),driver=sha(HERE/"layout_repair.cpp"),contact=sha(STUDY/"contact.hpp"),
              decremental=sha(STUDY/"expansion/baselines.hpp"),tglib_distances=sha(checkout/"tglib_cpp/src/algorithms/TemporalDistances.h")),
         OUT/"repair-build.json")
    names="witness_live witness_capacity adjacency_live adjacency_capacity state_live state_capacity header input_live input_capacity input_header prebuild_peak construction_peak logical allocated".split()
    rows=[]
    for g in GRAPHS:
        for c in range(4):
            p,n,s,start,digest=metadata(g,c)
            if c==0:assert sha(p)==digest
            for method in ["repair","decremental"]:
                run=subprocess.run([executable,p,str(n),str(s),str(start),method],text=True,capture_output=True,check=True)
                values=list(map(int,run.stdout.split()));assert len(values)==len(names)
                r=dict(graph=g,cohort=c,source=s,method=method,input_sha256=digest,**dict(zip(names,values)))
                assert r["logical"]==r["witness_live"]+r["adjacency_live"]+r["state_live"]
                assert r["allocated"]==r["witness_capacity"]+r["adjacency_capacity"]+r["state_capacity"]
                assert r["input_live"]==r["input_capacity"]==p.stat().st_size
                assert r["construction_peak"]>=r["prebuild_peak"] and r["allocated"]>=r["logical"]
                rows.append(r)
        print(g,flush=True)
    write(rows,RAW)
def tables():
    def get(p):
        with p.open(newline="",encoding="utf8") as f:return list(csv.DictReader(f))
    out=[]
    def add(g,c,src,family,method,live,alloc,dictionary,header,input_size,prebuild,peak):
        n=sum([int(alloc),int(dictionary or 0),int(header)])
        out.append(dict(graph=g,cohort=c,source=src,family=family,method=method,
            occupied_representation_buffers=live,allocated_representation_buffers=alloc,
            dictionary_capacity=dictionary,service_object_header=header,owned_retained=n,
            service_input_including_header=input_size,owned_plus_service_input=n+int(input_size),
            prebuild_process_peak=prebuild,construction_process_peak=peak))
    for r in get(OUT/"memory.csv"):
        if not r["construction_peak"] or r["family"] not in ("contact","scheduled"):continue
        add(r["graph"],r["cohort"],r["source"],r["family"],r["policy"],r["logical_payload"],r["capacity_buffers"],
            r["dictionary_bytes"],r["header_bytes"],0,r["prebuild_peak"],r["construction_peak"])
        assert out[-1]["owned_retained"]==int(r["retained"])
    for r in get(RAW):
        size=int(r["input_capacity"])+int(r["input_header"])
        add(r["graph"],r["cohort"],r["source"],"contact",r["method"],r["logical"],r["allocated"],"",
            r["header"],size,r["prebuild_peak"],r["construction_peak"])
    assert len(out)==243 and len({(x["graph"],x["cohort"],x["method"]) for x in out})==243
    write(out,OUT/"cross-method-memory.csv")
if __name__=="__main__":
    cli=argparse.ArgumentParser();cli.add_argument("--measure",action="store_true");flags=cli.parse_args()
    if flags.measure:measure()
    tables()

