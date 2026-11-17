

import argparse
import csv
import json
from pathlib import Path
import random
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from expanded_point_check import digest


def run(program, results, cache, output):
    graphs = "otc college email math higgs ubuntu coin comment flight".split()
    jobs = [(graph, repeat) for graph in graphs for repeat in range(3)]
    random.Random(20261109).shuffle(jobs)
    identities = {}
    binary_hash = digest(program)
    records = []
    with TemporaryDirectory() as scratch:
        wire = Path(scratch) / "answers.rows"
        for position, (graph, repeat) in enumerate(jobs):
            key = "positive-" + graph
            spec_file = results / "expansion/workloads" / key
            workload = spec_file.with_suffix(".txt")
            spec = json.loads(spec_file.with_suffix(".json").read_text())
            ref = json.loads(
                (results / "expansion/runs" / key / "0-mix.json").read_text()
            )
            packed = cache / (graph + ".bin")
            if graph not in identities:
                identities[graph] = (digest(packed), digest(workload))
            input_hash, query_hash = identities[graph]
            if (input_hash, query_hash) != (
                ref["identity"]["input"],
                ref["identity"]["queries"],
            ):
                raise ValueError(key + " input or query mismatch")
            
            modes = ("mixed", "point") if position % 2 == 0 else ("point", "mixed")
            for ordinal, mode in enumerate(modes):
                with packed.open("rb") as source:
                    while source.read(4 << 20):
                        pass
                command = [
                    str(program),
                    str(packed),
                    str(spec["vertices"]),
                    str(spec["source"]),
                    str(spec["release_row"]),
                    str(workload),
                    str(wire),
                    mode,
                ]
                start = perf_counter()
                response = subprocess.check_output(command, text=True)
                wall = perf_counter() - start
                requests, rows, space, build, service = response.split()
                actual = digest(wire)
                if (int(requests), int(rows), actual) != (
                    ref["requests"],
                    ref["rows"],
                    ref["identity"]["answer"],
                ):
                    raise ValueError(key + "/" + mode + " output mismatch")
                records.append(
                    dict(
                        graph=graph,
                        repeat=repeat,
                        position=position,
                        ordinal=ordinal,
                        method=mode,
                        requests=requests,
                        rows=rows,
                        retained_bytes=space,
                        build_s=build,
                        service_s=service,
                        wall_s=wall,
                        answer_sha256=actual,
                        binary_sha256=binary_hash,
                        input_sha256=input_hash,
                        workload_sha256=query_hash,
                    )
                )
            print(position + 1, graph, repeat, flush=True)
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
