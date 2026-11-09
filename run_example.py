import csv
from itertools import groupby
from pathlib import Path
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parent
with (root/"data/contacts.csv").open(newline="") as stream:
    events = [tuple(map(int,row)) for row in list(csv.reader(stream))[1:]]
with (root/"data/queries.tsv").open(newline="") as stream:
    queries = [tuple(map(int,row)) for row in list(csv.reader(stream,delimiter="\t"))[1:]]
vertices = 1 + max(max(u,v) for u,v,t in events)

def arrivals(withdrawn, deadline):
    reached = {0:-1}
    for time, batch in groupby(enumerate(events),key=lambda item:item[1][2]):
        if time > deadline:
            break
        added = {v for i,(u,v,t) in batch if i != withdrawn and u in reached}
        for vertex in added:
            reached.setdefault(vertex,time)
    return reached

expected = bytearray()
for event, deadline in queries:
    first, revised = arrivals(None,deadline), arrivals(event,deadline)
    rows = [(v,t,revised.get(v,-1)) for v,t in sorted(first.items()) if revised.get(v) != t]
    expected.extend(struct.pack("<I",len(rows)))
    for row in rows:
        expected.extend(struct.pack("<iii",*row))
with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp)
    contacts, requests, answers = (work/n for n in ("contacts.bin","requests.txt","answers.bin"))
    contacts.write_bytes(b"".join(struct.pack("<iii",*e) for e in events))
    requests.write_text("".join(f"{e} {t}\n" for e,t in queries))
    for method in ("mixed","point"):
        subprocess.run([root/"build/arrivals.exe",contacts,str(vertices),"0","0",requests,answers,method],check=True)
        if answers.read_bytes() != expected:
            raise ValueError(f"Incorrect recipient roster from {method}")
print(f"Both indexes match chronological replay on {len(queries)} withdrawals.")
