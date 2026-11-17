
import argparse
import filecmp
import hashlib
import json
import os
import random
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from numba import njit
from prepare import BASE,CACHE,sha
from run import save

OUT=BASE/"results/full/timetables"
CITIES={"kuopio":"d0192a8378193f5a90ae589a7be6172c","berlin":"13c7f559cc39571c5aa621057063d4d5",
        "paris":"914e5202f76d33bed9cfac75080270dd"}
ARMS=["mix","global","allpairs","csa"]

@njit
def scan(legs,order,n,s,start):
    first=np.full(n,2147483647,np.int32);first[s]=start-1
    via=np.full(n,-1,np.int32)
    for i in order:
        u,v,d,a=legs[i]
        if d>=start and first[u]<d and a<first[v]:
            first[v]=a;via[v]=i
    return via

def prepare(city):
    OUT.mkdir(parents=True,exist_ok=True)
    archive=CACHE/(city+".zip")
    url=f"https://zenodo.org/api/records/1186215/files/{city}.zip/content"
    if not archive.exists():
        import urllib.request
        urllib.request.urlretrieve(url,archive)
    with archive.open("rb") as f:assert hashlib.file_digest(f,"md5").hexdigest()==CITIES[city]
    with ZipFile(archive) as z:
        raw=z.read(f"{city}/network_temporal_day.csv")
    import io
    df=pd.read_csv(io.BytesIO(raw),sep=";")
    ids=np.unique(np.concatenate([df.from_stop_I.to_numpy(),df.to_stop_I.to_numpy()]))
    base=int(df.dep_time_ut.min())
    data=np.column_stack([np.searchsorted(ids,df.from_stop_I),np.searchsorted(ids,df.to_stop_I),
                          df.dep_time_ut-base,df.arr_time_ut-base]).astype("<i4")
    assert (data[:,2]<=data[:,3]).all()
    perm=np.argsort(data[:,3],kind="stable")
    legs=data[perm]
    path=CACHE/(city+".legs");legs.tofile(path)
    np.savez(CACHE/(city+"-leg-ids.npz"),source_row=perm+1,stops=ids,epoch=base)
    meta=dict(city=city,archive_url=url,daily_input_sha256=hashlib.sha256(raw).hexdigest(),packed_sha256=sha(path),
              rows=len(legs),vertices=len(ids),time_origin=base,zero_duration=int((legs[:,2]==legs[:,3]).sum()),
              max_time=int(legs[:,3].max()))
    save(OUT/f"{city}-input.json",meta)
    order=np.argsort(legs[:,2],kind="stable")
    for case,(quantile,release,seed) in enumerate([(0,0,711),(.5,0,2027),(.5,.5,9409)]):
        start=int(legs[order[int(release*(len(legs)-1))],2])
        available=order[legs[order,2]>=start]
        top=legs[available[:max(1,len(available)//100)],0]
        senders,num=np.unique(top,return_counts=True)
        ranked=senders[np.lexsort((senders,-num))]
        src=int(ranked[int(quantile*(len(ranked)-1))])
        via=scan(legs,order,len(ids),src,start);w=np.sort(via[via>=0])
        rng=np.random.default_rng(seed);qs=[]
        for j in range(256):
            if j%4==0 or not len(w):i=int(rng.choice(available))
            elif j%4==1:i=int(rng.choice(w))
            elif j%4==2:i=int(rng.choice(w[:32]))
            else:i=int(rng.choice(w[:max(1,len(w)//10)]))
            h=[meta["max_time"],int(rng.integers(start,meta["max_time"]+1)),
               int(rng.integers(int(legs[i,3]),meta["max_time"]+1)),int(legs[i,3])][(j//4+j%4)%4]
            qs.append((i,h))
        qfile=OUT/f"{city}-{case}.txt";qfile.write_text("".join(f"{i} {h}\n" for i,h in qs))
        save(qfile.with_suffix(".json"),dict(source=src,release=start,reachable=len(w)+1,seed=seed,query_sha256=sha(qfile)))

def invoke(legs,n,src,release,q,h,method,stem):
    exe=CACHE/"timetable.exe";t=time.perf_counter()
    p=subprocess.run([exe,legs,str(n),str(src),str(release),q,str(h),method,stem],
                     capture_output=True,text=True,check=True)
    result=json.loads(p.stdout);result["wall_s"]=time.perf_counter()-t;return result

def run(city):
    meta=json.loads((OUT/f"{city}-input.json").read_text())
    refs=CACHE/"timetable-answers";refs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=CACHE) as td:
        stem=Path(td)/"answer";wire=stem.with_suffix(".rows")
        for case in range(3):
            qfile=OUT/f"{city}-{case}.txt"
            s=json.loads(qfile.with_suffix(".json").read_text())
            for suite in (["online","census"] if case==0 else ["online"]):
                for rep in range(1 if suite=="census" else 3):
                    order=ARMS[:];random.Random(f"{city}-{case}-{rep}").shuffle(order)
                    for method in order:
                        key=f"{city}-{case}-{suite}"
                        dest=OUT/"runs"/f"{key}-{rep}-{method}.json";dest.parent.mkdir(exist_ok=True)
                        identity=dict(input=meta['packed_sha256'],queries='ALL' if suite=='census' else sha(qfile),
                                      source=s['source'],release=s['release'],binary=sha(CACHE/'timetable.exe'))
                        if dest.exists():
                            if json.loads(dest.read_text()).get('identity')!=identity:raise ValueError('stale run: '+str(dest))
                            continue
                        r=invoke(CACHE/(city+".legs"),meta["vertices"],s["source"],s["release"],
                                 "ALL" if suite=="census" else qfile,meta["max_time"],method,stem)
                        ref=refs/(key+".rows")
                        if ref.exists():
                            if not filecmp.cmp(ref,wire,shallow=False):raise ValueError([key,method])
                        else:os.replace(wire,ref)
                        assert ref.stat().st_size==8*r["positive"]+12*r["rows"]
                        r.update(city=city,case=case,suite=suite,rep=rep,method=method,status='complete',identity=identity,sha256=sha(ref),
                                 binary=sha(CACHE/"timetable.exe"))
                        save(dest,r)
                        print(key,rep,method,r["requests"],r["rows"],round(r["wall_s"],3),flush=True)

def exact():
    
    rng=random.Random(711);totals=[0,0,0]
    with tempfile.TemporaryDirectory(dir=CACHE) as td:
        folder=Path(td)
        for j in range(63):
            legs=[(rng.randrange(5),rng.randrange(5),d,d+rng.randrange(5)) for d in
                  [rng.randrange(7) for _ in range(14)]]
            if j==0:legs=[(0,1,0,5),(1,2,4,6),(1,2,5,7),(1,2,6,8),(0,1,2,3),(0,1,2,3),(2,3,8,8)]
            legs.sort(key=lambda e:e[3])
            start=j%3;src=j%5
            def arrivals(skip):
                ans=[2147483647]*5;ans[src]=start-1
                def walk(v,t):
                    for i,(u,w,d,a) in enumerate(legs):
                        if i!=skip and u==v and t<d and d>=start:
                            ans[w]=min(ans[w],a);walk(w,a)
                walk(src,start-1)
                return ans
            base=arrivals(-1);queries=[];oracle=bytearray()
            for i in range(len(legs)):
                alt=arrivals(i)
                for h in range(start,12):
                    k=len(queries);queries.append((i,h))
                    rows=[(v,t,alt[v] if alt[v]<=h else -1) for v,t in enumerate(base) if t<=h and alt[v]!=t]
                    if rows:
                        oracle.extend(struct.pack("<ii",k,len(rows)))
                        for row in rows:oracle.extend(struct.pack("<iii",*row))
                    totals[0]+=1;totals[1]+=bool(rows);totals[2]+=len(rows)
            file=folder/"legs";np.asarray(legs,"<i4").tofile(file)
            q=folder/"q";q.write_text("".join(f"{i} {h}\n" for i,h in queries))
            for arm in ARMS:
                invoke(file,5,src,start,q,12,arm,folder/"r")
                assert (folder/"r.rows").read_bytes()==oracle,(j,arm)
    OUT.mkdir(exist_ok=True,parents=True)
    save(OUT/"correctness.json",dict(instances=63,queries=totals[0],positive=totals[1],rows=totals[2],
         methods=ARMS,seed=711,oracle="fresh path enumeration per withdrawn event",binary=sha(CACHE/"timetable.exe")))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("action",choices=["prepare","run","exact"])
    ap.add_argument("cities",nargs="*");args=ap.parse_args()
    if args.action=="exact":exact()
    else:
        for city in args.cities or CITIES:
            (prepare if args.action=="prepare" else run)(city)

