# Reproducing the study

Use 64-bit Windows, Visual Studio C++ Build Tools with the Desktop C++ workload and Windows SDK, Python 3.11 or newer, and Git. The release check uses Python 3.13 and MSVC x64. Native engines are single threaded. The build fetches TGLib at a fixed revision and verifies all required source hashes; no system TGLib installation is needed. `python fetch_dependencies.py` can perform this step separately. Its downloaded checkout is ignored by Git and keeps the original upstream license and notices.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python reproduce.py build
.venv\Scripts\python reproduce.py prepare --graphs otc
.venv\Scripts\python reproduce.py benchmark --graphs otc --suite direct
.venv\Scripts\python reproduce.py summary
```

OTC uses all 35,592 records and 5,881 vertices. `--graphs all` selects the nine complete logs. Data are downloaded from the original public services, checked against fixed raw hashes, and transformed into packed inputs with matching published hashes. The four seeded 128-request streams must also match the archived files byte for byte. `.work` contains downloads, cache, fresh results and plots. `--work PATH` selects a separate workspace. Rebuilding a changed binary requires a new workspace; incompatible cached runs are rejected.

| Input | Records | Vertices | Distinct timestamps |
|---|---:|---:|---:|
| OTC | 35,592 | 5,881 | 35,592 |
| CollegeMsg | 59,835 | 1,899 | 58,911 |
| email-Eu | 332,334 | 986 | 207,880 |
| MathOverflow | 506,550 | 24,818 | 505,784 |
| Higgs | 563,069 | 304,691 | 194,437 |
| Ask Ubuntu | 964,437 | 159,316 | 960,866 |
| Coin | 22,809,486 | 638,486 | 1,295,720 |
| Comment | 44,314,507 | 994,790 | 30,998,030 |
| Flight | 67,169,570 | 18,143 | 1,385 |

Budget at least 16 GiB RAM for the large-log study and additional disk for raw exports, packed files and canonical answer streams. Direct incident-list runs on the largest logs may reach the documented 45 s cap. The full suite intentionally includes these censored runs. Flight has daily timestamps; the separate seven-city experiment supplies actual departure and arrival times.

`python validate_release.py` rebuilds everything and checks the four exhaustive/random/adversarial regression suites, scheduled connections, all short OTC comparisons and the original source-cache schedules. It writes `.work-validation/validation.json` and individual logs. This is a release test, not a rerun of every paper measurement. The independent Python oracle freezes all senders in a timestamp group before updating recipients. It checks complete recipient and arrival triples, including duplicates, simultaneous contacts, releases, deadlines, unreachable records and missing replacements. The scheduled oracle enumerates paths on 63 small instances.

## Paper-to-command map

Commands below use `python` from the installed environment and default to three repetitions unless stated otherwise. All timing runs are serial. Large-log scans, censuses and source sampling can be lengthy; do not run competing workloads concurrently when collecting performance data.

| Paper evidence | Command after preparation | Implementations and outputs |
|---|---|---|
| Direct baseline table: eight empty and eight nonempty requests | `python reproduce.py benchmark --graphs all --suite direct` | TGLib ordered/incident, FIFO, decremental, repair, mixed; `results/expansion/runs/direct-*`; 45 s process cap |
| Original 36 source/release sessions | `python reproduce.py benchmark --graphs all --suite sessions` | Ten online engines and 64-way offline batch; `results/full/runs`, `results/batch` |
| Balanced 2,000-request service figure | `python reproduce.py benchmark --graphs all --suite conditioned` | Exact full-deadline census, 1,000 affected and 1,000 empty withdrawals; mixed/no-pruning/decremental/repair; `positive-*` |
| Constructor figure | `python reproduce.py benchmark --graphs all --suite constructors` | Stream, pruned DAG and full DAG with the same downstream encoder; `mix`, `dom`, `domfull` |
| Nested record/vertex scaling figure | `python reproduce.py benchmark --graphs math coin --suite scale` | 20/40/60/80/100 percent, seed 2519, 64 matched queries; `scale-*` |
| Independent expanded-state comparison, 36 sessions | `python reproduce.py benchmark --graphs all --suite reporters` | Two independent reporters in one binary, shared dictionary/output contract; `results/reporters` |
| Independent reporters on balanced workloads | `python reproduce.py benchmark --graphs all --suite reporters-conditioned` | Run `conditioned` first; `results/reporters-conditioned` |
| Six mechanism removals plus global/explicit controls | `python reproduce.py benchmark --graphs all --suite ablation` | Cohorts 0 and 2, identical 128-request streams; `abl-*` |
| Output-size and deadline figure | `python reproduce.py benchmark --graphs all --suite size` | Up to 24 distinct withdrawals per six size bins, three cutoffs, exact clipped census answers; `size-*` |
| Withdrawal prevalence and maximum output census | `python reproduce.py census --graphs all` | Every record, active and lower-quartile sources, middle/final deadlines; mixed and repair must agree |
| Source sensitivity | `python reproduce.py benchmark --graphs college email math --suite sources` | 100 sampled sources and ten most active senders; 32 queries, one run per source and engine |
| Nonempty latency p99 table | `python reproduce.py benchmark --graphs math coin flight --suite long` | Three 2,048-request seeds, three repetitions, mixed/repair/explicit; raw per-query CSV |
| Structured synthetic controls | `python reproduce.py benchmark --suite synthetic` | Shared, staircase, sparse and mixed dependency families at multiple depths |
| Catalog bridge isolation | `build\bridge_isolation.exe` | Twelve fixtures, two lookup backends and full replay; CSV on stdout |
| Seven-city scheduled-contact table | `python reproduce.py timetables` | Public full-day connections, three 256-query settings and all-leg census; mixed/global/explicit/connection scan |
| Source reuse under retention budgets | `python reproduce.py cache --graphs otc college email math higgs ubuntu` | Original grouped/shuffled schedules, five budgets, three reporters; `results/cache` |

For the long-session table, `python supplement/latency_check.py .work/results` checks per-query ledgers and computes nonempty p99 using rank `ceil(.99*(n-1))`. After scaling, `python supplement/latency_repeat.py .work/results .work/cache build/latency_clock.exe` runs the eight adjacent, order-balanced full-Coin constructor pairs and records the timer probe. Full-Coin endpoints contain identical input and are not independent dataset samples.

For a small synthetic run, append `--fixtures shared64 mixed128 --repeats 1` to the synthetic command. The paper's four ablation controls can be selected as `--fixtures shared1024 stairs256 sparse2048 mixed2048`; the synthetic suite includes all six mechanism removals on each selected fixture.

For scheduled witness repair:

```powershell
python supplement/scheduled_control.py . .work/cache build .work/scheduled-exact.json
python supplement/scheduled_control.py . .work/cache exact .work/scheduled-exact.json
python supplement/scheduled_control.py . .work/cache measure .work/scheduled-runs.json
python supplement/scheduled_summary.py .work/results .work/scheduled-runs.json
```

The `measure` command requires all seven city runs first. `build` instruments the same scheduled source and adds the departure-aware repair comparator. A custom workspace must also set `PAPER3_WORKSPACE` and `PAPER3_CACHE` for standalone supplementary scripts.

For detailed representation and retained-memory audits, run `python supplement/layout_audit.py build`, then `profile`, `synthetic`, `windows`, or `peak`, optionally followed by graph names where supported. `python supplement/layout_repair.py --measure` measures repair/decremental allocations. These use prepared real and scheduled inputs; the full profile includes the generated stress inputs. The profile reports vector capacities, dictionary storage, object headers and peak working set separately. Do not compare retained-index bytes to process memory or charge common input only to one algorithm.

`python supplement/deployment_run.py .work/results .work/cache .work/deployment.csv` replays uniform and balanced prefixes after the conditioned/census suite. `python supplement/deployment_model.py .work/deployment.csv --export .work/deployment-summary` produces prefix and amortization summaries. It requires all nine inputs; workload-conditioned break-even estimates are not natural request-log claims.

## Results and figures

`python reproduce.py summary` produces `summary/runs.csv`, `summary/medians-and-ranges.csv`, and PDF/PNG process-time plots. Every plot compares methods on one suite and one fixed workload. Timeouts remain labeled records and are excluded from medians; skipped repetitions are not zeros. Per-query CSVs retain generation and encoding times. Timed engines are checked against identical canonical answer bytes after the timed process exits.

`reference` contains the original measurements, input/workload manifests and source-cache schedules. `data/session-space.csv`, `data/matched-runs.csv` and `data/source-cache.csv` support the concise README results. New measurements are written only under the selected workspace and must not be substituted into archived tables without explicitly reporting the new machine, binary and run protocol.

`python plot_reference.py` regenerates the paper's four evaluation figures from the archived source data into `.work/reference-plots`. It does not rerun the experiments. The main method diagram is reproducible with `python figures/overview.py --out .work/method-figure --preview`. Fresh-run plots come from `reproduce.py summary` and stay separate.

Contact answers contain a little-endian uint32 count for every request followed by sorted int32 `(recipient, original, replacement)` triples. `-1` denotes no replacement by the deadline. Census/scheduled answers store `(record-or-query-ordinal, count, triples)` only for nonempty outputs. Input IDs are zero based after stable sorting; `*-ids.npz` maps ranked timestamps, vertices and physical records back to source values. Withdrawals are independent and do not mutate the retained index.
