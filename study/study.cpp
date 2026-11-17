#include "histories.hpp"
#include "dag.hpp"
#include "equations.hpp"
#include "cascade.hpp"
#include "components.hpp"
#include "dominator.hpp"
#include "expansion/baselines.hpp"
#include "algorithms/TemporalDistances.h"
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#pragma comment(lib,"psapi.lib")
#endif

uint64_t ready_rss=0,peak_rss=0;
void memory(bool ready){
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS counters{};
    if(!GetProcessMemoryInfo(GetCurrentProcess(),&counters,sizeof(counters)))
        throw std::runtime_error("failed to read working set");
    if(ready) ready_rss=counters.WorkingSetSize;
    peak_rss=counters.PeakWorkingSetSize;
#endif
}

struct TGLibReplay {
    using Graph=tglib::OrderedEdgeList<tglib::TemporalEdge>;
    const Contacts& g;
    int source;
    Witness w;
    std::unique_ptr<Graph> graph;
    TGLibReplay(const Contacts& contacts,int src):g(contacts),source(src),w(g,src) {
        vector<tglib::TemporalEdge> ed;
        ed.reserve(g.edges.size()-g.begin);
        for(size_t i=g.begin;i<g.edges.size();++i){
            auto [u,v,t]=g.edges[i];
            tglib::TemporalEdge edge;
            edge.u=u;edge.v=v;edge.t=t;edge.tt=1;ed.push_back(edge);
        }
        graph=std::make_unique<Graph>(g.n,std::move(ed),tglib::TimeInterval{0,g.edges.back().t});
    }
    void report(Query q,vector<Row>& out,Work&) {
        if(!w.relevant(g,q)) return;
         
         
        auto& e=const_cast<tglib::TemporalEdge&>(graph->getEdges()[q.event-g.begin]);
        int original=e.v;e.v=e.u;
        auto alt=tglib::earliest_arrival_times(*graph,source,{0,q.deadline});
        e.v=original;
        for(int v=0;v<g.n;++v) if(v!=source && w.first[v]<=q.deadline){
            int replacement=alt[v]==tglib::inf ? NEVER:int(alt[v]-1);
            if(replacement!=w.first[v]) emit(out,v,w.first[v],replacement,q.deadline);
        }
    }
};
double seconds(Clock::time_point a,Clock::time_point b){return std::chrono::duration<double>(b-a).count();}

template<class Index>
void serve(Index& index,const vector<Query>& qs,const std::string& stem) {
    memory(true);
    std::ofstream wire(stem+".rows",std::ios::binary),log(stem+".csv");
    if(!wire || !log) throw std::runtime_error("cannot open study outputs");
    log<<"i,event,deadline,rows,query_ns,encode_ns,probes,child_tests,heap_ops\n";
    for(size_t i=0;i<qs.size();++i){
        vector<Row> rows;
        Work counters;
        auto a=Clock::now();
        index.report(qs[i],rows,counters);
        auto b=Clock::now();
        std::sort(rows.begin(),rows.end(),[](Row a,Row b){return a.vertex<b.vertex;});
        uint32_t n=uint32_t(rows.size());
        wire.write(reinterpret_cast<const char*>(&n),sizeof n);
        wire.write(reinterpret_cast<const char*>(rows.data()),sizeof(Row)*n);
        auto c=Clock::now();
        auto ns=[](auto d){return std::chrono::duration_cast<std::chrono::nanoseconds>(d).count();};
        log<<i<<','<<qs[i].event<<','<<qs[i].deadline<<','<<n<<','<<ns(b-a)<<','<<ns(c-b)
           <<','<<counters.probes<<','<<counters.child_tests<<','<<counters.heap_ops<<'\n';
    }
    wire.close();log.close();
    if(!wire || !log) throw std::runtime_error("could not persist results");
}

int main(int argc,char** argv) try {
    if(argc!=9) throw std::runtime_error("study BIN N SOURCE FIRST_INDEX QUERIES METHOD OUTPUT_STEM METRICS");
    auto boot=Clock::now();
    std::ifstream in(argv[1],std::ios::binary|std::ios::ate);
    auto bytes=in.tellg();
    if(bytes<=0 || bytes%sizeof(Event)) throw std::runtime_error("invalid packed input");
    Contacts g;
    g.n=std::stoi(argv[2]);int source=std::stoi(argv[3]);g.begin=std::stoi(argv[4]);
    g.edges.resize(size_t(bytes)/sizeof(Event));
    in.seekg(0);in.read(reinterpret_cast<char*>(g.edges.data()),bytes);
    if(!in || g.begin<0 || g.begin>=int(g.edges.size()) || source<0 || source>=g.n)
        throw std::runtime_error("invalid graph or release");
    vector<Query> qs;Query q;
    std::ifstream queries(argv[5]);
    while(queries>>q.event>>q.deadline){
        if(q.event<0 || q.event>=int(g.edges.size())) throw std::runtime_error("bad event");
        qs.push_back(q);
    }
    if(!queries.eof() || qs.empty()) throw std::runtime_error("invalid query input");
    auto loaded=Clock::now();
    std::string method=argv[6],stem=argv[7];
    int64_t history=0,pairs=0,catalog_keys=0,hard_sites=0,index_bytes=0;
    int component_counts[3]{};
    int64_t dom_nodes=0,dom_meets=0;
    Clock::time_point built;
    if(method=="repair" || method=="eager" || method=="unfiltered"){
        Repair index(g,source,method=="eager",method!="unfiltered");built=Clock::now();serve(index,qs,stem);
    } else if(method=="incident"){
        IncidentReplay index(g,source);built=Clock::now();serve(index,qs,stem);
    } else if(method=="calendar"){
        CalendarSearch index(g,source);built=Clock::now();serve(index,qs,stem);
    } else if(method=="decremental"){
        Decremental index(g,source);built=Clock::now();serve(index,qs,stem);
    } else if(method.rfind("without-",0)==0){
        const std::vector<std::pair<std::string,ComponentIndex::Policy>> policies={
            {"without-explicit",ComponentIndex::NO_EXPLICIT},{"without-direct",ComponentIndex::NO_DIRECT},
            {"without-catalog",ComponentIndex::NO_CATALOG},{"without-uniform",ComponentIndex::NO_UNIFORM},
            {"without-prune",ComponentIndex::NO_PRUNE},{"without-links",ComponentIndex::NO_LINKS}};
        auto p=std::find_if(policies.begin(),policies.end(),[&](auto& item){return item.first==method;});
        if(p==policies.end())throw std::invalid_argument("unknown ablation");
        ComponentIndex index(g,source,p->second);built=Clock::now();index_bytes=index.bytes();pairs=index.possible_pairs;
        std::copy_n(index.root_counts,3,component_counts);vector<Event>().swap(g.edges);serve(index,qs,stem);
    } else if(method=="history" || method=="pairs"){
        HistoryIndex index(g,source,method=="pairs");built=Clock::now();
        history=index.history_count;pairs=index.pair_count;serve(index,qs,stem);
    } else if(method=="ordered" || method=="cascade" || method=="adaptive"){
        auto mode=method=="ordered"?CascadeIndex::BINARY:(method=="cascade"?CascadeIndex::ALL:CascadeIndex::ADAPTIVE);
        CascadeIndex index(g,source,mode);built=Clock::now();
        history=index.entries.size();catalog_keys=index.links.size();hard_sites=index.hard_sites;
        index_bytes=index.bytes();vector<Event>().swap(g.edges);
        serve(index,qs,stem);
    } else if(method=="dom" || method=="domfull"){
        DominatorIndex index(g,source,method=="dom");built=Clock::now();
        index_bytes=index.result->bytes();dom_nodes=index.state_count;dom_meets=index.intersections;
        std::copy_n(index.result->root_counts,3,component_counts);
        vector<Event>().swap(g.edges);serve(index,qs,stem);
    } else if(method=="mix" || method=="frontier" || method=="global" || method=="allpairs"){
        auto policy=method=="global"?ComponentIndex::GLOBAL:(method=="allpairs"?ComponentIndex::ALL_PAIRS:ComponentIndex::MIXED);
        ComponentIndex index(g,source,policy);built=Clock::now();
        pairs=index.possible_pairs;index_bytes=index.bytes();
        std::copy_n(index.root_counts,3,component_counts);vector<Event>().swap(g.edges);serve(index,qs,stem);
    } else if(method=="flatpairs"){
        FlatPairs index(g,source);built=Clock::now();pairs=index.rows.size();index_bytes=index.bytes();
        vector<Event>().swap(g.edges);serve(index,qs,stem);
    } else if(method=="equations"){
        EquationRepair index(g,source);built=Clock::now();serve(index,qs,stem);
    } else if(method=="dag"){
        DagReplay index(g,source);built=Clock::now();serve(index,qs,stem);
    } else if(method=="scan"){
        SuffixReplay index(g,source);built=Clock::now();serve(index,qs,stem);
    } else if(method=="tglib"){
        TGLibReplay index(g,source);built=Clock::now();serve(index,qs,stem);
    } else throw std::runtime_error("unknown method");
    auto done=Clock::now();
    memory(false);
    std::ofstream metrics(argv[8]);
    metrics<<std::setprecision(12)<<"{\"load_s\":"<<seconds(boot,loaded)<<",\"build_s\":"<<seconds(loaded,built)
           <<",\"serve_and_teardown_s\":"<<seconds(built,done)<<",\"history\":"<<history<<",\"pairs\":"<<pairs
           <<",\"ready_bytes\":"<<ready_rss<<",\"peak_bytes\":"<<peak_rss
           <<",\"catalog_keys\":"<<catalog_keys<<",\"hard_sites\":"<<hard_sites<<",\"index_bytes\":"<<index_bytes
           <<",\"components\":["<<component_counts[0]<<','<<component_counts[1]<<','<<component_counts[2]<<"]"
           <<",\"dom_nodes\":"<<dom_nodes<<",\"dom_meets\":"<<dom_meets<<"}\n";
    return metrics?0:3;
} catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}

