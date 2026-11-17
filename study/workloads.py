
import json
from pathlib import Path
import numpy as np
from numba import njit
from prepare import BASE,CACHE,FILES,TGB,sha

OUT=BASE/"results/full"
@njit
def witnesses(edges,n,src,start):
    first=np.full(n,2147483647,np.int32)
    first[src]=-1
    via=np.full(n,-1,np.int32)
    for i in range(start,len(edges)):
        u,v,t=edges[i]
        if first[u]<t and first[v]==2147483647:
            first[v]=t;via[v]=i
    return via

def make(name,extended=False):
    meta=json.loads((OUT/"inputs"/(name+".json")).read_text())
    n=meta["vertices"]
    edges=np.memmap(CACHE/(name+".bin"),dtype="<i4",mode="r").reshape(-1,3)
    cases=[(.75,0,17),(.75,0,91),(.75,0,2027)] if extended else [(0,0,711),(.5,0,2027),(.75,0,9409),(.5,.5,5113)]
    for cohort,(fraction,release,seed) in enumerate(cases,4 if extended else 0):
        start=int(len(edges)*release)
        while start and edges[start-1,2]==edges[start,2]:start-=1
        early=edges[start:start+max(1,(len(edges)-start)//100),0]
        senders,counts=np.unique(early,return_counts=True)
        ranked=senders[np.lexsort((senders,-counts))]
        source=int(ranked[int((len(ranked)-1)*fraction)])
        via=witnesses(edges,n,source,start)
        ids=np.sort(via[via>=0])
        if len(ids):
            parents=edges[ids,0]
            p,freq=np.unique(parents,return_counts=True)
            hot=p[np.lexsort((p,-freq))[:16]]
            hot_ids=ids[np.isin(parents,hot)]
        rng=np.random.default_rng(seed)
        workload=[]
        for j in range(2048 if extended else 128):
            lane=j%4
            if lane==0 or not len(ids):i=int(rng.integers(start,len(edges)))
            elif lane==1:i=int(rng.choice(ids))
            elif lane==2:i=int(rng.choice(ids[:32]))
            else:i=int(rng.choice(hot_ids))
            horizon=(j//4+lane)%4
            h=[len(edges)-1,rng.integers(start,len(edges)),rng.integers(i,len(edges)),i][horizon]
            workload.append((i,int(edges[h,2])))
        dest=OUT/"workloads"/f"{name}-{cohort}"
        dest.parent.mkdir(exist_ok=True,parents=True)
        dest.with_suffix(".txt").write_text("".join(f"{i} {h}\n" for i,h in workload))
        meta2=dict(graph=name,cohort=cohort,seed=seed,release_row=start,release_time=int(edges[start,2]),
                   source=source,reachable=len(ids)+1,total_rows=len(edges)-start,vertices=n,
                   workload_sha256=sha(dest.with_suffix(".txt")))
        dest.with_suffix(".json").write_text(json.dumps(meta2,indent=2)+"\n")

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("graphs",nargs="*");ap.add_argument("--extended",action="store_true")
    args=ap.parse_args()
    for graph in args.graphs or [*FILES,*TGB]:
        make(graph,args.extended)

