#include "components.hpp"
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <string>

struct PointStateIndex {
    struct State {
        int time, tour;
    };
    struct Birth {
        int tour, vertex, first, begin, end;
    };
    struct Marker {
        int enter, leave, first, last;
    };
    struct Counters {
        uint64_t ranges = 0, time_tests = 0;
    };

    RankDictionary dictionary;
    vector<State> timelines;
    vector<Birth> births;
    vector<Marker> markers;
    vector<int> min_birth;
    int base = 1;
    size_t expanded_nodes = 0;

    struct Builder {
        struct Node {
            int parent, jump, depth;
            bool dependent;
        };
        vector<Node> tree{{0, 0, 0, false}};

        int add(int p, bool dependent) {
            int j = tree[p].jump, k = tree[j].jump;
            int skip = tree[p].depth - tree[j].depth == tree[j].depth - tree[k].depth ? k : p;
            tree.push_back({p, skip, tree[p].depth + 1, dependent});
            return int(tree.size() - 1);
        }
        int lca(int a, int b) const {
            if (tree[a].depth < tree[b].depth)
                std::swap(a, b);
            while (tree[a].depth > tree[b].depth) {
                int jump = tree[a].jump;
                a = tree[jump].depth >= tree[b].depth ? jump : tree[a].parent;
            }
            while (a != b) {
                bool can_jump = tree[a].jump != tree[b].jump;
                a = can_jump ? tree[a].jump : tree[a].parent;
                b = can_jump ? tree[b].jump : tree[b].parent;
            }
            return a;
        }
    };

    PointStateIndex(const Contacts &graph, int source) {
        Witness witness(graph, source);
        Builder builder;
        vector<int> state(graph.n, -1), pending(graph.n, -1), touched;
        vector<vector<State>> timeline(graph.n);
        vector<std::pair<int, int>> event_nodes;
        state[source] = 0;
        for (int i = graph.begin; i < int(graph.edges.size());) {
            int t = graph.edges[i].t;
            touched.clear();
            do {
                const auto &e = graph.edges[i];
                if (state[e.u] >= 0 && state[e.v] != 0) {
                    int p = state[e.u];
                    if (witness.via[e.v] == i) {
                        p = builder.add(p, true);
                        event_nodes.emplace_back(i, p);
                    }
                    if (pending[e.v] < 0) {
                        touched.push_back(e.v);
                        pending[e.v] = state[e.v] < 0 ? p : builder.lca(state[e.v], p);
                    } else
                        pending[e.v] = builder.lca(pending[e.v], p);
                }
                ++i;
            } while (i < int(graph.edges.size()) && graph.edges[i].t == t);
            for (int v : touched) {
                int p = pending[v];


                if (builder.tree[p].dependent)
                    state[v] = builder.add(p, true);
                else
                    state[v] = 0;
                if (state[v] || !timeline[v].empty())
                    timeline[v].push_back({t, state[v]});
                pending[v] = -1;
            }
        }
        expanded_nodes = builder.tree.size();


        vector<int> size(expanded_nodes, 1), enter(expanded_nodes), next(expanded_nodes);
        for (int i = int(expanded_nodes) - 1; i > 0; --i)
            size[builder.tree[i].parent] += size[i];
        next[0] = 1;
        for (int i = 1; i < int(expanded_nodes); ++i) {
            int p = builder.tree[i].parent;
            enter[i] = next[p];
            next[p] += size[i];
            next[i] = enter[i] + 1;
        }
        size_t count = 0, eligible = 0;
        for (const auto &local : timeline) {
            count += local.size();
            eligible += !local.empty();
        }
        timelines.reserve(count);
        births.reserve(eligible);
        for (int v = 0; v < graph.n; ++v) {
            const auto &local = timeline[v];
            if (local.empty())
                continue;
            int begin = int(timelines.size());
            for (const auto &s : local)
                timelines.push_back({s.time, enter[s.tour]});
            births.push_back(
                {enter[local.front().tour], v, local.front().time, begin, int(timelines.size())});
        }
        std::sort(births.begin(), births.end(),
                  [](const Birth &a, const Birth &b) { return a.tour < b.tour; });
        auto first_at = [&](int pos) {
            return int(std::lower_bound(births.begin(), births.end(), pos,
                                        [](const Birth &b, int key) { return b.tour < key; }) -
                       births.begin());
        };
        vector<std::pair<int, int>> keys;
        for (auto [event, node] : event_nodes) {
            int lo = enter[node], hi = lo + size[node], first = first_at(lo), last = first_at(hi);
            if (first == last)
                continue;
            keys.emplace_back(event, int(markers.size()));
            markers.push_back({lo, hi, first, last});
        }
        markers.shrink_to_fit();
        dictionary.build(keys);
        while (base < int(births.size()))
            base *= 2;
        min_birth.assign(2 * base, NEVER);
        for (int i = 0; i < int(births.size()); ++i)
            min_birth[base + i] = births[i].first;
        for (int i = base - 1; i; --i)
            min_birth[i] = std::min(min_birth[2 * i], min_birth[2 * i + 1]);
    }
    size_t bytes() const {
        return sizeof(*this) + dictionary.bytes() + timelines.capacity() * sizeof(State) +
               births.capacity() * sizeof(Birth) + markers.capacity() * sizeof(Marker) +
               min_birth.capacity() * sizeof(int);
    }
    void enumerate(const Marker &m, int h, int idx, int l, int r, vector<Row> &rows,
                   Counters &c) const {
        if (m.last <= l || r <= m.first)
            return;
        ++c.ranges;
        if (min_birth[idx] > h)
            return;
        if (r - l == 1) {
            const auto &b = births[l];

            int lo = b.begin + 1, hi = b.end;
            while (lo < hi) {
                ++c.time_tests;
                int mid = lo + (hi - lo) / 2, pos = timelines[mid].tour;
                if (m.enter <= pos && pos < m.leave)
                    lo = mid + 1;
                else
                    hi = mid;
            }
            int recovery = lo == b.end ? NEVER : timelines[lo].time;
            emit(rows, b.vertex, b.first, recovery, h);
            return;
        }
        int mid = l + (r - l) / 2;
        enumerate(m, h, idx * 2, l, mid, rows, c);
        enumerate(m, h, idx * 2 + 1, mid, r, rows, c);
    }
    void report(Query q, vector<Row> &rows, Counters &c) const {
        int idx = dictionary.find(q.event);
        if (idx >= 0)
            enumerate(markers[idx], q.deadline, 1, 0, base, rows, c);
    }
};

template <class Answer>
std::pair<uint64_t, uint64_t> serve(const char *query_file, const char *output_file,
                                    Answer answer) {
    std::ifstream qs(query_file);
    std::ofstream wire(output_file, std::ios::binary);
    Query q;
    uint64_t requests = 0, output = 0;
    while (qs >> q.event >> q.deadline) {
        vector<Row> rows;
        answer(q, rows);
        std::sort(rows.begin(), rows.end(),
                  [](const Row &a, const Row &b) { return a.vertex < b.vertex; });
        uint32_t n = uint32_t(rows.size());
        wire.write(reinterpret_cast<const char *>(&n), sizeof(n));
        if (n)
            wire.write(reinterpret_cast<const char *>(rows.data()), sizeof(Row) * n);
        ++requests;
        output += n;
    }
    wire.close();
    if (!qs.eof() || !wire)
        throw std::runtime_error("query or answer I/O failed");
    return {requests, output};
}

#ifndef ARRIVAL_INDEX_TYPES_ONLY
int main(int argc, char **argv) {
    if (argc != 7 && argc != 8)
        return 2;
    Contacts graph;
    graph.n = std::stoi(argv[2]);
    graph.begin = std::stoi(argv[4]);
    const auto bytes = std::filesystem::file_size(argv[1]);
    if (bytes % sizeof(Event))
        return 3;
    graph.edges.resize(bytes / sizeof(Event));
    std::ifstream input(argv[1], std::ios::binary);
    input.read(reinterpret_cast<char *>(graph.edges.data()), std::streamsize(bytes));
    if (!input)
        return 4;
    const int source = std::stoi(argv[3]);
    const std::string mode = argc == 8 ? argv[7] : "audit";
    using Seconds = std::chrono::duration<double>;
    auto start = Clock::now();
    auto finish = [&](auto &index, auto answer) {
        double build = Seconds(Clock::now() - start).count();
        vector<Event>().swap(graph.edges);
        auto begin = Clock::now();
        auto [requests, rows] = serve(argv[5], argv[6], answer);
        double service = Seconds(Clock::now() - begin).count();
        std::cout << std::setprecision(12) << requests << " " << rows << " " << index.bytes() << " "
                  << build << " " << service << "\n";
    };
    if (mode == "mixed") {
        ComponentIndex index(graph, source, ComponentIndex::MIXED);
        finish(index, [&](Query q, vector<Row> &rows) {
            Work unused;
            index.report(q, rows, unused);
        });
    } else if (mode == "point") {
        PointStateIndex index(graph, source);
        finish(index, [&](Query q, vector<Row> &rows) {
            PointStateIndex::Counters unused;
            index.report(q, rows, unused);
        });
    } else if (mode == "audit") {
        PointStateIndex index(graph, source);
        vector<Event>().swap(graph.edges);
        PointStateIndex::Counters counts;
        auto [requests, output] = serve(
            argv[5], argv[6], [&](Query q, vector<Row> &rows) { index.report(q, rows, counts); });
        std::cout << requests << " " << output << " " << index.bytes() << " "
                  << index.expanded_nodes << " " << index.timelines.size() << " " << counts.ranges
                  << " " << counts.time_tests << "\n";
    } else
        return 5;
}
#endif
