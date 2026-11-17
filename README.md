# Output-Sensitive Replacement Arrivals in Temporal Contact Streams

A withdrawal query removes one contact and returns each delayed recipient with its original and replacement arrival times.

![Construction and query processing for replacement arrivals.](figures/overview.png)

The stream constructor builds dependency histories and a reporting forest. Each component selects an explicit, direct or catalog encoding. Independent queries resolve a withdrawn record, apply the deadline, and return changed arrival times.

## A withdrawal query

Rows in [contacts.csv](data/contacts.csv) are numbered from zero. The first [query](data/queries.tsv) withdraws row 1, the contact from vertex 1 to vertex 2 at time 2, with deadline 7. Two recipients change:

| Recipient | Original arrival | Replacement arrival |
|---:|---:|---:|
| 2 | 2 | 5 |
| 4 | 3 | 6 |

Run all seven queries on x64 Windows with Visual Studio C++ Build Tools, Git and Python 3.11+:

```powershell
.\build.cmd
python run_example.py
```

The component index and the time-expanded dominator index each return the same rosters as chronological replay.

For the full OTC input and six matched baselines:

```powershell
python -m pip install -r requirements.txt
python reproduce.py benchmark --graphs otc --suite direct
python reproduce.py summary
```

[Reproduction commands and experiment map](docs/reproduction.md) · [Baselines and ablations](docs/baselines.md) · [Data and third-party sources](THIRD_PARTY.md)

Across 36 source sessions, the component index used less space in 35. The median ratio of expanded to component bytes was **2.48**. On nine logs the corresponding median service-time ratio was **1.03**, with overlapping three-run ranges on every log. [Space](data/session-space.csv) · [Service time](data/matched-runs.csv)

With a 16 MiB budget on Ask Ubuntu, the component index served four interleaved sources with 4 builds. The expanded index built 22 times and local repair built 24 times. All three built four times with unlimited retention. [Cache measurements](data/source-cache.csv)

Run `python run_cache_example.py` after the build to replay the 1 MiB Bitcoin OTC schedule. The script downloads the public ratings file and checks all 512 answers for each method. [Bitcoin OTC at SNAP](https://snap.stanford.edu/data/soc-sign-bitcoin-otc.html)

`python validate_release.py` rebuilds the release and verifies independent correctness checks, the complete OTC comparisons and the original grouped/shuffled cache requests. It records fresh results separately from the paper measurements.

[Verified release](verification/release-check.json) · [Source checksums](verification/source-sha256.json)
