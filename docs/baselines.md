# Methods and comparison contract

| CLI name | Implementation |
|---|---|
| `mix` | Stream dependency construction, monotone histories, birth reporting forest and per-component choice of explicit, direct or catalog representation |
| `tglib` | Unmodified author ordered-edge earliest-arrival routine from the pinned TGLib checkout, wrapped to mask one physical record |
| `incident` | Unmodified author TGLib incident-list routine with the same withdrawal and output adapter |
| `calendar` | Our FIFO time-dependent Dijkstra implementation with ordered-pair departure lists |
| `decremental` | Our specialization of Bilò et al., Section 4 Algorithm 2, with live incoming/outgoing cursors and epoch restoration between independent withdrawals |
| `repair` | Our witness-child repair and candidate incoming-record implementation |
| `equations` | Our priority-queue inconsistent-label repair implementation, following the Ramalingam–Reps formulation |
| `dag` | Our reachable time-expanded support propagation and rollback implementation |
| `dom`, `domfull` | Pruned and full expanded-DAG constructors feeding the same component encoder and reporter as `mix` |
| `point` | Independent expanded-state dominator reporter in `arrivals.exe`, using birth-range and time searches rather than the component depth-history reporter |
| `batch64` | Offline 64-scenario propagation; all withdrawal IDs and deadlines are supplied in advance |
| `csa` | Our departure-ordered connection scan with actual scheduled departure/arrival times and a witness rejection test |

Only the two TGLib engines use third-party implementation code. The other comparators are local implementations or adaptations, not author binaries. TGLib is credited in [THIRD_PARTY.md](../THIRD_PARTY.md). The decremental source is the [authors' November 2026 manuscript, Section 4](https://arxiv.org/html/2611.06387v1#S4); independent requests reset epochs, so a theorem for a permanent monotone deletion sequence is not attributed to this workload. Priority-queue label repair follows [Ramalingam and Reps (1996)](https://doi.org/10.1006/jagm.1996.0046). Ordered replay follows the standard temporal earliest-arrival formulation of [Wu et al. (2014)](https://doi.org/10.14778/2732939.2732945).

Every instantaneous contact at rank `t` receives unit traversal time in the TGLib adapters; returned arrival ranks are shifted back by one. Ordered TGLib checks a departure upper bound and receives `H`; incident TGLib checks an arrival upper bound and receives `H+1`. Both include original arrivals exactly at `H`, preserve duplicate identities and enforce strictly increasing original ranks. Baselines share a safe chosen-witness rejection test. The index uses its event dictionary. Initialization, retained input and sorting/encoding are included under their respective reported clocks.

The six removals are `without-explicit`, `without-direct`, `without-catalog`, `without-uniform`, `without-prune` and `without-links`. The first three forbid one candidate and select among the remainder. `without-uniform` expands the direct representation while preserving choices. `without-prune` removes traversal skips while preserving output conditions. `without-links` changes the whole catalog lookup backend, including short/mask paths; its effect cannot be attributed solely to sampled bridges. `global` forces one encoding across the forest, and `allpairs` forces materialization. The bridge-isolation experiment holds visited sites and queries fixed before counting lookup comparisons.

All completed arms compare ordered recipient and time triples, not just counts. Native runs are single threaded, with matched input, source, release, withdrawal and deadline. Process time includes loading, construction, queries, serialization and teardown. The per-request generation clock excludes sorting and writing; the encoding clock includes them. The independent reporter and cache driver instead measure their full service loop. Downloading and preprocessing are outside timed runs. Input hashing warms the filesystem cache; these results do not measure cold-disk reads.
