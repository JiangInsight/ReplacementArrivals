import sys,random,json,struct,shutil,tempfile,filecmp,time,subprocess,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepare import BASE,CACHE,sha
from run import save
from workloads import witnesses
import numpy as np
O=BASE/'results/expansion';F=BASE/'results/full';EX=CACHE/'expanded.exe'
R=CACHE/'expansion-answers';R.mkdir(exist_ok=True)
W=O/'workloads';W.mkdir(exist_ok=True,parents=True)
G='otc college email math ubuntu higgs coin comment flight'.split()
A=['mix','global','allpairs',*('without-'+x for x in 'explicit direct catalog uniform prune links'.split())]
def load(p):return json.loads(p.read_text())
def original(g,c):return load(F/'workloads'/f'{g}-{c}.json')
def unpack(data):
    x=0
    while x<len(data):
        n=struct.unpack_from('<I',data,x)[0];y=x+4+12*n
        assert y<=len(data);yield data[x:y];x=y
def run(group,key,s,qs,ref,methods,inp,sha_input,more=None,budget=300,repeats=3):
    q=W/(key+'.txt');q.write_text(''.join(f'{i} {h}\n' for i,h in qs))
    case=dict(group=group,key=key,source=s['source'],vertices=s['vertices'],release_row=s['release_row'],graph=s['graph'],requests=len(qs),distinct_events=len({i for i,h in qs}),input_sha256=sha_input,query_sha256=sha(q),**(more or {}))
    save(q.with_suffix('.json'),case)
    raw=O/'runs'/key;raw.mkdir(parents=True,exist_ok=True)
    expected=sha(ref) if ref.exists() else None
    if expected is None: assert group in ('scale','sources')
    with tempfile.TemporaryDirectory(dir=CACHE) as td:
        stem=Path(td)/'out';stats=Path(td)/'stats';wire=stem.with_suffix('.rows')
        def invoke(m,b):return subprocess.run([EX,inp,str(s['vertices']),str(s['source']),str(s['release_row']),q,m,stem,stats],capture_output=True,timeout=b,check=True)
        if not expected:
            invoke('scan',600);shutil.copyfile(wire,ref);expected=sha(ref)
        identity=dict(input=sha_input,queries=sha(q),answer=expected,binary=EXSHA)
        for rep in range(repeats):
            arms=methods[:];random.Random(f'{key}/{rep}/314').shuffle(arms)
            for m in arms:
                dest=raw/f'{rep}-{m}.json'
                if dest.exists():
                    assert load(dest)['identity']==identity;continue
                prev=raw/f'{rep-1}-{m}.json';rec=dict(key=key,group=group,method=m,rep=rep,identity=identity,budget_s=budget)
                if rep and prev.exists() and load(prev)['status']!='complete':
                    save(dest,dict(rec,status='not-repeated-after-timeout'));continue
                t=time.perf_counter()
                try:invoke(m,budget)
                except subprocess.TimeoutExpired:
                    save(dest,dict(rec,status='timeout',wall_s=time.perf_counter()-t));continue
                wall=time.perf_counter()-t
                assert filecmp.cmp(wire,ref,shallow=False),(key,m,rep)
                rows=list(csv.DictReader(stem.with_suffix('.csv').open()));assert [(int(r['event']),int(r['deadline'])) for r in rows]==qs
                durations=np.array([int(r['query_ns']) for r in rows]);enc=sum(int(r['encode_ns']) for r in rows)
                shutil.copyfile(stem.with_suffix('.csv'),dest.with_suffix('.csv'))
                save(dest,dict(load(stats),**rec,status='complete',wall_s=wall,requests=len(rows),rows=sum(int(r['rows']) for r in rows),nonempty=sum(int(r['rows'])>0 for r in rows),query_s=float(durations.sum())/1e9,encode_s=enc/1e9,p95_ns=float(np.percentile(durations,95)),p99_ns=float(np.percentile(durations,99))))
    print(key,'done',flush=True)
def contact(g,group):
    inp=CACHE/(g+'.bin');meta=load(F/'inputs'/(g+'.json'));digest=meta['packed_sha256'];assert sha(inp)==digest
    for c in ([0,2] if group=='ablation' and g in G else [0]):
        s=original(g,c);q=F/'workloads'/f'{g}-{c}.txt'
        qs=[tuple(map(int,r.split())) for r in q.read_text().splitlines()]
        ref=CACHE/'answers'/f"{g}-{c}-{sha(q)[:16]}.rows"
        if group=='ablation':run(group,f'abl-{g}-{c}',s,qs,ref,A,inp,digest);continue
        rng=random.Random('external/'+g)
        if group=='direct':
            ans=list(unpack(ref.read_bytes()))
            ids=[i for yes in (True,False) for i in rng.sample([j for j,a in enumerate(ans) if (len(a)>4)==yes],min(8,sum((len(a)>4)==yes for a in ans)))]
            rng.shuffle(ids);key='direct-'+g;ref2=R/(key+'.rows');ref2.write_bytes(b''.join(ans[i] for i in ids))
            run(group,key,s,[qs[i] for i in ids],ref2,'incident calendar tglib decremental repair mix'.split(),inp,digest,budget=45)
        elif group=='conditioned':
            data=(CACHE/'census-answers'/f'{g}-0-end.rows').read_bytes()
            pos={};j=0
            while j<len(data):
                i,n=struct.unpack_from('<ii',data,j);pos[i]=(j+4,j+8+n*12);j+=8+n*12
            assert j==len(data) and pos
            ids=rng.sample(list(pos),min(1000,len(pos)))
            ids+=rng.choices(list(pos),k=1000-len(ids));zero=set()
            while len(zero)<1000:
                i=rng.randrange(meta['rows'])
                if i not in pos:zero.add(i)
            ids+=sorted(zero);rng.shuffle(ids)
            h=int(np.memmap(inp,dtype='<i4',mode='r')[-1]);key='positive-'+g;ref2=R/(key+'.rows')
            ref2.write_bytes(b''.join(data[slice(*pos[i])] if i in pos else bytes(4) for i in ids))
            run(group,key,s,[(i,h) for i in ids],ref2,'mix without-prune decremental repair'.split(),inp,digest,dict(positive_population=len(pos),distinct_positive=len(set(ids)&pos.keys()),full_deadline=h))
def scale(g,axis):
    orig=CACHE/(g+'.bin');e=np.memmap(orig,dtype='<i4',mode='r').reshape(-1,3);s=original(g,0);n=s['vertices'];src=s['source']
    assert sha(orig)==load(F/'inputs'/(g+'.json'))['packed_sha256']
    rank=np.random.default_rng(2519).integers(0,100,size=n if axis=='vertices' else len(e),dtype=np.uint8)
    if axis=='vertices':rank[src]=0
    for pct in [20,40,60,80,100]:
        key=f'scale-{g}-{axis}-{pct}';inp=CACHE/(key+'.bin') if pct!=100 else orig
        if pct!=100:
            mask=(rank[e[:,0]]<pct)&(rank[e[:,1]]<pct) if axis=='vertices' else rank<pct
            e[mask].tofile(inp)
        z=np.memmap(inp,dtype='<i4',mode='r').reshape(-1,3);via=witnesses(z,n,src,0);w=via[via>=0];rng=np.random.default_rng(8801);qs=[]
        for j in range(64):
            i=int(rng.choice(w)) if j%2 and len(w) else int(rng.integers(len(z)))
            h=int(z[-1 if j%4<2 else rng.integers(i,len(z)),2]);qs.append((i,h))
        ref=R/(key+'.rows')
        
        if ref.exists():ref.unlink()
        seen=np.zeros(n,dtype=bool);seen[z[:,0]]=True;seen[z[:,1]]=True
        run('scale',key,s,qs,ref,'mix dom decremental'.split(),inp,sha(inp),dict(axis=axis,target_pct=pct,events=len(z),active_vertices=int(seen.sum()),reachable=1+len(w),sampling_seed=2519))
        del z
        if pct!=100:inp.unlink()
if __name__=='__main__':
    EXSHA=sha(EX)
    for group in sys.argv[1:] or ['direct','ablation','conditioned','scale']:
        if group=='scale':
            for g in ['math','coin']:
                for axis in ['contacts','vertices']:scale(g,axis)
        else:
            for g in G+('shared1024 stairs256 sparse2048 mixed2048'.split() if group=='ablation' else []):contact(g,group)

