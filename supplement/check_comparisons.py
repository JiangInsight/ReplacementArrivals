
from pathlib import Path
import csv,json,statistics as st,sys
if len(sys.argv)!=2: raise SystemExit("Usage: python check_comparisons.py PATH_TO_RESULTS")
R=Path(sys.argv[1])
graphs='otc college email math higgs ubuntu coin comment flight'.split()
def read(p):return json.loads(p.read_text())
def cell(g,m,rep):
    p=R/'expansion/runs'/('positive-'+g)/(str(rep)+'-'+m+'.json')
    meta=read(p)
    with p.with_suffix('.csv').open() as fh: requests=list(csv.DictReader(fh))
    assert len(requests)==2000 and sum(int(x['rows'])>0 for x in requests)==1000
    return (sum(int(x['query_ns'])+int(x['encode_ns']) for x in requests)*1e-9,meta['wall_s'])
def summarize():
    result={}
    for method in ('decremental','repair'):
        result[method]={}
        for col,label in enumerate(('service','wall')):
            ratios=[];ahead=0;behind=0
            for g in graphs:
                ours=[cell(g,'mix',i)[col] for i in range(3)]
                theirs=[cell(g,method,i)[col] for i in range(3)]
                ratios.append(st.median(theirs)/st.median(ours))
                ahead+=max(ours)<min(theirs);behind+=max(theirs)<min(ours)
            result[method][label]=dict(median=st.median(ratios),range=[min(ratios),max(ratios)],median_wins=sum(x>1 for x in ratios),disjoint_favor_index=ahead,disjoint_favor_baseline=behind)
    return result
if __name__=='__main__':print(json.dumps(summarize(),indent=2))
