import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit_native as a
from prepare import BASE,CACHE,sha
a.METHODS=('incident','calendar','decremental','mix',*('without-'+x for x in ('explicit','direct','catalog','uniform','prune','links')))
if __name__=='__main__':
    out=BASE/'results/expansion';out.mkdir(exist_ok=True,parents=True)
    r=a.execute(CACHE/'expanded.exe','base')
    root=Path(__file__).resolve().parents[2]
    r['source_sha256'].update({str(p.relative_to(root)):sha(p) for p in (root/'study').rglob('*.hpp')})
    (out/'correctness.json').write_text(json.dumps(r,indent=2))
    print(r['totals'])

