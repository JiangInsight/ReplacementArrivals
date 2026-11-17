

from collections import Counter
import csv
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]/'reference/supplement'
GRAPHS = {
    "otc": "OTC",
    "college": "College",
    "email": "email-Eu",
    "math": "MathOverflow",
    "higgs": "Higgs",
    "ubuntu": "Ask Ubuntu",
    "coin": "Coin",
    "comment": "Comment",
    "flight": "Flight",
}


def read(name):
    with (ROOT / name).open(newline="") as source:
        return list(csv.DictReader(source))


def summarize():
    audit = read("expanded_point_runs.csv")
    timings = read("expanded_point_timings.csv")
    assert len({(r["graph"], r["cohort"]) for r in audit}) == len(audit) == 36
    assert (
        len({(r["graph"], r["repeat"], r["method"]) for r in timings})
        == len(timings)
        == 54
    )
    assert all(r["requests"] == "2000" for r in timings)
    for key in ("binary_sha256",):
        assert len({r[key] for r in timings}) == 1
    assert all(
        v == 3 for v in Counter((r["graph"], r["method"]) for r in timings).values()
    )
    for name in ("requests", "rows", "birth_range_tests", "time_search_tests"):
        print(name, sum(int(r[name]) for r in audit))
    ratios = [int(r["expanded_bytes"]) / int(r["component_bytes"]) for r in audit]
    print(
        "bytes point/mixed minimum, median, maximum, greater",
        min(ratios),
        median(ratios),
        max(ratios),
        sum(v > 1 for v in ratios),
    )
    line_ratios = {field: [] for field in ("build_s", "service_s", "wall_s")}
    clears = {field: [0, 0] for field in line_ratios}
    pairs = {field: [] for field in line_ratios}
    lines = []
    for graph, label in GRAPHS.items():
        arm = {
            m: sorted(
                (r for r in timings if r["graph"] == graph and r["method"] == m),
                key=lambda r: r["repeat"],
            )
            for m in ("mixed", "point")
        }
        for left, right in zip(arm["mixed"], arm["point"]):
            assert all(
                left[f] == right[f]
                for f in (
                    "rows",
                    "answer_sha256",
                    "workload_sha256",
                    "input_sha256",
                    "position",
                )
            )
            assert left["ordinal"] != right["ordinal"]
        fields = []
        for field in line_ratios:
            mixed = [float(r[field]) for r in arm["mixed"]]
            point = [float(r[field]) for r in arm["point"]]
            ratio = median(point) / median(mixed)
            line_ratios[field].append(ratio)
            clears[field][0] += min(point) > max(mixed)
            clears[field][1] += min(mixed) > max(point)
            pairs[field].extend(p / m for p, m in zip(point, mixed))
            if field == "service_s":
                service_ms = (1000 * median(mixed), 1000 * median(point))
            fields.append(ratio)
        lines.append(
            label
            + " & "
            + f"{service_ms[0]:.2f} & {service_ms[1]:.2f} & "
            + " & ".join(f"{v:.2f}" for v in fields)
            + r" \\"
        )
    for key, ratios in line_ratios.items():
        print(
            key,
            "point/mixed median",
            median(ratios),
            "higher in",
            sum(v > 1 for v in ratios),
            "nonoverlap mixed/point",
            clears[key],
            "paired range",
            min(pairs[key]),
            max(pairs[key]),
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    rows = summarize()
    print(rows, end="")
