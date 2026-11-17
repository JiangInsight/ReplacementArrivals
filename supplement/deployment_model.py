
import argparse
import csv
import math
from pathlib import Path
from statistics import median

GRAPHS = "otc college email math higgs ubuntu coin comment flight".split()
METHODS = "mix allpairs repair decremental".split()
NAMES = ["BTC-OTC", "CollegeMsg", "email-Eu", "MathOverflow", "Higgs", "Ask Ubuntu", "Coin", "Comment", "Flight"]
LENGTHS = (1, 16, 128, 512, 1024, 2000, 4096, 8192)


def group_data(path):
    with path.open(encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 216
    by_cell = {}
    for g in GRAPHS:
        for workload in ("balanced", "uniform"):
            for method in METHODS:
                cell = sorted((r for r in rows if (r["graph"], r["workload"], r["method"]) ==
                               (g, workload, method)), key=lambda x: int(x["rep"]))
                assert [int(r["rep"]) for r in cell] == [0, 1, 2]
                for r in cell:
                    event_ns = int(r["positive_ns"]) + int(r["empty_ns"])
                    assert event_ns == int(r["service_ns_" + r["requests"]])
                    if workload == "balanced":
                        assert int(r["positive_requests"]) == 1000
                by_cell[g, workload, method] = cell
            for i in range(3):
                ref = by_cell[g, workload, "mix"][i]
                for m in METHODS:
                    alt = by_cell[g, workload, m][i]
                    for k in ("source", "deadline", "records", "positive_population", "requests",
                              "input_sha256", "query_sha256", "expected_sha256", "binary_sha256", "total_rows"):
                        assert ref[k] == alt[k]
    return by_cell


def estimates(rows):
    
    b = median(float(r["build_s"]) for r in rows) * 1e9
    e = median(int(r["empty_ns"]) / (int(r["requests"])-int(r["positive_requests"])) for r in rows)
    a = median(int(r["positive_ns"]) / int(r["positive_requests"]) for r in rows)
    return b, e, a


def interval(intercept, slope):

    if slope == 0:
        return (1, math.inf) if intercept <= 0 else None
    if slope < 0:
        return max(1, math.ceil(-intercept / slope)), math.inf
    last = math.floor(-intercept / slope)
    return (1, last) if last >= 1 else None


def interval_text(x):
    if x is None:
        return "never"
    start, stop = x
    if start == 1 and math.isinf(stop):
        return "all"
    return ">=" + str(start) if math.isinf(stop) else "<=" + str(stop)


def analyze(data):
    models = []
    empirical = []
    for g in GRAPHS:
        examples = data[g, "uniform", "mix"]
        prevalence = int(examples[0]["positive_population"]) / int(examples[0]["records"])
        pars = {m: estimates(data[g, "balanced", m]) for m in METHODS}
        for label, p in [("uniform", prevalence), *[(str(v), v) for v in (0, .01, .05, .1, .25, .5, .75, 1)]]:
            for method in METHODS:
                b, empty, affected = pars[method]
                mean = (1-p)*empty + p*affected
                mixb, mixempty, mixaffected = pars["mix"]
                mixmean = (1-p)*mixempty+p*mixaffected
                region = interval(mixb-b, mixmean-mean)
                models.append(dict(graph=g, prevalence=label, p=p, method=method, build_ms=b/1e6,
                                   empty_ns=empty, positive_ns=affected, mean_ns=mean,
                                   mix_no_slower=interval_text(region),
                                   **{f"cost_ms_{n}":(b+n*mean)/1e6 for n in LENGTHS}))
        for n in LENGTHS:
            for method in METHODS:
                rows = data[g, "uniform", method]
                prefix = [int(r[f"service_ns_{n}"])/1e6 for r in rows]
                cost = [float(r["build_s"])*1000+t for r,t in zip(rows,prefix)]
                empirical.append(dict(graph=g, method=method, n=n,
                                      measured_prefix_min_ms=min(cost), measured_prefix_median_ms=median(cost),
                                      measured_prefix_max_ms=max(cost), measured_service_median_ms=median(prefix),
                                      wall_median_ms=(median(float(r["wall_s"]) for r in rows)*1000 if n==8192 else "")))
    return models, empirical


def prevalence_regions(data):

    output = []
    for g in GRAPHS:
        pars = {m: estimates(data[g, "balanced", m]) for m in METHODS}
        mb, me, ma = pars["mix"]
        for n in LENGTHS:
            for method in METHODS[1:]:
                b, e, a = pars[method]
                at_zero = mb - b + n * (me - e)
                at_one = mb - b + n * (ma - a)
                if max(at_zero, at_one) <= 0:
                    lo, hi = 0.0, 1.0
                elif min(at_zero, at_one) > 0:
                    lo = hi = ""
                else:
                    threshold = -at_zero / (at_one - at_zero)
                    lo, hi = (threshold, 1.0) if at_one <= 0 else (0.0, threshold)
                output.append(dict(graph=g, n=n, method=method, minimum_p=lo, maximum_p=hi))
    return output


def save_csv(path, rows):
    with path.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)


def overview(data, models, empirical):
    for g,name in zip(GRAPHS,NAMES):
        mod = {(r["prevalence"], r["method"]):r for r in models if r["graph"]==g}
        obs = {(r["n"],r["method"]):r for r in empirical if r["graph"]==g}
        print(name,round(100*mod["uniform","mix"]["p"],4),
              'region [E,R,D] uniform,half',[(p,[mod[p,m]["mix_no_slower"] for m in METHODS[1:]]) for p in ("uniform","0.5")],
              'observed winners',[(n,min(METHODS,key=lambda m:obs[n,m]["measured_prefix_median_ms"])) for n in (1,128,8192)],
              'wall',min(METHODS,key=lambda m:obs[8192,m]["wall_median_ms"]),
              'observed/forecast service', [round(obs[8192,m]["measured_service_median_ms"]*1e6/(8192*mod["uniform",m]["mean_ns"]),2) for m in METHODS])
    for n in (1,128,8192):
        correct=0
        for g in GRAPHS:
            mr=[r for r in models if r["graph"]==g and r["prevalence"]=="uniform"]
            er=[r for r in empirical if r["graph"]==g and r["n"]==n]
            correct+=min(mr,key=lambda r:r[f"cost_ms_{n}"])["method"]==min(er,key=lambda r:r["measured_prefix_median_ms"])["method"]
        print(f"model agrees with empirical winners @ {n}: {correct}/9")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path)
    parser.add_argument("--export",type=Path,help="directory for per-graph model and measured-prefix CSVs")
    args=parser.parse_args()
    data=group_data(args.input)
    models,empirical=analyze(data)
    overview(data,models,empirical)
    if args.export:
        args.export.mkdir(parents=True,exist_ok=True)
        save_csv(args.export/"deployment_model.csv",models)
        save_csv(args.export/"deployment_measured.csv",empirical)
        save_csv(args.export/"deployment_prevalence.csv",prevalence_regions(data))
