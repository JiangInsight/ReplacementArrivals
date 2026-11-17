#include "contact.hpp"
#include <map>
#include <iomanip>
#include <iostream>
#include <string>
#ifdef _MSC_VER
#include <intrin.h>
#endif
int low_bit(uint64_t x){
#ifdef _MSC_VER
    unsigned long pos;_BitScanForward64(&pos,x);return int(pos);
#else
    return __builtin_ctzll(x);
#endif
}
struct Group {int event,horizon;vector<int> requests;vector<Row> affected;};
int main(int argc,char** argv) try {
    if(argc!=7) throw std::runtime_error("batch INPUT N SOURCE BEGIN QUERIES WIRE");
    auto started=Clock::now();
    std::ifstream input(argv[1],std::ios::binary|std::ios::ate);
    auto bytes=input.tellg();if(bytes<=0 || bytes%sizeof(Event))throw std::runtime_error("bad input");
    Contacts g;g.n=std::stoi(argv[2]);g.begin=std::stoi(argv[4]);int src=std::stoi(argv[3]);
    g.edges.resize(size_t(bytes)/sizeof(Event));input.seekg(0);input.read(reinterpret_cast<char*>(g.edges.data()),bytes);
    if(!input)throw std::runtime_error("read failed");
    std::ifstream file(argv[5]);vector<Query> qs;Query q;
    while(file>>q.event>>q.deadline)qs.push_back(q);
    if(!file.eof()||qs.empty())throw std::runtime_error("bad workload");
    auto loaded=Clock::now();Witness w(g,src);
    vector<Group> groups;std::map<int,int> id;
    for(int i=0;i<int(qs.size());++i){
        q=qs[i];
        if(!w.relevant(g,q))continue;
        auto [it,added]=id.emplace(q.event,int(groups.size()));
        if(added)groups.push_back({q.event,q.deadline,{},{}});
        auto& group=groups[it->second];group.horizon=std::max(group.horizon,q.deadline);group.requests.push_back(i);
    }
    std::sort(groups.begin(),groups.end(),[](const Group& a,const Group& b){
        return std::tie(a.horizon,a.event)<std::tie(b.horizon,b.event);});
    auto prepared=Clock::now();
    vector<uint64_t> active(g.n),pending(g.n),banned(g.n);
    int passes=0;
    for(int base=0;base<int(groups.size());base+=64){
        int width=std::min(64,int(groups.size())-base);
        uint64_t full=width==64?~uint64_t(0):(uint64_t(1)<<width)-1;
        int limit=groups[base+width-1].horizon;
        std::fill(active.begin(),active.end(),0);active[src]=full;
        std::fill(banned.begin(),banned.end(),0);
        for(int j=0;j<width;++j)banned[g.edges[groups[base+j].event].v]|=uint64_t(1)<<j;
        vector<int> touched;
        auto report=[&](uint64_t mask,int v,int t){
            while(mask){
                int bit=low_bit(mask);mask&=mask-1;
                auto& group=groups[base+bit];
                if(w.first[v]<=group.horizon)emit(group.affected,v,w.first[v],t,group.horizon);
            }
        };
        for(int i=g.begin;i<int(g.edges.size()) && g.edges[i].t<=limit;){
            int t=g.edges[i].t;touched.clear();
            do {
                auto [u,v,unused]=g.edges[i];
                uint64_t add=active[u]&~active[v];
                if(i==w.via[v])add&=~banned[v];
                if(add){if(!pending[v])touched.push_back(v);pending[v]|=add;}
                ++i;
            }while(i<int(g.edges.size()) && g.edges[i].t==t);
            for(int v:touched){
                auto new_bits=pending[v];pending[v]=0;active[v]|=new_bits;
                if(t>w.first[v])report(new_bits,v,t);
            }
        }
        for(int v=0;v<g.n;++v)if(w.first[v]<=limit)report(full^active[v],v,NEVER);
        ++passes;
    }
    vector<vector<Row>> answers(qs.size());
    for(const auto& group:groups)for(int idx:group.requests){
        int h=qs[idx].deadline;
        for(auto r:group.affected)if(r.before<=h)
            emit(answers[idx],r.vertex,r.before,r.after<0?NEVER:r.after,h);
    }
    auto computed=Clock::now();std::ofstream wire(argv[6],std::ios::binary);
    for(auto& answer:answers){
        std::sort(answer.begin(),answer.end(),[](Row a,Row b){return a.vertex<b.vertex;});
        int n=int(answer.size());wire.write(reinterpret_cast<char*>(&n),4);
        wire.write(reinterpret_cast<const char*>(answer.data()),sizeof(Row)*n);
    }
    wire.close();if(!wire)throw std::runtime_error("write failed");
    auto sec=[](auto a,auto b){return std::chrono::duration<double>(b-a).count();};
    std::cout<<std::setprecision(12)<<"{\"load_s\":"<<sec(started,loaded)<<",\"prepare_s\":"<<sec(loaded,prepared)
             <<",\"compute_s\":"<<sec(prepared,computed)<<",\"encode_s\":"<<sec(computed,Clock::now())
             <<",\"packed_failures\":"<<groups.size()<<",\"passes\":"<<passes<<"}\n";
    return 0;
} catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}

