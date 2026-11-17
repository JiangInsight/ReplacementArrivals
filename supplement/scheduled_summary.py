
from collections import Counter
import json
from pathlib import Path
from statistics import median
import sys

here = Path(__file__).resolve().parent
results = Path(sys.argv[1])
ledger = Path(sys.argv[2]) if len(sys.argv) > 2 else here.parent / 'reference/supplement/scheduled_runs.json'
runs = json.loads(ledger.read_text())["runs"]
assert len(runs) == 133
census = [r for r in runs if r["suite"] == "census"]
assert len(census) == 7
print("Census:", [sum(r[key] for r in census) for key in ("requests","positive","rows","recovered")])
wins, disjoint = Counter(), Counter()
for city in sorted({r["city"] for r in census}):
    folder = results / "full/timetables/runs"
    for r in (r for r in runs if r["city"] == city):
        ref = json.loads((folder / f'{city}-{r["case"]}-{r["suite"]}-0-csa.json').read_text())
        assert ref["sha256"] == r["answer_sha256"]
        assert all(ref[k] == r[k] for k in ("requests","positive","rows","recovered"))
    ratios = []
    for case in range(3):
        group = [r for r in runs if r["suite"] == "online" and r["city"] == city and r["case"] == case]
        assert len(group) == 6 and {r["requests"] for r in group} == {256}
        metrics = ("loop_s","service_s","wall_s") if "loop_s" in group[0] else ("service_s","wall_s")
        for metric in metrics:
            times = {arm: [r[metric] for r in group if r["arm"] == arm] for arm in ("mix","repair")}
            assert all(len(v) == 3 for v in times.values())
            faster = min(times, key=lambda a: median(times[a]))
            wins[(metric,faster)] += 1
            if max(times[faster]) < min(times["mix" if faster == "repair" else "repair"]):
                disjoint[(metric,faster)] += 1
            if metric == "wall_s":
                ratios.append(median(times["repair"])/median(times["mix"]))
    print(city, "repair / index wall ratios by source:", *(f"{x:.3f}" for x in ratios))
print("wins", dict(wins), "disjoint ranges", dict(disjoint))
