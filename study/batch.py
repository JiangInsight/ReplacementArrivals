
import filecmp
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from prepare import CACHE,sha
from run import OUT,save

def main():
    executable=CACHE/"batch.exe"
    dest=OUT/"batch";dest.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=CACHE) as td:
        wire=Path(td)/"transcript.rows"
        for graph in ["otc","college","email","math","higgs","ubuntu","coin","comment","flight"]:
            for cohort in range(7 if graph in ["math","coin","flight"] else 4):
                name=f"{graph}-{cohort}";q=OUT/"workloads"/(name+".txt");s=json.loads(q.with_suffix(".json").read_text())
                source=json.loads((OUT/"runs"/name/"0-mix.json").read_text())
                ref=CACHE/"answers"/(name+"-"+s["workload_sha256"][:16]+".rows")
                for rep in range(3):
                    out=dest/f"{name}-{rep}.json"
                    if out.exists():continue
                    tick=time.perf_counter()
                    run=subprocess.run([executable,CACHE/(graph+".bin"),str(s["vertices"]),str(s["source"]),
                        str(s["release_row"]),q,wire],capture_output=True,text=True,check=True)
                    elapsed=time.perf_counter()-tick
                    assert filecmp.cmp(ref,wire,shallow=False)
                    r=json.loads(run.stdout)
                    r.update(graph=graph,cohort=cohort,rep=rep,wall_s=elapsed,requests=source["requests"],
                             rows=source["rows"],answer_sha256=source["answer_sha256"],binary=sha(executable))
                    save(out,r);print(name,rep,r["passes"],round(elapsed,3),flush=True)
if __name__=="__main__":main()

