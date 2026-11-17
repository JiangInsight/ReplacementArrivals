
import experiment as x
from experiment import np,sha
def main():
    x.EXSHA=sha(x.EX)
    for graph in ['college','email','math']:
        inp=x.CACHE/(graph+'.bin');digest=sha(inp);assert digest==x.load(x.F/'inputs'/(graph+'.json'))['packed_sha256']
        e=np.memmap(inp,dtype='<i4',mode='r').reshape(-1,3);template=x.original(graph,0);n=template['vertices']
        f=np.bincount(e[:,0],minlength=n);top=np.lexsort((np.arange(n),-f))[:10]
        samples=np.random.default_rng(5071).choice(n,100,replace=False)
        for label,ids in [('uniform',samples),('high',top)]:
            for src in ids:
                src=int(src);s=dict(template,source=src);key=f'source-{graph}-{label}-{src}';ref=x.R/(key+'.rows')
                via=x.witnesses(e,n,src,0);w=via[via>=0]
                rng=np.random.default_rng([3417,src]);qs=[]
                for j in range(32):
                    i=int(rng.choice(w)) if j%2 and len(w) else int(rng.integers(len(e)))
                    h=int(e[-1 if j%4<2 else rng.integers(i,len(e)),2]);qs.append((i,h))
                if ref.exists():ref.unlink()
                x.run('sources',key,s,qs,ref,['mix','decremental','repair'],inp,digest,dict(sampling=label,reachable=len(w)+1,outgoing=int(f[src])),repeats=1)
if __name__=='__main__':main()

