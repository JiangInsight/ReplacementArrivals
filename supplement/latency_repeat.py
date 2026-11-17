




import argparse
import datetime
import hashlib
import json
import platform
import random
import subprocess
import tempfile
import time
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def run(results, cache, clock):
    rng_seed = 86273
    order = [("contacts", "vertices"), ("vertices", "contacts")] * 4
    random.Random(rng_seed).shuffle(order)
    coin = cache / "coin.bin"
    exe = cache / "expanded.exe"
    reference = read_json(results/"expansion/runs/scale-coin-contacts-100/0-mix.json")
    expected = reference["identity"]
    assert digest(coin) == expected["input"] and digest(exe) == expected["binary"]
    queries = {}
    for variant in ["contacts", "vertices"]:
        key = f"scale-coin-{variant}-100"
        spec = read_json(results/"expansion/workloads"/(key + ".json"))
        queries[variant] = results/"expansion/workloads"/(key + ".txt")
        assert (spec["vertices"],spec["source"],spec["release_row"]) == (638486,91,0)
        assert digest(queries[variant]) == expected["queries"]
    stamps = {"utc_start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "platform": platform.platform(), "random_seed": rng_seed, "original_identity": expected,
              "clock_executable_hash": digest(clock), "clock": [], "pairs": []}
    for _ in range(3):
        proc = subprocess.run([str(clock)], capture_output=True, check=True, text=True)
        stamps["clock"].append(json.loads(proc.stdout))
    with tempfile.TemporaryDirectory() as folder:
        stem = Path(folder)/"probe"
        stats = Path(folder)/"stats.json"
        for pair, variants in enumerate(order):
            trials = []
            for variant in variants:
                start = time.perf_counter()
                subprocess.run([str(exe), str(coin), "638486", "91", "0", str(queries[variant]),
                                "mix", str(stem), str(stats)], capture_output=True, check=True)
                elapsed = time.perf_counter() - start
                metrics = read_json(stats)
                assert digest(stem.with_suffix(".rows")) == expected["answer"]
                trials.append({"label":variant, "build_s":metrics["build_s"], "wall_s":elapsed})
            stamps["pairs"].append({"pair":pair, "order":variants, "trials":trials})
    stamps["utc_end"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return stamps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("results", "cache", "clock"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.results.resolve(), args.cache.resolve(), args.clock.resolve()), indent=2))
