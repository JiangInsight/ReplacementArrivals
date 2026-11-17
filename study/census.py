
import filecmp
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from prepare import BASE,CACHE,sha
from run import GRAPHS,save

OUT=BASE/"results/full"
ARMS=["adaptive","dag","repair","flatpairs"]

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--graphs",nargs="+",default=GRAPHS)
    ap.add_argument("--mix",action="store_true")
    args=ap.parse_args()
    dest=OUT/"census";dest.mkdir(parents=True,exist_ok=True)
    refs=CACHE/"census-answers";refs.mkdir(exist_ok=True)
    exe=CACHE/("all-events.exe" if args.mix else "census.exe");exe_hash=sha(exe)
    with tempfile.TemporaryDirectory(dir=CACHE) as folder:
        path=Path(folder)/"answers.bin"
        for graph in args.graphs:
            for cohort in (0,2):
                spec=json.loads((OUT/"workloads"/f"{graph}-{cohort}.json").read_text())
                assert spec["release_row"]==0
                for h in ("half","end"):
                    index=(spec["total_rows"]-1)//(2 if h=="half" else 1)
                    name=f"{graph}-{cohort}-{h}"
                    ref=refs/(name+".rows")
                    for method in (["mix"] if args.mix else ARMS):
                        record=dest/f"{name}-{method}.json"
                        if record.exists():
                            assert json.loads(record.read_text())["binary"]==exe_hash
                            continue
                        command=[exe,CACHE/(graph+".bin"),str(spec["vertices"]),str(spec["source"]),
                              str(index),method,path]
                        tick=time.perf_counter()
                        measured=subprocess.run(command,capture_output=True,check=True,text=True)
                        wall=time.perf_counter()-tick
                        data=json.loads(measured.stdout)
                        if ref.exists():
                            if not filecmp.cmp(path,ref,shallow=False):raise ValueError([name,method])
                        else:os.replace(path,ref)
                        assert ref.stat().st_size==data["positive"]*8+data["rows"]*12
                        data.update(graph=graph,cohort=cohort,horizon=h,source=spec["source"],method=method,
                                    binary=exe_hash,wall_s=wall,sha256=sha(ref))
                        save(record,data)
                        print(name,method,data["eligible"],data["rows"],round(wall,2),flush=True)

if __name__=="__main__":main()

