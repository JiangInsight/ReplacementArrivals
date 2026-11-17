
import csv,json,math,statistics,zipfile
from pathlib import Path
from collections import Counter,defaultdict
from layout_audit import BASE,OUT,GRAPHS,CITIES,STRESS,LAY,POL,read,write

def quantile(hist,p):
    
    count=sum(hist.values()); target=max(1,math.ceil(p*count));sofar=0
    for v,n in sorted((int(x),n) for x,n in hist.items()):
        sofar+=n
        if sofar>=target:return v
    return 0
def table(path):
    with path.open(newline="",encoding="utf8") as f:return list(csv.DictReader(f))
def real(g):return "scheduled" if g in CITIES else "contact" if g in GRAPHS else "control"
def raw_profiles():
    raw=OUT/"raw"; archive=OUT/"raw-profiles.zip"
    if raw.exists():
        files=sorted(raw.glob("*.json"))
        
        if len(files)!=142:raise ValueError(f"Expected 142 setting profiles, found {len(files)}")
        with zipfile.ZipFile(archive.with_suffix(".tmp"),"w",compression=zipfile.ZIP_DEFLATED) as z:
            for f in files:
                entry=zipfile.ZipInfo(f.name,date_time=(2026,11,8,0,0,0))
                z.writestr(entry,f.read_bytes(),compress_type=zipfile.ZIP_DEFLATED)
        archive.with_suffix(".tmp").replace(archive)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError("Corrupt profile archive")
        for name in z.namelist():yield name[:-5],json.loads(z.read(name))
def archived_reference():
    archives=defaultdict(list)
    fallback=Path(__file__).resolve().parents[1]/'reference/layout-audit/archived-reference.csv'
    if not (BASE/"results/full/summary/runs.csv").exists():
        for a in table(fallback):
            archives[(a["graph"],int(a["cohort"]),a["policy"])].append((int(a["index_bytes"]),int(a["peak_bytes"])))
        return archives
    for a in table(BASE/"results/full/summary/runs.csv"):
        if a["method"] not in POL or a["suite"]!="main":continue
        archives[(a["graph"],int(a["cohort"]),a["method"])].append((int(a["index_bytes"]),int(a["peak_bytes"])))
    for city in CITIES:
        src="full" if city in CITIES[:3] else "expansion"
        for path in (BASE/"results"/src/"timetables/runs").glob(city+"-*-online-*.json"):
            a=read(path)
            if a["method"] in POL:
                archives[(city,a["case"],a["method"])].append((a["index_bytes"],0))
    records=[dict(graph=g,cohort=c,policy=m,index_bytes=int(statistics.median(x for x,y in v)),
        peak_bytes=int(statistics.median(y for x,y in v))) for (g,c,m),v in sorted(archives.items())
        if g in GRAPHS+CITIES and c in range(3 if g in CITIES else 4)]
    assert len(records)==171
    write(records,fallback)
    return archives
def summarize():
    archives=archived_reference()
    peaks={}
    for path in OUT.glob("peaks-*.csv"):
        for row in table(path):peaks[(row["graph"],int(row["cohort"]),row["policy"])]=row
    settings=[];groups=[];models=[];memory=[];synthetic=[]
    for name,a in raw_profiles():
        g=a["graph"];c=a["cohort"]
        tag=dict(setting=name,family=real(g),graph=g,cohort=c,source=a["source"])
        original=name==f"{g}-{c}"
        if g.startswith("d") and "-s" in g:
            p,s=(int(z[1:]) for z in g.split("-"));mix=a["groups"];best=next(x["kind"] for x in mix if x["roots"])
            synthetic.append(dict(depth=p,steps=s,events=a["eligible_events"],births=sum(x["recipients"] for x in mix),
                                U=sum(x["U"] for x in mix),hard=sum(x["hard"] for x in mix),choice=LAY[best],
                                live=sum(x["live"] for x in mix),retained=a["memory"][0]["retained"]))
            continue
        hist=a["histograms"];r=sum(x["recipients"] for x in a["groups"]);u=sum(x["U"] for x in a["groups"])
        live=sum(x["live"] for x in a["groups"])
        core=dict(**tag,eligible_events=a["eligible_events"],retained_births=r,U=u,U_per_eligible=u/a["eligible_events"],
                  uniform=sum(x["uniform"] for x in a["groups"]),hard=sum(x["hard"] for x in a["groups"]),
                  roots=sum(x["roots"] for x in a["groups"]))
        for key in ("depth","history","span","component"):
            for p in (.5,.9,.99,1):
                core[f"{key}_p{int(p*100)}"]=quantile(hist.get(key,{}),p)
        settings.append(core)
        mixed=a["memory"][0]
        for z in a["groups"]:
            capacity=mixed["cap"+LAY[z["kind"]]]
            groups.append(dict(**tag,layout=LAY[z["kind"]],roots=z["roots"],recipients=z["recipients"],
                recipient_fraction=z["recipients"]/r if r else 0,U=z["U"],uniform=z["uniform"],hard=z["hard"],
                score_bytes=z["score"],live_bytes=z["live"],live_fraction=z["live"]/live if live else 0,
                allocated_layout_bytes=capacity,fraction_of_entire_retained=capacity/mixed["retained"]))
        for x in a["profiles"]:models.append(dict(**tag,**x))
        for x in a["memory"]:
            kind=POL[x["policy"]];key=(g,c,kind);peak=peaks.get(key,{}) if original else {}
            rec=archives.get(key,[]) if original else []
            archive_bytes=statistics.median(z[0] for z in rec) if rec else None
            
            
            if peak:assert int(peak["retained"])==x["retained"]
            mem=dict(**tag,policy=kind,live_E=x["liveE"],live_D=x["liveD"],live_C=x["liveC"],
                capacity_E=x["capE"],capacity_D=x["capD"],capacity_C=x["capC"],
                logical_payload=x["liveE"]+x["liveD"]+x["liveC"],capacity_buffers=x["capE"]+x["capD"]+x["capC"],
                dictionary_bytes=x["dictionary"],header_bytes=x["header"],retained=x["retained"],
                prebuild_peak=peak.get("prebuild_process_peak",""),construction_peak=peak.get("construction_process_peak",""),
                archived_retained=archive_bytes or "",archived_end_to_end_peak=statistics.median(z[1] for z in rec) if rec and rec[0][1] else "")
            assert mem["capacity_buffers"]+mem["dictionary_bytes"]+mem["header_bytes"]==mem["retained"]
            memory.append(mem)
    for rows,name in [(settings,"session-structure"),(groups,"root-choices"),(models,"scoring-sensitivity"),(memory,"memory"),]:
        write(rows,OUT/(name+".csv"))
    tm=defaultdict(list)
    for t in table(OUT/"synthetic_times.csv"):tm[(int(t["depth"]),int(t["steps"]),t["layout"])].append(t)
    for x in synthetic:
        for k in LAY:
            lines=tm[(x["depth"],x["steps"],k)];assert len(lines)==3
            x["retained_"+k]=int(lines[0]["retained"])
            x["build_us_"+k]=statistics.median(float(a["build_s"])*1e6 for a in lines)
            durations=[float(a["roster_checksum_s"])*1e6/int(a["requests"]) for a in lines]
            x["query_us_"+k]=statistics.median(durations)
            x["query_min_us_"+k]=min(durations);x["query_max_us_"+k]=max(durations)
        x["fastest_on_test"]=min(LAY,key=lambda k:x["query_us_"+k])
    synthetic.sort(key=lambda x:(x["depth"],x["steps"]))
    write(synthetic,OUT/"synthetic-transitions.csv")

if __name__=="__main__":summarize()

