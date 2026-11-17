
import csv
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import time

GRAPHS = "otc college email math higgs ubuntu coin comment flight".split()
METHODS = "mix allpairs repair decremental".split()
PREFIXES = (1, 16, 128, 512, 1024, 2000, 4096, 8192)
EMPTY = bytes(4)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def census_answers(path, wanted, expected_positive):
    answer = {}
    count = 0
    buf = path.read_bytes()
    offset = 0
    while offset < len(buf):
        event, rows = struct.unpack_from("<II", buf, offset)
        end = offset + 8 + 12 * rows
        assert rows and end <= len(buf)
        if event in wanted:
            answer[event] = buf[offset + 4:end]
        count += 1
        offset = end
    assert count == expected_positive
    return answer


def benchmark(results, cache, out_file):
    exe = cache / "expanded.exe"
    binary_sha = digest(exe)
    with tempfile.TemporaryDirectory() as temp, out_file.open("w", newline="") as out:
        tmp = Path(temp)
        writer = None
        for graph in GRAPHS:
            base = read(results / "full/inputs" / (graph + ".json"))
            session = read(results / "expansion/workloads" / ("positive-" + graph + ".json"))
            census = read(results / "full/census" / (graph + "-0-end-mix.json"))
            inp = cache / (graph + ".bin")
            inp_sha = digest(inp)
            census_path = cache / "census-answers" / (graph + "-0-end.rows")
            assert digest(census_path) == census["sha256"]
            assert inp_sha == base["packed_sha256"] == session["input_sha256"]
            assert base["rows"] == census["eligible"] and session["release_row"] == 0
            assert session["positive_population"] == census["positive"]
            assert session["source"] == census["source"]
            archived = results / "expansion/workloads" / ("positive-" + graph + ".txt")
            assert digest(archived) == session["query_sha256"]
            conditioned = [tuple(map(int, s.split())) for s in archived.read_text().splitlines()]
            streams = {}
            for rep in range(3):
                rng = random.Random(f"deployment-v1/uniform/{graph}/{rep}")
                streams["uniform", rep] = [(rng.randrange(base["rows"]), census["deadline"]) for _ in range(8192)]
                streams["balanced", rep] = conditioned
            wanted = {e for qs in streams.values() for e, h in qs}
            answers = census_answers(census_path, wanted, census["positive"])
            for rep in range(3):
                cells = [(kind, method) for kind in ("uniform", "balanced") for method in METHODS]
                random.Random(f"deployment-v1/order/{graph}/{rep}").shuffle(cells)
                for kind, method in cells:
                    requests = streams[kind, rep]
                    assert all(h == census["deadline"] for e, h in requests)
                    queries = tmp / "queries.txt"
                    queries.write_text("".join(f"{e} {h}\n" for e, h in requests), encoding="ascii")
                    expected = b"".join(answers.get(e, EMPTY) for e, h in requests)
                    started = time.perf_counter()
                    subprocess.run([exe, inp, str(session["vertices"]), str(session["source"]), "0",
                                    queries, method, tmp / "out", tmp / "metrics"], check=True,
                                   capture_output=True, timeout=300)
                    wall = time.perf_counter() - started
                    assert (tmp / "out.rows").read_bytes() == expected
                    meta = read(tmp / "metrics")
                    with (tmp / "out.csv").open() as raw:
                        rows = list(csv.DictReader(raw))
                    assert len(rows) == len(requests)
                    summary = dict(graph=graph, workload=kind, rep=rep, method=method,
                                   source=session["source"], deadline=census["deadline"],
                                   records=base["rows"], positive_population=census["positive"],
                                   requests=len(requests), wall_s=wall, load_s=meta["load_s"],
                                   build_s=meta["build_s"], total_rows=sum(int(x["rows"]) for x in rows),
                                   input_sha256=inp_sha, query_sha256=digest(queries),
                                   expected_sha256=hashlib.sha256(expected).hexdigest(),
                                   binary_sha256=binary_sha)
                    service = []
                    positive = []
                    for i, (row, (e, h)) in enumerate(zip(rows, requests, strict=True)):
                        assert (int(row["i"]), int(row["event"]), int(row["deadline"])) == (i, e, h)
                        service.append(int(row["query_ns"]) + int(row["encode_ns"]))
                        positive.append(int(row["rows"]) > 0)
                    summary["positive_requests"] = sum(positive)
                    summary["positive_ns"] = sum(t for t, flag in zip(service, positive) if flag)
                    summary["empty_ns"] = sum(t for t, flag in zip(service, positive) if not flag)
                    for n in PREFIXES:
                        summary[f"service_ns_{n}"] = sum(service[:n]) if n <= len(requests) else ""
                    if writer is None:
                        writer = csv.DictWriter(out, fieldnames=summary)
                        writer.writeheader()
                    writer.writerow(summary)
                    out.flush()
            print(graph, "complete", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    benchmark(*(Path(s) for s in sys.argv[1:]))
