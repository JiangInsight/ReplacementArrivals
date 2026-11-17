
import argparse,csv,hashlib,json,os,subprocess,tempfile,random,statistics
from collections import Counter
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
BASE=Path(os.environ.get("PAPER3_WORKSPACE", ROOT/".work"))
STUDY=ROOT/"study"
CACHE=Path(os.environ.get("PAPER3_CACHE",BASE/"cache"))
WORK=CACHE/"layout-audit";WORK.mkdir(parents=True,exist_ok=True)
OUT=BASE/"results/layout_audit"
OUT.mkdir(exist_ok=True,parents=True)
GRAPHS="college email otc math ubuntu higgs coin comment flight".split()
CITIES="kuopio berlin paris bordeaux detroit sydney winnipeg".split()
STRESS="shared1024 stairs256 sparse2048 mixed2048".split()
EX=WORK/"audit.exe"
POL=["mix","global","allpairs"]
LAY=["E","D","C"]
def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def read(p):return json.loads(p.read_text())
def save(data,p):p.write_text(json.dumps(data,indent=2)+"\n",encoding="utf8")
def write(rows,p):
    with p.open("w",newline="",encoding="utf8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def build():
    src=(STUDY/"components.hpp").read_text()
    key="++root_counts[kind[x]];"
    assert src.count(key)==1
    
    (WORK/"layout_audit_components.hpp").write_text(src.replace(key,"if(audit_force>=0) kind[x]=audit_force;\n            "+key))
    driver=WORK/"layout_audit.cpp";driver.write_bytes((HERE/driver.name).read_bytes())
    subprocess.run([STUDY/"build.bat",WORK,EX,driver],check=True)
    save(dict(binary=sha(EX),instrument=sha(HERE/"layout_audit.cpp"),headers={x.name:sha(x) for x in
         [STUDY/(n+".hpp") for n in ("components","cascade","dictionary","histories","contact")]}),OUT/"build.json")
def metadata(graph,k):
    if graph in CITIES:
        dr=BASE/"results/full/timetables"
        m=read(dr/(graph+"-input.json"));s=read(dr/(f"{graph}-{k}.json"))
        return CACHE/(graph+".legs"),m["vertices"],s["source"],s["release"],m["packed_sha256"]
    f=BASE/"results/full";m=read(f/"inputs"/(graph+".json"));s=read(f/"workloads"/(f"{graph}-{k}.json"))
    return CACHE/(graph+".bin"),s["vertices"],s["source"],s["release_row"],m["packed_sha256"]
def native(mode,g,meta,cap,arg,path):
    p,n,s,first,_=meta
    q=subprocess.run([EX,mode,p,str(n),str(s),str(first),str(cap),str(int(g in CITIES)),str(arg),path],
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,text=True)
    return [r.split() for r in q.stdout.splitlines() if r]
def process(g,k,meta,cap=-1,suffix=""):
    stamp=f"{g}-{k}"+suffix; rootfile=WORK/(stamp+".roots");hist={};groups=[];sensitivity=[];memory=[]
    for tag,*v in native("profile",g,meta,cap,-1,rootfile):
        if tag=="W":eligible=int(v[0]);continue
        if tag=="H":hist.setdefault(v[0],{})[int(v[1])]=int(v[2]);continue
        if tag=="G":groups.append(dict(zip(("kind","roots","recipients","U","hard","uniform","score","live"),map(int,v))))
        if tag=="S":sensitivity.append(dict(model=v[0],**dict(zip(("E","D","C","switched","recipients_switched","native_live"),map(int,v[1:])))))
        if tag=="M":memory.append(dict(zip(("policy","liveE","liveD","liveC","capE","capD","capC","dictionary","header","retained"),map(int,v))))
    assert len(groups)==len(memory)==3 and len(sensitivity)==6
    total=sum(row["recipients"] for row in groups)
    assert sum(hist.get("depth",{}).values())==total
    result=dict(graph=g,cohort=k,source=meta[2],start=meta[3],cap=cap,input_sha256=meta[4],eligible_events=eligible,
                events=(meta[0].stat().st_size//(16 if g in CITIES else 12) if cap<0 else cap),
                groups=groups,histograms=hist,profiles=sensitivity,memory=memory)
    (OUT/"raw").mkdir(exist_ok=True);save(result,OUT/"raw"/(stamp+".json"))
    return rootfile
def profiles(graphs):
    for g in graphs:
        for k in range(3 if g in CITIES else 1 if g in STRESS else 4):
            meta=metadata(g,k)
            if k==0:assert sha(meta[0])==meta[4]
            process(g,k,meta)
        print(g,flush=True)
def windows():
    rows=[]
    for g in ("college","math"):
        meta=metadata(g,0);assert sha(meta[0])==meta[4]
        ref=process(g,0,meta);orig={e:(k,n) for e,k,n in np.fromfile(ref,"<i4").reshape(-1,3)}
        e=np.memmap(meta[0],dtype="<i4",mode="r").reshape(-1,3)
        for label,release,cap in [("release+1pct",1,100),("prefix99pct",0,99)]:
            left=int(np.searchsorted(e[:,2],e[len(e)*release//100,2],side="left"))
            right=len(e) if cap==100 else int(np.searchsorted(e[:,2],e[len(e)*cap//100,2],side="right"))
            m=(meta[0],meta[1],meta[2],left,meta[4])
            path=process(g,0,m,right,"-"+label);new={i:(k,n) for i,k,n in np.fromfile(path,"<i4").reshape(-1,3)}
            common=orig.keys()&new.keys()
            rows.append(dict(graph=g,source=meta[2],condition=label,kept_rows=right-left,
                      base_roots=len(orig),new_roots=len(new),same_event_root=len(common),
                      departed=len(orig)-len(common),appeared=len(new)-len(common),
                      encoding_changed=sum(orig[i][0]!=new[i][0] for i in common),
                      size_changed=sum(orig[i][1]!=new[i][1] for i in common)))
    write(rows,OUT/"windows.csv")
def generated(depth,steps):
    
    
    stream=[(v,v+1,v+1) for v in range(depth)]
    stream.extend((depth,depth+1+j,depth+1) for j in range(depth))
    parents=np.linspace(depth-1,0,min(depth,steps),dtype=int) if steps>=2 else ([max(0,(depth-1)//2)] if steps else [])
    for j,p in enumerate(parents):
        stream.extend((p,depth+1+i,depth+2+j) for i in range(depth))
    e=np.array(stream,dtype="<i4")
    g=f"d{depth}-s{steps}";path=WORK/(g+".bin");e.tofile(path)
    rng=random.Random(9124);h=int(e[-1,2]);most=min(len(e),2*depth)
    qs=[(rng.randrange(len(e)) if j%4==0 else rng.randrange(most), h if j%3 else rng.randrange(h+1)) for j in range(256)]
    qp=WORK/(g+".txt");qp.write_text("".join(f"{i} {t}\n" for i,t in qs))
    return g,(path,2*depth+1,0,0,sha(path)),qp
def run_synthetic(timing):
    out=[]
    
    for d in (1,2,4,8,16,24,32,48,64,96,128,192):
        for s in sorted({min(d,k) for k in (0,1,2,4,8,16,32,64,192)}):
            g,m,qp=generated(d,s)
            if not timing:process(g,0,m);continue
            for repeat in range(3):
                order=list(range(3));random.Random(5812+repeat*19+d+s).shuffle(order)
                fingerprints=[]
                for p in order:
                    [v]=native("serve",g,m,-1,p,qp)
                    _,policy,build,serve,n,check,b=v
                    fingerprints.append((int(n),int(check)))
                    out.append(dict(depth=d,steps=s,repeat=repeat,layout=LAY[p],build_s=float(build),
                        roster_checksum_s=float(serve),requests=1280,count=int(n),digest=check,retained=int(b)))
                assert len(set(fingerprints))==1
    if timing:write(out,OUT/"synthetic_times.csv")
def peaks(graphs):
    raw=[]
    for g in graphs:
        for k in range(3 if g in CITIES else 4):
            m=metadata(g,k)
            for p,method in enumerate(POL):
                [[tag,pol,loaded,peak,retained]]=native("peak",g,m,-1,p,WORK/"ignore")
                assert tag=="P"
                raw.append(dict(graph=g,cohort=k,policy=method,prebuild_process_peak=int(loaded),
                                construction_process_peak=int(peak),retained=int(retained)))
            print("peak",g,k,flush=True)
        write(raw,OUT/("peaks-"+graphs[0]+".csv"))
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=["build","profile","windows","synthetic","timing","peak"])
    parser.add_argument("graphs",nargs="*");a=parser.parse_args()
    if a.mode=="build":build()
    elif a.mode=="profile":profiles(a.graphs or GRAPHS+CITIES+STRESS)
    elif a.mode=="windows":windows()
    elif a.mode=="peak":peaks(a.graphs or GRAPHS+CITIES)
    else:run_synthetic(a.mode=="timing")

