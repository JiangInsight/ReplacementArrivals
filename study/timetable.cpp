#include "components.hpp"
#include <iostream>
#include <string>
#include <iomanip>
struct Leg {int u,v,departure,arrival;};
struct ConnectionScan {
    const vector<Leg>& legs;
    const vector<std::pair<int,int>>& order;
    int source,release;
    vector<int> first,via,alt;
    ConnectionScan(const vector<Leg>& records,const vector<std::pair<int,int>>& departures,int n,int s,int start)
        :legs(records),order(departures),source(s),release(start),first(n,NEVER),via(n,-1),alt(n){
        first[s]=release-1;
        for(auto [d,i]:order){
            auto e=legs[i];
            if(first[e.u]<d && e.arrival<first[e.v]){first[e.v]=e.arrival;via[e.v]=i;}
        }
    }
    void report(Query q,vector<Row>& out,Work& work){
        const auto e=legs[q.event];
        if(via[e.v]!=q.event || e.arrival>q.deadline) return;
        std::fill(alt.begin(),alt.end(),NEVER);alt[source]=release-1;
        for(auto [d,i]:order){
            if(d>q.deadline) break;
            auto a=legs[i];++work.probes;
            if(i!=q.event && alt[a.u]<d && a.arrival<alt[a.v]) alt[a.v]=a.arrival;
        }
        for(int v=0;v<int(alt.size());++v) if(first[v]<=q.deadline && alt[v]!=first[v])
            emit(out,v,first[v],alt[v],q.deadline);
    }
};
int main(int argc,char** argv) try {
    if(argc!=9) throw std::runtime_error("timetable LEGS N SOURCE RELEASE QFILE_OR_ALL HORIZON METHOD STEM");
    std::ifstream in(argv[1],std::ios::binary|std::ios::ate);
    auto bytes=in.tellg();if(bytes<=0 || bytes%sizeof(Leg))throw std::runtime_error("bad input");
    vector<Leg> legs(size_t(bytes)/sizeof(Leg));in.seekg(0);in.read(reinterpret_cast<char*>(legs.data()),bytes);
    if(!in)throw std::runtime_error("bad read");
    Contacts g;g.n=std::stoi(argv[2]);g.begin=0;int src=std::stoi(argv[3]),start=std::stoi(argv[4]);
    vector<std::pair<int,int>> order;
    for(int i=0;i<int(legs.size());++i){
        auto [u,v,d,a]=legs[i];
        if(u<0||v<0||u>=g.n||v>=g.n||d>a||(i && a<legs[i-1].arrival)) throw std::runtime_error("invalid leg");
        g.edges.push_back({u,v,a});if(d>=start)order.emplace_back(d,i);
    }
    std::sort(order.begin(),order.end());
    int deadline=std::stoi(argv[6]);std::string arm=argv[7],stem=argv[8];
    bool all=std::string(argv[5])=="ALL";
    vector<Query> qs;Query q;
    if(!all){
        std::ifstream input(argv[5]);while(input>>q.event>>q.deadline) qs.push_back(q);
        if(qs.empty()||!input.eof())throw std::runtime_error("invalid requests");
    }
    std::ofstream wire(stem+".rows",std::ios::binary);
    int64_t returned=0,restored=0,requests=0,positive=0,bytes_index=0;
    int component_counts[3]{};
    auto construction=Clock::now(),built=construction;
    auto run=[&](auto& index){
        built=Clock::now();
        vector<Row> rows;
        Work work;
        auto visit=[&](int ordinal,Query query){
            rows.clear();index.report(query,rows,work);++requests;
            if(rows.empty())return;
            ++positive;returned+=rows.size();
            for(auto r:rows) restored+=r.after>=0;
            std::sort(rows.begin(),rows.end(),[](Row a,Row b){return a.vertex<b.vertex;});
            int n=int(rows.size());
            wire.write(reinterpret_cast<const char*>(&ordinal),4);
            wire.write(reinterpret_cast<const char*>(&n),4);
            wire.write(reinterpret_cast<const char*>(rows.data()),n*sizeof(Row));
        };
        if(all){
            for(int i=0;i<int(legs.size());++i) if(legs[i].departure>=start && legs[i].arrival<=deadline)
                visit(i,{i,deadline});
        }else{
            for(int i=0;i<int(qs.size());++i) visit(i,qs[i]);
        }
    };
    if(arm=="csa"){
        ConnectionScan index(legs,order,g.n,src,start);run(index);
    }else{
        ComponentIndex::Policy policy;
        if(arm=="mix") policy=ComponentIndex::MIXED;
        else if(arm=="allpairs") policy=ComponentIndex::ALL_PAIRS;
        else if(arm=="global") policy=ComponentIndex::GLOBAL;
        else throw std::runtime_error("unknown method");
        ComponentIndex index(g,src,policy,&order);
        bytes_index=index.bytes();std::copy_n(index.root_counts,3,component_counts);
        run(index);
    }
    wire.close();if(!wire)throw std::runtime_error("write failed");
    std::cout<<std::setprecision(10)<<"{\"requests\":"<<requests<<",\"positive\":"<<positive<<",\"rows\":"<<returned
             <<",\"recovered\":"<<restored<<",\"index_bytes\":"<<bytes_index<<",\"build_s\":"
             <<std::chrono::duration<double>(built-construction).count()<<",\"service_s\":"
             <<std::chrono::duration<double>(Clock::now()-built).count()<<",\"components\":["
             <<component_counts[0]<<','<<component_counts[1]<<','<<component_counts[2]<<"]}\n";
    return 0;
} catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}

