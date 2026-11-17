

int audit_force = -1;
#include "layout_audit_components.hpp"
#include <windows.h>
#include <psapi.h>
#include <array>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <string>
using i64 = int64_t;
using Triple = std::array<i64,3>;
struct Leg {int u,v,d,a;};
struct Input {
    Contacts g;
    vector<Leg> legs;
    vector<std::pair<int,int>> dep;
    bool scheduled;
    Input(const std::string& file,int n,int release,int cap,bool timetable):scheduled(timetable){
        std::ifstream in(file,std::ios::binary|std::ios::ate);
        if(!in) throw std::runtime_error(file);
        const auto bytes=in.tellg();
        in.seekg(0);g.n=n;g.begin=scheduled?0:release;
        auto read=[&](auto& a){using T=typename std::decay_t<decltype(a)>::value_type;
            if(bytes%sizeof(T)) throw std::runtime_error("input width");
            size_t rows=size_t(bytes)/sizeof(T);if(cap>=0)rows=std::min(rows,size_t(cap));
            a.resize(rows);in.read(reinterpret_cast<char*>(a.data()),rows*sizeof(T));
            if(!in)throw std::runtime_error("truncated log");
        };
        if(!scheduled){read(g.edges);return;}
        read(legs);
        for(int i=0;i<int(legs.size());++i){
            auto [u,v,d,a]=legs[i];g.edges.push_back({u,v,a});
            if(d>=release)dep.emplace_back(d,i);
        }
        std::sort(dep.begin(),dep.end());
    }
};
struct Shape {i64 k=0,r=0,U=0,hard=0,keys=0,aug=0,uniform=0,sumdepth=0,nonuniform=0;};
enum Model {NATIVE,EXACT,CAT_LOW,CAT_HIGH,WIDE,TIME64};
const char* names[]={"native","exact_links","catalog_minus20","catalog_plus20","all_fields_64","time_fields_64"};
struct TimeRow {int v;int64_t before,after;};
struct TimeSite {int v;int64_t before;int end,skip;int64_t handle;int depth;};
struct TimeCat {int v;int64_t before;int begin,count,left,right,ending,skip,catalog,length,start_rank;uint64_t mask;};
Triple price(const Shape& x,Model m){
    i64 off=4,row=sizeof(Row),site=sizeof(ComponentIndex::Site),dep=4,cs=sizeof(CascadeIndex::Site),
        hist=sizeof(std::pair<int,int>),link=sizeof(CascadeIndex::Link);
    if(m==WIDE){off=8;row=24;site=48;dep=8;cs=96;hist=16;link=32;}
    if(m==TIME64){row=sizeof(TimeRow);site=sizeof(TimeSite);dep=8;cs=sizeof(TimeCat);hist=16;}
    i64 c=cs*x.r+hist*x.U+link*(m==EXACT?x.aug:2*x.keys);
    Triple t{off*x.k+row*x.sumdepth,site*x.r+dep*x.nonuniform,c};
    
    if(m==CAT_LOW || m==CAT_HIGH){for(i64& v:t)v*=5;t[2]=c*(m==CAT_LOW?4:6);}
    return t;
}
int winner(Triple t){return int(std::min_element(t.begin(),t.end())-t.begin());}
i64 capE(const ComponentIndex& x){return sizeof(int)*x.offsets.capacity()+sizeof(Row)*x.rows.capacity();}
i64 capD(const ComponentIndex& x){return sizeof(int)*x.dense.capacity()+sizeof(ComponentIndex::Site)*x.sites.capacity();}
i64 capC(const ComponentIndex& x){return x.catalog.bytes()-sizeof(x.catalog);}
size_t peak(){
    PROCESS_MEMORY_COUNTERS pc{};
    if(!GetProcessMemoryInfo(GetCurrentProcess(),&pc,sizeof(pc)))throw std::runtime_error("working set");
    return pc.PeakWorkingSetSize;
}
void profile(const Input& input,int src,const std::string& ids){
    const auto& g=input.g;
    std::cout<<"W "<<(input.scheduled?input.dep.size():g.edges.size()-g.begin)<<"\n";
    vector<int> births;
    HistoryIndex h(g,src,false,&births,input.scheduled?&input.dep:nullptr);
    vector<int> root(h.parent.size());
    vector<Shape> data(h.parent.size());
    std::map<std::string,std::map<int,int>> hist;
    for(int i=1;i<int(root.size());++i){root[i]=h.parent[i]?root[h.parent[i]]:i;++data[root[i]].k;}
    for(int v:births){
        const auto& hv=h.histories[v];const auto& a=hv.changes;
        auto& x=data[root[hv.birth_node]];const int d=a.front().second,n=int(a.size()),span=d-a.back().second;
        ++x.r;x.U+=n;x.sumdepth+=d;
        if(ComponentIndex::uniform(a))++x.uniform;else x.nonuniform+=d;
        if(n>8 && span>=64){++x.hard;x.keys+=n;}
        ++hist["depth"][d];++hist["history"][n];++hist["span"][span];
    }
    {
        CascadeIndex pool(CascadeIndex::ADAPTIVE);vector<std::pair<int,int>> ignored;
        pool.assemble(g,h,nullptr,&ignored);
        for(const auto& s:pool.sites)data[root[h.histories[s.vertex].birth_node]].aug+=s.length;
    }
    Triple predicted{},actual{},roots{},recipients{},history{},hard{},uni{};
    std::array<std::array<i64,6>,6> scenario{};
    Triple global{};
    std::ofstream keys(ids,std::ios::binary);
    for(int i:h.children[0]){
        const auto& x=data[i];if(x.aug>2*x.keys || x.aug<x.keys)throw std::logic_error("link bound");
        const auto score=price(x,NATIVE),occ=price(x,EXACT);const int b=winner(score);
        for(int j=0;j<3;++j)global[j]+=score[j];
        ++roots[b];recipients[b]+=x.r;history[b]+=x.U;hard[b]+=x.hard;uni[b]+=x.uniform;
        actual[b]+=occ[b];predicted[b]+=score[b];++hist["component"][int(x.r)];
        int record[3]={h.event_of[i],b,int(x.r)};keys.write(reinterpret_cast<const char*>(record),sizeof(record));
        for(int m=NATIVE;m<=TIME64;++m){
            const int k=winner(price(x,Model(m)));auto& c=scenario[m];
            ++c[k];c[3]+=k!=b;c[4]+=(k!=b)*x.r;c[5]+=occ[k];
        }
    }
    if(!keys)throw std::runtime_error("root dump");
    for(const auto& [group,counts]:hist)for(auto [value,n]:counts)std::cout<<"H "<<group<<" "<<value<<" "<<n<<"\n";
    for(int i=0;i<3;++i) std::cout<<"G "<<i<<" "<<roots[i]<<" "<<recipients[i]<<" "<<history[i]<<" "
        <<hard[i]<<" "<<uni[i]<<" "<<predicted[i]<<" "<<actual[i]<<"\n";
    for(int m=0;m<=TIME64;++m){
        std::cout<<"S "<<names[m];for(auto x:scenario[m])std::cout<<" "<<x;std::cout<<"\n";
    }
    for(auto p:{ComponentIndex::MIXED,ComponentIndex::GLOBAL,ComponentIndex::ALL_PAIRS}){
        ComponentIndex x(g,h,births,p);
        const i64 e=capE(x),d=capD(x),c=capC(x),dict=x.dict.bytes(),header=sizeof(x);
        i64 e0=(x.offsets.size()-1)*4+x.rows.size()*sizeof(Row);
        i64 d0=x.sites.size()*sizeof(ComponentIndex::Site)+x.dense.size()*4;
        i64 c0=x.catalog.sites.size()*sizeof(CascadeIndex::Site)+x.catalog.entries.size()*8+x.catalog.links.size()*sizeof(CascadeIndex::Link);
        if(header+e+d+c+dict!=i64(x.bytes()))throw std::logic_error("retained size");
        if(p==ComponentIndex::MIXED && (e0!=actual[0] || d0!=actual[1] || c0!=actual[2]))
            throw std::logic_error("independent occupied size");
        Triple exp{};
        for(int i:h.children[0]){const auto& a=data[i];int kind=p==ComponentIndex::MIXED?winner(price(a,NATIVE)):p==ComponentIndex::GLOBAL?winner(global):0;
            ++exp[kind];}
        for(int j=0;j<3;++j)if(exp[j]!=x.root_counts[j])throw std::logic_error("root distribution");
        std::cout<<"M "<<int(p)<<" "<<e0<<" "<<d0<<" "<<c0<<" "<<e<<" "<<d<<" "<<c<<" "<<dict<<" "<<header<<" "<<x.bytes()<<"\n";
    }
}
int main(int argc,char** argv) try{
    if(argc!=10) throw std::runtime_error("mode file n source first cap scheduled policy output");
    const std::string mode=argv[1];int source=std::stoi(argv[4]),p=std::stoi(argv[8]);
    Input input(argv[2],std::stoi(argv[3]),std::stoi(argv[5]),std::stoi(argv[6]),std::stoi(argv[7])!=0);
    if(mode=="profile"){profile(input,source,argv[9]);return 0;}
    if(mode=="peak"){
        auto before=peak();
        ComponentIndex index(input.g,source,ComponentIndex::Policy(p),input.scheduled?&input.dep:nullptr);
        std::cout<<"P "<<p<<" "<<before<<" "<<peak()<<" "<<index.bytes()<<"\n";return 0;
    }
    if(mode!="serve")throw std::runtime_error("mode");
    std::ifstream query(argv[9]);vector<Query> q;Query line;
    while(query>>line.event>>line.deadline)q.push_back(line);
    if(!query.eof() || q.empty())throw std::runtime_error("requests");
    audit_force=p;
    auto start=Clock::now();ComponentIndex index(input.g,source,ComponentIndex::MIXED);
    auto ready=Clock::now();vector<Event>().swap(input.g.edges);
    
    uint64_t checksum=0,count=0;Work work;vector<Row> rows;
    auto a=Clock::now();
    for(int repeat=0;repeat<5;++repeat)for(auto request:q){
        rows.clear();index.report(request,rows,work);uint64_t hash=0;
        for(auto r:rows)hash+=(uint64_t(uint32_t(r.vertex))*0x9e3779b185ebca87ULL)^
           (uint64_t(uint32_t(r.before))*0x85ebca77c2b2ae63ULL)^uint32_t(r.after);
        checksum=checksum*0x27d4eb2f165667c5ULL+hash;count+=rows.size();
    }
    std::cout<<"T "<<p<<" "<<std::chrono::duration<double>(ready-start).count()<<" "
       <<std::chrono::duration<double>(Clock::now()-a).count()<<" "<<count<<" "<<checksum<<" "<<index.bytes()<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}

