
struct ScheduledRepair {
    const vector<Leg>& legs;
    vector<int> base, witness, replacement;
    vector<unsigned char> changed;
    vector<vector<int>> incoming, children;

    ScheduledRepair(const vector<Leg>& records, const vector<std::pair<int,int>>& order,
                    int n, int source, int release)
        : legs(records), base(n, NEVER), witness(n, -1), replacement(n),
          changed(n), incoming(n), children(n) {
        base[source] = release - 1;
        for (auto [departure, i] : order) {
            const auto& e = legs[i];
            if (base[e.u] < departure && e.arrival < base[e.v]) {
                base[e.v] = e.arrival;
                witness[e.v] = i;
            }
        }
        
        
        for (int i = 0; i < int(legs.size()); ++i) {
            const auto& e = legs[i];
            if (release <= e.departure && base[e.u] < e.departure)
                incoming[e.v].push_back(i);
        }
        for (auto [departure, i] : order)
            if (witness[legs[i].v] == i) children[legs[i].u].push_back(i);
    }

    void report(Query q, vector<Row>& out, Work& work) {
        const auto& failed = legs[q.event];
        if (failed.arrival > q.deadline || witness[failed.v] != q.event) return;
        std::priority_queue<Cursor> queue;
        vector<int> touched;
        auto schedule_child = [&](int v, int pos) {
            if (pos == int(children[v].size())) return;
            int t = legs[children[v][pos]].departure;
            if (t <= q.deadline) queue.push({t, v, pos, true});
        };
        queue.push({failed.arrival, failed.v, 0, false});
        while (!queue.empty()) {
            auto [time, v, pos, child] = queue.top();
            queue.pop();
            if (child) {
                ++work.child_tests;
                if (replacement[v] < time) continue;
                const auto& e = legs[children[v][pos]];
                if (e.arrival <= q.deadline) queue.push({e.arrival, e.v, 0, false});
                schedule_child(v, pos + 1);
                continue;
            }
            const auto& options = incoming[v];
            bool reached = false;
            while (pos < int(options.size()) && legs[options[pos]].arrival == time) {
                int i = options[pos++];
                const auto& e = legs[i];
                ++work.probes;
                int sender = changed[e.u] ? replacement[e.u] : base[e.u];
                if (i != q.event && sender < e.departure) {
                    reached = true;
                    break;
                }
            }
            if (reached) {
                if (changed[v]) replacement[v] = time;
                continue;
            }
            if (!changed[v]) {
                changed[v] = 1;
                replacement[v] = NEVER;
                touched.push_back(v);
                schedule_child(v, 0);
            }
            if (pos < int(options.size())) {
                int next = legs[options[pos]].arrival;
                if (next <= q.deadline) queue.push({next, v, pos, false});
            }
        }
        for (int v : touched) {
            emit(out, v, base[v], replacement[v], q.deadline);
            changed[v] = 0;
        }
    }
};
