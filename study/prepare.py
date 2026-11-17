
import argparse
import gzip
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

BASE = Path(os.environ.get("PAPER3_WORKSPACE", Path(__file__).resolve().parents[1] / ".work"))
CACHE = Path(os.environ.get("PAPER3_CACHE", BASE / "cache"))
REV = "af2aaea1b75bf58dcc9d01521d0347c89afec878"
FILES = {"college": "CollegeMsg.txt.gz", "email": "email-Eu-core-temporal.txt.gz",
         "math": "sx-mathoverflow.txt.gz", "ubuntu": "sx-askubuntu.txt.gz",
         "otc": "soc-sign-bitcoinotc.csv.gz","higgs":"higgs-activity_time.txt.gz"}
TGB = {"coin": ("2cb55669b70c80745b5bef406780431994c1077f87467e5f57836934f0312fca",22809486),
       "comment": ("370293c934558da2f7c83d84a9c2615d9a9cba270d759517afd80fbcc57795fe",44314507),
       "flight": ("ebc32bfff9375e0456affdf68bdec696d54889b52627cef49712b125c96b836d",67169570)}

def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def prepare(name):
    import urllib.request
    CACHE.mkdir(parents=True,exist_ok=True)
    if name in TGB:
        raw = CACHE / (name+".parquet")
        url = f"https://huggingface.co/datasets/stanford-star/tgb/resolve/{REV}/tgbl-{name}/db/events.parquet"
    else:
        raw = BASE / "data" / FILES[name]
        url = "https://snap.stanford.edu/data/"+raw.name
    if not raw.exists():
        raw.parent.mkdir(parents=True,exist_ok=True)
        part = raw.with_suffix(".download")
        urllib.request.urlretrieve(url,part)
        part.replace(raw)
    digest = sha(raw)
    recorded=Path(__file__).resolve().parents[1]/"reference"/"inputs"/(name+".json")
    if recorded.exists() and digest!=json.loads(recorded.read_text())["raw_sha256"]:
        raise ValueError(f"published input changed: {name}")
    unit = "seconds"
    if name in TGB:
        assert digest == TGB[name][0]
        table = pq.read_table(raw,columns=["src_id","dst_id","event_ts","event_id"])
        u,v = (table[key].to_numpy().astype(np.int32) for key in ["src_id","dst_id"])
        stamp = table["event_ts"].to_numpy().astype("datetime64[ns]").astype(np.int64)
        assert np.all(stamp % 1000000000 == 0)
        stamp //= 1000000000
        ids = table["event_id"].to_numpy().astype(np.int32)
        assert len(ids)==TGB[name][1] and np.array_equal(ids,np.arange(len(ids),dtype=np.int32))
        del table
        vertices = np.unique(np.concatenate([u,v]))
    else:
        if name=="otc":
            with gzip.open(raw,"rt") as f:
                records=[s.strip().split(",") for s in f if s.strip()]
            amounts = [Decimal(r[3]) for r in records]
            precision = max(0,-min(x.as_tuple().exponent for x in amounts))
            stamp = np.array([int(x*10**precision) for x in amounts],np.int64)
            unit = f"10^-{precision} seconds"
            u,v = (np.array([int(r[j]) for r in records],np.int32) for j in [0,1])
        elif name=="higgs":
            df=pd.read_csv(raw,sep=r"\s+",header=None,names=["actor","other","t","type"])
            assert set(df.type)=={"RT","MT","RE"}
            retweet=df.type=="RT"
            u=np.where(retweet,df.other,df.actor)
            v=np.where(retweet,df.actor,df.other)
            stamp=df.t.to_numpy()
        else:
            df = pd.read_csv(raw,sep=r"\s+",header=None,comment="#",names=["u","v","t"])
            u,v,stamp = df.u.to_numpy(),df.v.to_numpy(),df.t.to_numpy()
        ids = np.arange(1,len(stamp)+1,dtype=np.int32)
        vertices = np.unique(np.concatenate([u,v]))
    out = np.empty((len(stamp),3),dtype="<i4")
    out[:,0] = np.searchsorted(vertices,u)
    out[:,1] = np.searchsorted(vertices,v)
    times,ranks = np.unique(stamp,return_inverse=True)
    out[:,2] = ranks
    if np.any(np.diff(out[:,2])<0):
        perm = np.argsort(out[:,2],kind="stable")
        out, ids = out[perm], ids[perm]
    path = CACHE / (name+".bin")
    out.tofile(path)
    np.savez(CACHE/(name+"-ids.npz"),vertices=vertices,times=times,events=ids)
    data = dict(dataset=name,url=url,raw_sha256=digest,rows=len(ids),vertices=len(vertices),
                times=len(times),tick=unit,packed_sha256=sha(path),raw_bytes=raw.stat().st_size)
    dest = BASE/"results"/"full"/"inputs"
    dest.mkdir(exist_ok=True,parents=True)
    (dest/(name+".json")).write_text(json.dumps(data,indent=2)+"\n")
    print(name,len(out),len(vertices),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("graphs",nargs="+",choices=[*FILES,*TGB])
    for name in ap.parse_args().graphs:
        prepare(name)

