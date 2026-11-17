#pragma once
#include "contact.hpp"

 
 
struct EquationRepair {
    const Contacts& g;
    Witness w;
    vector<vector<int>> in,outgoing;
    vector<int> label,rhs,version,notified;
    int stamp=0;
    EquationRepair(const Contacts& graph,int src):g(graph),w(g,src),in(g.n),outgoing(g.n),
        label(w.first),rhs(w.first),version(g.n),notified(g.n) {
        for(int i=g.begin;i<int(g.edges.size());++i){
            auto [u,v,t]=g.edges[i];
            if(v!=src && w.first[u]<t) {in[v].push_back(i);outgoing[u].push_back(i);}
        }
    }
    void report(Query q,vector<Row>& out,Work& work){
        if(!w.relevant(g,q)) return;
        using Entry=std::tuple<int,int,int>;
        std::priority_queue<Entry,vector<Entry>,std::greater<Entry>> heap;
        vector<int> touched;
        auto update=[&](int v){
            if(!version[v]) touched.push_back(v);
            ++version[v];
            rhs[v]=NEVER;
            for(int i:in[v]){
                ++work.probes;
                const auto& e=g.edges[i];
                if(e.t>q.deadline) break;
                if(i!=q.event && label[e.u]<e.t){rhs[v]=e.t;break;}
            }
            if(rhs[v]!=label[v]){
                heap.emplace(std::min(rhs[v],label[v]),v,version[v]);++work.heap_ops;
            }
        };
        update(g.edges[q.event].v);
        while(!heap.empty()){
            auto [key,u,serial]=heap.top();heap.pop();
            if(serial!=version[u]) continue;
            int old=label[u];
            if(old>rhs[u]) label[u]=rhs[u];
            else {label[u]=NEVER;update(u);}
            int lo=std::min(old,label[u]),hi=std::min(q.deadline,std::max(old,label[u]));
            const auto& edges=outgoing[u];
            auto it=std::upper_bound(edges.begin(),edges.end(),lo,
                [&](int t,int i){return t<g.edges[i].t;});
            if(stamp==NEVER){std::fill(notified.begin(),notified.end(),0);stamp=0;}
            ++stamp;
            for(;it!=edges.end() && g.edges[*it].t<=hi;++it){
                int v=g.edges[*it].v;++work.child_tests;
                if(notified[v]!=stamp) {notified[v]=stamp;update(v);}
            }
        }
        for(int v:touched){
            if(label[v]!=w.first[v]) emit(out,v,w.first[v],label[v],q.deadline);
            label[v]=rhs[v]=w.first[v];version[v]=0;
        }
    }
};

