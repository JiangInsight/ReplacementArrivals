#define ARRIVAL_INDEX_TYPES_ONLY
#include "expanded_point_control.cpp"
#include <array>
#include <memory>

struct SourceQueries {
    int source, release;
    std::array<std::size_t,3> retained_bytes;
    std::vector<Query> queries;
};

struct Session {
    int source_id, first, count;
};

std::size_t retained(const ComponentIndex &index) { return index.bytes(); }
std::size_t retained(const PointStateIndex &index) { return index.bytes(); }
std::size_t retained(const Repair &index) {
    std::size_t bytes = sizeof(index) + index.children.capacity() * sizeof(vector<int>);
    for (const auto &v : index.children) bytes += v.capacity() * sizeof(int);
    for (const auto *v : {&index.w.first, &index.w.via, &index.offsets, &index.incoming,
                          &index.stamp, &index.recovered}) bytes += v->capacity() * sizeof(int);
    return bytes;
}

void report(ComponentIndex &index, Query q, vector<Row> &rows) {
    Work work;
    index.report(q, rows, work);
}
void report(PointStateIndex &index, Query q, vector<Row> &rows) {
    PointStateIndex::Counters work;
    index.report(q, rows, work);
}
void report(Repair &index, Query q, vector<Row> &rows) {
    Work work;
    index.report(q, rows, work);
}

template<class Index, class Build>
void measure(Contacts &graph, const std::array<SourceQueries,4> &sources, const vector<Session> &sessions,
             std::size_t budget, int size_column, const char *path, Build build) {
    struct Entry {
        std::unique_ptr<Index> index;
        std::size_t size = 0;
        int last_use = -1;
    };
    std::array<Entry,4> cache;
    std::size_t kept = 0, peak = 0;
    int misses = 0, hits = 0, queries = 0, evictions = 0;
    double build_seconds = 0;
    using Seconds = std::chrono::duration<double>;
    auto start = Clock::now();
    std::ofstream wire(path, std::ios::binary);
    for (int step = 0; step < int(sessions.size()); ++step) {
        auto session = sessions[step];
        auto &source = sources.at(session.source_id);
        graph.begin = source.release;
        auto &entry = cache.at(session.source_id);
        std::unique_ptr<Index> transient;
        if (entry.index) {
            ++hits;
        } else {
            ++misses;
            auto begin = Clock::now();
            transient = build(graph, source.source);
            build_seconds += Seconds(Clock::now()-begin).count();
            auto size = source.retained_bytes.at(size_column);
            if (size <= budget) {
                while (kept > budget-size) {
                    Entry *oldest = nullptr;
                    for (auto &e : cache)
                        if (e.index && (!oldest || e.last_use < oldest->last_use)) oldest = &e;
                    if (!oldest) throw std::logic_error("cache accounting");
                    kept -= oldest->size;
                    oldest->index.reset();
                    ++evictions;
                }
                entry.index = std::move(transient);
                entry.size = size;
                kept += size;
                peak = std::max(peak, kept);
            }
        }
        entry.last_use = step;
        auto &index = entry.index ? *entry.index : *transient;
        for (int i=session.first; i<session.first+session.count; ++i) {
            vector<Row> rows;
            report(index,source.queries.at(i),rows);
            std::sort(rows.begin(),rows.end(),[](auto &a, auto &b){return a.vertex<b.vertex;});
            uint32_t n=static_cast<uint32_t>(rows.size());
            wire.write(reinterpret_cast<const char*>(&n),sizeof(n));
            if(n) wire.write(reinterpret_cast<const char*>(rows.data()),sizeof(Row)*n);
            ++queries;
        }
    }
    wire.close();
    if (!wire || peak>budget) throw std::runtime_error("invalid output or retention");
    auto seconds=Seconds(Clock::now()-start).count();
    for (int i=0; i<int(cache.size()); ++i)
        if (cache[i].index && retained(*cache[i].index)!=sources[i].retained_bytes.at(size_column))
            throw std::runtime_error("source size differs from independent memory ledger");
    std::cout<<std::setprecision(12)<<queries<<" "<<hits<<" "<<misses<<" "<<evictions<<" "<<peak<<" "
             <<build_seconds<<" "<<seconds<<"\n";
}

int main(int argc, char **argv) try {
    if(argc!=7) throw std::runtime_error("contacts.bin vertices workload budget_bytes method output");
    Contacts graph;
    graph.n=std::stoi(argv[2]);
    graph.begin=0;
    auto bytes=std::filesystem::file_size(argv[1]);
    if(bytes%sizeof(Event)) throw std::runtime_error("invalid graph");
    graph.edges.resize(bytes/sizeof(Event));
    std::ifstream input(argv[1],std::ios::binary);
    if(!input.read(reinterpret_cast<char*>(graph.edges.data()),bytes)) throw std::runtime_error("input");
    std::ifstream schedule(argv[3]);
    std::array<SourceQueries,4> sources;
    for(auto &source:sources) {
        int count;
        if(!(schedule>>source.source>>source.release>>count) || count<1) throw std::runtime_error("source");
        for(auto &size:source.retained_bytes) if(!(schedule>>size)) throw std::runtime_error("retained bytes");
        source.queries.resize(count);
        for(auto &q:source.queries) if(!(schedule>>q.event>>q.deadline)) throw std::runtime_error("query");
    }
    vector<Session> sessions;
    Session next{};
    while(schedule>>next.source_id>>next.first>>next.count) sessions.push_back(next);
    if(!schedule.eof() || sessions.empty()) throw std::runtime_error("schedule");
    auto budget=std::stoull(argv[4]);
    std::string method=argv[5];
    if(method=="component") measure<ComponentIndex>(graph,sources,sessions,budget,0,argv[6],[](auto &g,int s){
        return std::make_unique<ComponentIndex>(g,s,ComponentIndex::MIXED);});
    else if(method=="expanded") measure<PointStateIndex>(graph,sources,sessions,budget,1,argv[6],[](auto &g,int s){
        return std::make_unique<PointStateIndex>(g,s);});
    else if(method=="repair") measure<Repair>(graph,sources,sessions,budget,2,argv[6],[](auto &g,int s){
        return std::make_unique<Repair>(g,s);});
    else throw std::runtime_error("unknown method");
    return 0;
} catch(const std::exception &error) {std::cerr<<error.what()<<"\n";return 1;}
