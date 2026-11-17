
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
load = lambda p: json.loads(p.read_text())
graphs = dict(otc="Bitcoin OTC", college="CollegeMsg", email="email-Eu",
              math="MathOverflow", higgs="Higgs", ubuntu="Ask Ubuntu",
              coin="Coin", comment="Comment", flight="Flight")
lines = []
for graph, label in graphs.items():
    sessions = [load(root / "full/workloads" / f"{graph}-{i}.json") for i in range(4)]
    for i, item in enumerate(sessions):
        frozen = root / "full/workloads" / f"{graph}-{i}.txt"
        assert hashlib.sha256(frozen.read_bytes()).hexdigest() == item["workload_sha256"]
    for key in ("direct", "positive"):
        sampled = load(root / "expansion/workloads" / f"{key}-{graph}.json")
        assert sampled["source"] == sessions[0]["source"] and sampled["release_row"] == 0
    assert all(x["release_row"] == 0 for x in sessions[:3])
    fields = [label, *(str(x["source"]) for x in sessions),
              f'{sessions[3]["release_row"]:,}', f'{sessions[3]["release_time"]:,}']
    lines.append(" & ".join(fields) + r" \\")
print(r"""\begin{tabular}{@{}lrrrrrr@{}}
\toprule
&\multicolumn{4}{c}{Source ID}&\multicolumn{2}{c}{Release D}\\
\cmidrule(lr){2-5}\cmidrule(l){6-7}
Log & A & B & C & D & Record & Time rank\\
\midrule""")
print("\n".join(lines))
print(r"\bottomrule")
print(r"\end{tabular}")
