

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run(program, results, cache, output):
    records = []
    with TemporaryDirectory() as scratch:
        wire = Path(scratch) / "answers.rows"
        for graph in "otc college email math higgs ubuntu coin comment flight".split():
            packed = cache / (graph + ".bin")
            input_hash = digest(packed)
            for cohort in range(4):
                key = f"{graph}-{cohort}"
                work = results / "full/workloads" / key
                query = work.with_suffix(".txt")
                spec = json.loads(work.with_suffix(".json").read_text())
                expected = json.loads(
                    (results / "full/runs" / key / "0-mix.json").read_text()
                )
                if (
                    input_hash != expected["identity"]["input"]
                    or digest(query) != expected["identity"]["workload"]
                ):
                    raise ValueError(key + " input or workload mismatch")
                args = [
                    str(program),
                    str(packed),
                    str(spec["vertices"]),
                    str(spec["source"]),
                    str(spec["release_row"]),
                    str(query),
                    str(wire),
                ]
                values = [
                    int(x) for x in subprocess.check_output(args, text=True).split()
                ]
                requests, rows, byte_count, nodes, states, intervals, searches = values
                measured = digest(wire)
                if (
                    measured != expected["answer_sha256"]
                    or rows != expected["rows"]
                    or requests != expected["requests"]
                ):
                    raise ValueError(key + " full output mismatch")
                mixed = subprocess.check_output(args + ["mixed"], text=True).split()
                comp_requests, comp_rows, component_bytes = map(int, mixed[:3])
                if (comp_requests, comp_rows, digest(wire)) != (
                    requests,
                    rows,
                    measured,
                ):
                    raise ValueError(key + " matched component output mismatch")
                records.append(
                    dict(
                        graph=graph,
                        cohort=cohort,
                        requests=requests,
                        rows=rows,
                        expanded_bytes=byte_count,
                        component_bytes=component_bytes,
                        constructed_nodes=nodes,
                        retained_states=states,
                        birth_range_tests=intervals,
                        time_search_tests=searches,
                        answer_sha256=measured,
                        input_sha256=input_hash,
                        query_sha256=expected["identity"]["workload"],
                    )
                )
            print(graph, flush=True)
    with output.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("program", "results", "cache", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    run(args.program.resolve(), args.results, args.cache, args.output)
