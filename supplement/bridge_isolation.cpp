#include "components.hpp"
#include <iostream>
#include <string>

struct Counts {
    uint64_t sites = 0, hard = 0, local_comparisons = 0, bridge_comparisons = 0;
    uint64_t mask = 0, short_history = 0;
};

Contacts fixture(int depth, int leaves, int detours) {
    Contacts g{{}, 1 + depth + leaves, 0};
    for (int i = 0; i < depth; ++i)
        g.edges.push_back({i, i + 1, i + 1});
    for (int j = 0; j < leaves; ++j)
        g.edges.push_back({depth, depth + 1 + j, depth + 1});
    for (int r = 0; r < detours; ++r) {
        int parent = (depth - 1) * (detours - 1 - r) / std::max(1, detours - 1);
        for (int j = 0; j < leaves; ++j)
            g.edges.push_back({parent, depth + 1 + j, depth + 2 + r});
    }
    return g;
}

int binary_rank(const CascadeIndex &ix, const CascadeIndex::Site &s, int depth, Counts &ct) {
    int l = 0, r = s.count;
    while (l < r) {
        int m = l + (r - l) / 2;
        ++ct.local_comparisons;
        if (ix.entries[s.begin + m].second >= depth)
            l = m + 1;
        else
            r = m;
    }
    return l;
}

vector<Row> query(const CascadeIndex &ix, Query q, bool bridge, Counts &ct) {
    vector<Row> rows;
    int root = ix.dict.find(q.event);
    if (root < 0 || ix.sites[root].before > q.deadline)
        return rows;
    int depth = ix.entries[ix.sites[root].begin].second;
    vector<std::pair<int, int>> pending{{root, ix.sites[root].start_rank}};
    const CascadeIndex::Link zero{0, 0, 0, 0};
    while (!pending.empty()) {
        auto [i, rank] = pending.back();
        pending.pop_back();
        const auto &s = ix.sites[i];
        if (s.before > q.deadline)
            continue;
        const auto &here = (bridge && rank) ? ix.links[s.catalog + rank - 1] : zero;
        ++ct.sites;
        int local;
        if (ix.need(s)) {
            ++ct.hard;
            local = bridge ? here.local : binary_rank(ix, s, depth, ct);
        } else {
            if (s.count <= 8)
                ++ct.short_history;
            else
                ++ct.mask;
            local = ix.local_rank(s, depth, zero);
        }
        int recovery = local < s.count ? ix.entries[s.begin + local].first : NEVER;
        emit(rows, s.vertex, s.before, recovery, q.deadline);
        auto descend = [&](int child, int inherited) {
            if (child < 0)
                return;
            if (bridge && inherited < ix.sites[child].length) {
                ++ct.bridge_comparisons;
                if (ix.child_key(child, inherited) <= -depth)
                    ++inherited;
            }
            pending.emplace_back(child, inherited);
        };
        if (i != root)
            descend(s.right, here.right);
        descend(s.left, here.left);
    }
    return rows;
}

void canonical(vector<Row> &rows) {
    std::sort(rows.begin(), rows.end(), [](Row a, Row b) { return a.vertex < b.vertex; });
}
bool same(const vector<Row> &a, const vector<Row> &b) {
    if (a.size() != b.size())
        return false;
    for (size_t i = 0; i < a.size(); ++i)
        if (std::tie(a[i].vertex, a[i].before, a[i].after) !=
            std::tie(b[i].vertex, b[i].before, b[i].after))
            return false;
    return true;
}
int main() {
    std::cout
        << "depth,leaves,detours,hard_sites,augmented_keys,selected_catalog,requests,rows,visited_"
           "sites,hard_visits,short_visits,mask_visits,binary_key_tests,bridge_key_tests\n";
    for (int depth : {48, 128, 512})
        for (int detours : {1, 8, 16, 32}) {
            const int leaves = 32;
            auto graph = fixture(depth, leaves, detours);
            CascadeIndex ix(graph, 0, CascadeIndex::ADAPTIVE);
            ComponentIndex selected(graph, 0, ComponentIndex::MIXED);
            SuffixReplay oracle(graph, 0);
            Counts independent, linked;
            int requests = 0;
            uint64_t emitted = 0;
            for (int event = 0; event < depth; ++event)
                for (int h : {depth / 2, depth + 1 + detours}) {
                    Query q{event, h};
                    vector<Row> expected, original;
                    Work work;
                    oracle.report(q, expected, work);
                    ix.report(q, original, work);
                    auto a = query(ix, q, false, independent), b = query(ix, q, true, linked);
                    canonical(expected);
                    canonical(original);
                    canonical(a);
                    canonical(b);
                    if (!same(a, expected) || !same(b, expected) || !same(original, expected))
                        throw std::logic_error("complete answer mismatch");
                    ++requests;
                    emitted += expected.size();
                }
            if (independent.sites != linked.sites || independent.hard != linked.hard)
                throw std::logic_error("traversal mismatch");
            std::cout << depth << "," << leaves << "," << detours << "," << ix.hard_sites << ","
                      << ix.links.size() << "," << selected.root_counts[2] << "," << requests << ","
                      << emitted << "," << linked.sites << "," << linked.hard << ","
                      << linked.short_history << "," << linked.mask << ","
                      << independent.local_comparisons << "," << linked.bridge_comparisons << "\n";
        }
}
