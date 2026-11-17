
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="unpacked paper3 artifact")
    parser.add_argument("cache", type=Path, help="prepared data and answer cache")
    parser.add_argument("action", choices=("build", "exact", "measure"))
    parser.add_argument("output", type=Path, help="path for the measurement ledger")
    args = parser.parse_args()
    root, cache = args.root.resolve(), args.cache.resolve()
    workspace = Path(os.environ.get("PAPER3_WORKSPACE", root/".work"))
    source = root / "study" / "timetable.cpp"
    executable = cache / "scheduled-review.exe"
    if args.action == "build":
        code = source.read_text()
        marker = 'if(arm=="csa"){'
        assert code.count(marker) == 1 and code.count("int main(") == 1
        code = code.replace("int main(", '#include "scheduled_repair.hpp"\nint main(')
        code = code.replace(marker, 'if(arm=="repair"){\n'
                            'ScheduledRepair index(legs,order,g.n,src,start);run(index);\n'
                            '}else ' + marker)
        
        
        assert code.count("built=construction;") == 1
        code = code.replace("built=construction;", "built=construction, served=construction;")
        end_loop = "    };\n    if(arm=="
        assert code.count(end_loop) == 1
        code = code.replace(end_loop, "        served=Clock::now();\n" + end_loop)
        anchor = '<<",\\"components\\":["'
        assert code.count(anchor) == 1
        code = code.replace(anchor, '<<",\\"loop_s\\":"<<std::chrono::duration<double>'
                                    '(served-built).count()' + anchor)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "scheduled.cpp"
            path.write_text(code)
            header = Path(__file__).with_name("scheduled_repair.hpp")
            (path.parent / header.name).write_bytes(header.read_bytes())
            subprocess.run([str(root / "study/build.bat"), str(root / "vendor/tglib"),
                            str(executable), str(path)], check=True)
        return

    if args.action == "exact":
        os.environ["PAPER3_CACHE"] = str(cache)
        sys.path.insert(0, str(root / "study"))
        import timetables
        def invoke(legs, n, src, release, queries, horizon, arm, stem):
            subprocess.run([executable, legs, str(n), str(src), str(release), queries,
                            str(horizon), arm, stem], check=True, capture_output=True)
        timetables.ARMS = ["repair"]
        timetables.invoke = invoke
        legacy_hash = timetables.sha
        timetables.sha = lambda path: (legacy_hash(executable) if path == cache / "timetable.exe"
                                       else legacy_hash(path))
        with tempfile.TemporaryDirectory() as td:
            timetables.OUT = Path(td)
            timetables.exact()
            report = json.loads((Path(td) / "correctness.json").read_text())
            report["binary"] = sha(executable)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
        return

    read = lambda path: json.loads(path.read_text())
    records = []
    binary_hash = sha(executable)
    with tempfile.TemporaryDirectory(dir=cache) as td:
        stem = Path(td) / "out"
        for city in "berlin bordeaux detroit kuopio paris sydney winnipeg".split():
            inputs = workspace / "results/full/timetables"
            meta = read(inputs / f"{city}-input.json")
            legs = cache / (city + ".legs")
            assert sha(legs) == meta["packed_sha256"]
            for case in range(3):
                session = read(inputs / f"{city}-{case}.json")
                qfile = inputs / f"{city}-{case}.txt"
                assert sha(qfile) == session["query_sha256"]
                for suite in (["online", "census"] if case == 0 else ["online"]):
                    key = f"{city}-{case}-{suite}"
                    
                    expected = read(inputs / "runs" / (key + "-0-csa.json"))["sha256"]
                    for rep in range(3 if suite == "online" else 1):
                        arms = ["mix", "repair"] if suite == "online" else ["repair"]
                        random.Random(f"schedule-repair/{key}/{rep}").shuffle(arms)
                        for position, arm in enumerate(arms):
                            cmd = [executable, legs, str(meta["vertices"]), str(session["source"]),
                                   str(session["release"]), qfile if suite == "online" else "ALL",
                                   str(meta["max_time"]), arm, stem]
                            start = time.perf_counter()
                            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
                            elapsed = time.perf_counter() - start
                            assert sha(stem.with_suffix(".rows")) == expected, (key, arm)
                            records.append(dict(**json.loads(process.stdout), wall_s=elapsed, city=city,
                                                case=case, suite=suite, rep=rep, position=position,
                                                arm=arm, answer_sha256=expected))
    args.output.write_text(json.dumps(dict(executable_sha256=binary_hash, runs=records),
                                      indent=1) + "\n")


if __name__ == "__main__":
    main()
