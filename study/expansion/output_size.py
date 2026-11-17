

import experiment as x
import struct
def main():
    x.EXSHA=x.sha(x.EX)
    for g in x.G:
        orig=x.CACHE/(g+'.bin');digest=x.sha(orig);assert digest==x.load(x.F/'inputs'/(g+'.json'))['packed_sha256']
        e=x.np.memmap(orig,dtype='<i4',mode='r').reshape(-1,3);end=int(e[-1,2])
        raw=(x.CACHE/'census-answers'/f'{g}-0-end.rows').read_bytes();bins=[[] for _ in range(6)];j=0
        while j<len(raw):
            i,n=struct.unpack_from('<ii',raw,j);b=sum(n>=v for v in (2,4,16,64,256));bins[b].append((i,n,j+8));j+=8+12*n
        rng=x.random.Random('size-grid/702/'+g);selected=[rng.sample(a,min(24,len(a))) for a in bins]
        tasks=[];labels=['1','2-3','4-15','16-63','64-255','256+']
        for b,items in enumerate(selected):
            for i,n,j in items:
                t=int(e[i,2])
                for phase,h in [('at-contact',t),('midpoint',(t+end)//2),('end',end)]:tasks.append((i,n,j,b,h,phase))
        rng.shuffle(tasks);qs=[];lanes=[];key='size-'+g;ref=x.R/(key+'.rows')
        with ref.open('wb') as out:
            for i,n,j,b,h,phase in tasks:
                full=x.np.frombuffer(raw,'<i4',3*n,j).reshape(-1,3);picked=full[full[:,1]<=h].copy();picked[picked[:,2]>h,2]=-1
                out.write(struct.pack('<I',len(picked)));out.write(picked.tobytes());qs.append((i,h));lanes.append((labels[b],phase))
        x.save(x.W/(key+'.lanes'),lanes)
        x.run('size',key,x.original(g,0),qs,ref,['mix','without-prune','decremental','repair'],orig,digest,dict(bin_population=[len(a) for a in bins],drawn_per_bin=[len(a) for a in selected]))
if __name__=='__main__':main()

