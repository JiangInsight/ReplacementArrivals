
import experiment as x
def main():
    x.EXSHA=x.sha(x.EX)
    for g in x.G[:6]:
        inp=x.CACHE/(g+'.bin');digest=x.sha(inp);assert digest==x.load(x.F/'inputs'/(g+'.json'))['packed_sha256']
        s=x.original(g,0);q=x.F/'workloads'/f'{g}-0.txt';qs=[tuple(map(int,k.split())) for k in q.read_text().splitlines()]
        ref=x.CACHE/'answers'/f'{g}-0-{x.sha(q)[:16]}.rows'
        x.run('direct128','direct128-'+g,s,qs,ref,'incident calendar tglib decremental repair mix'.split(),inp,digest,budget=45)
if __name__=='__main__':main()

