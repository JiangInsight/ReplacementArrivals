
import json
import numpy as np
from prepare import BASE,CACHE,sha
from workloads import OUT,witnesses

def family(kind,d):
    records=[]
    next_vertex=1
    def chain(flavor):
        nonlocal next_vertex
        spine=[0,*range(next_vertex,next_vertex+d)]
        leaves=list(range(next_vertex+d,next_vertex+2*d))
        next_vertex+=2*d
        records.extend((spine[i-1],spine[i],i) for i in range(1,d+1))
        records.extend((spine[-1],v,d+1) for v in leaves)
        if flavor=="shared":levels=[0]
        elif flavor=="stairs":levels=list(range(d-1,-1,-1))
        else:levels=list(range(d-1,-1,-max(1,d//16)))+[0]
        for j,p in enumerate(dict.fromkeys(levels)):
            records.extend((spine[p],v,d+2+8*j+(i%7)) for i,v in enumerate(leaves))
    if kind=="mixed":
        chain("shared");chain("sparse")
        records.extend((0,v,1+v%7) for v in range(next_vertex,next_vertex+8*d))
        next_vertex+=8*d
    else:chain(kind)
    records.sort(key=lambda x:x[2])
    return np.asarray(records,dtype="<i4"),next_vertex

def fixtures():
    names=[]
    for kind,depths in [("shared",(64,256,1024,4096)),("stairs",(64,256,1024)),
                        ("sparse",(128,512,2048)),("mixed",(128,512,2048))]:
        for d in depths:
            name=f"{kind}{d}";names.append(name)
            data,n=family(kind,d)
            file=CACHE/(name+".bin");data.tofile(file)
            spec=dict(dataset=name,rows=len(data),vertices=n,times=len(np.unique(data[:,2])),
                      packed_sha256=sha(file),generator=kind,depth=d)
            (OUT/"inputs"/(name+".json")).write_text(json.dumps(spec,indent=2)+"\n")
            via=witnesses(data,n,0,0);via=np.sort(via[via>=0])
            rng=np.random.default_rng(711)
            qs=[]
            for i in range(128):
                if i%4==0:e=rng.integers(len(data))
                elif i%4==1:e=rng.choice(via)
                elif i%4==2:e=rng.choice(via[:32])
                else:e=rng.choice(via[:min(len(via),2*d)])
                h=[data[-1,2],data[rng.integers(len(data)),2],data[rng.integers(e,len(data)),2],data[e,2]][(i//4+i%4)%4]
                qs.append((e,h))
            path=OUT/"workloads"/(name+"-0.txt")
            path.write_text("".join(f"{e} {h}\n" for e,h in qs))
            spec=dict(graph=name,cohort=0,seed=711,release_row=0,release_time=int(data[0,2]),source=0,
                      reachable=len(via)+1,total_rows=len(data),vertices=n,workload_sha256=sha(path))
            path.with_suffix(".json").write_text(json.dumps(spec,indent=2)+"\n")
    return names

if __name__=="__main__":
    print(" ".join(fixtures()))

