import argparse
import csv
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from urllib.request import urlretrieve


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack_events(source, packed):
    with gzip.open(source, "rt", newline="") as stream:
        events = [(int(u), int(v), Decimal(when)) for u, v, _, when in csv.reader(stream)]
    vertices = sorted({v for u, w, _ in events for v in (u, w)})
    ranks = {t: i for i, t in enumerate(sorted({t for _, _, t in events}))}
    ids = {v: i for i, v in enumerate(vertices)}
    with packed.open("wb") as stream:
        for u, v, t in sorted(events, key=lambda e: e[2]):
            stream.write(struct.pack("<iii", ids[u], ids[v], ranks[t]))
    return len(vertices)


def main(raw):
    root = Path(__file__).resolve().parent
    schedule = root/"data/otc-shuffled.txt"
    ref = json.loads((root/"data/otc-replay.json").read_text())
    if fingerprint(schedule) != ref["schedule_sha256"]:
        raise ValueError("Unexpected source schedule")
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        if raw is None:
            raw = work/"ratings.csv.gz"
            urlretrieve("https://snap.stanford.edu/data/soc-sign-bitcoinotc.csv.gz", raw)
        if fingerprint(raw) != ref["raw_sha256"]:
            raise ValueError("Unexpected raw graph")
        graph = work/"contacts.bin"
        vertices = pack_events(raw, graph)
        if fingerprint(graph) != ref["input_sha256"]:
            raise ValueError("Unexpected packed graph")
        for method, expected in ref["builds"].items():
            output = work/"answers.bin"
            cmd = [root/"build/source_cache.exe", graph, str(vertices), schedule, str(ref["budget_bytes"]), method, output]
            count, hits, builds, _, _, _, elapsed = subprocess.check_output(cmd, text=True).split()
            if int(builds) != expected or int(count) != 512 or fingerprint(output) != ref["answer_sha256"]:
                raise ValueError(f"Mismatch for {method}")
            print(f"{method}: {count} answers, {hits} cache hits, {builds} builds, {float(elapsed):.4f} s")


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("raw", type=Path, nargs="?")
    main(cli.parse_args().raw)
