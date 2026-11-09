#pragma once
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <limits>
#include <queue>
#include <stdexcept>
#include <tuple>
#include <vector>

using std::vector;
using Clock = std::chrono::steady_clock;
constexpr int NEVER = std::numeric_limits<int>::max();
struct Event { int u,v,t; };
static_assert(sizeof(Event)==12);
struct Row { int vertex, before, after; };
static_assert(sizeof(Row)==12);
struct Query { int event, deadline; };
struct Contacts {
    vector<Event> edges;
    int n, begin;
};
struct Work { uint64_t probes=0, child_tests=0, heap_ops=0; };

struct Witness {
    vector<int> first, via;
    Witness(const Contacts& g,int source): first(g.n,NEVER), via(g.n,-1) {
        first[source]=-1;
        for(int i=g.begin;i<int(g.edges.size());++i) {
            auto [u,v,t]=g.edges[i];
            if(first[u]<t && first[v]==NEVER) { first[v]=t; via[v]=i; }
        }
    }
    bool relevant(const Contacts& g,Query q) const {
        const auto& e=g.edges[q.event];
        return q.event>=g.begin && e.t<=q.deadline && via[e.v]==q.event;
    }
};

inline void emit(vector<Row>& out,int v,int before,int after,int horizon) {
    out.push_back({v,before,after>horizon ? -1:after});
}

struct SuffixReplay {
    const Contacts& g;
    Witness w;
    SuffixReplay(const Contacts& graph,int src):g(graph),w(g,src) {}
    void report(Query q,vector<Row>& out,Work& work) const {
        if(!w.relevant(g,q)) return;
        const int start=g.edges[q.event].t;
        vector<int> alt=w.first;
        for(int& t:alt) if(t>=start) t=NEVER;
        auto it=std::lower_bound(g.edges.begin()+g.begin,g.edges.end(),start,
              [](const Event& e,int t){return e.t<t;});
        for(;it!=g.edges.end() && it->t<=q.deadline;++it){
            ++work.probes;
            if(&*it!=&g.edges[q.event] && alt[it->u]<it->t && alt[it->v]==NEVER)
                alt[it->v]=it->t;
        }
        for(int v=0;v<g.n;++v) if(w.first[v]<=q.deadline && w.first[v]!=alt[v])
            emit(out,v,w.first[v],alt[v],q.deadline);
    }
};


struct Cursor {
    int time, v, pos;
    bool child;
    bool operator<(const Cursor& b) const {return time>b.time;}
};
struct Repair {
    const Contacts& g;
    Witness w;
    vector<vector<int>> children;
    vector<int> offsets, incoming, stamp, recovered;
    int epoch=0;
    bool eager, filtered;
    Repair(const Contacts& graph,int source,bool eager_children=false,bool filter=true):
        g(graph),w(g,source),children(g.n),offsets(g.n+1),stamp(g.n),recovered(g.n),
        eager(eager_children),filtered(filter) {
        for(int i=g.begin;i<int(g.edges.size());++i) {
            auto [u,v,t]=g.edges[i];
            if(w.via[v]==i) children[u].push_back(i);
            if(!filtered || w.first[u]<t) ++offsets[v+1];
        }
        for(int i=0;i<g.n;++i) offsets[i+1]+=offsets[i];
        incoming.resize(offsets.back());
        auto next=offsets;
        for(int i=g.begin;i<int(g.edges.size());++i) {
            auto [u,v,t]=g.edges[i];
            if(!filtered || w.first[u]<t) incoming[next[v]++]=i;
        }
    }
    void report(Query q,vector<Row>& out,Work& work) {
        if(!w.relevant(g,q)) return;
        if(epoch==NEVER) {std::fill(stamp.begin(),stamp.end(),0); epoch=0;}
        ++epoch;
        std::priority_queue<Cursor> heap;
        auto push=[&](Cursor c){
            if(c.time<=q.deadline){heap.push(c);++work.heap_ops;}
        };
        auto child=[&](int v,int pos){
            if(pos<int(children[v].size())) push({g.edges[children[v][pos]].t,v,pos,true});
        };
        auto first_pos=[&](int v){
            if(filtered) return offsets[v];
            return int(std::lower_bound(incoming.begin()+offsets[v],incoming.begin()+offsets[v+1],
                w.first[v],[&](int i,int t){return g.edges[i].t<t;})-incoming.begin());
        };
        const int root=g.edges[q.event].v;
        push({w.first[root],root,first_pos(root),false});
        vector<int> changed;
        while(!heap.empty()) {
            auto [t,v,pos,is_child]=heap.top();heap.pop();
            if(is_child) {
                ++work.child_tests;
                if(recovered[v]<t) continue;
                int c=g.edges[children[v][pos]].v;
                push({t,c,first_pos(c),false});
                if(!eager) child(v,pos+1);
                continue;
            }
            const int stop=offsets[v+1];
            bool reached=false;
            while(pos<stop && g.edges[incoming[pos]].t==t) {
                int i=incoming[pos++],u=g.edges[i].u;
                ++work.probes;
                int sender=stamp[u]==epoch ? recovered[u]:w.first[u];
                if(i!=q.event && sender<t) {reached=true;break;}
            }
            if(reached) {
                if(stamp[v]==epoch) recovered[v]=t;
                continue;
            }
            if(stamp[v]!=epoch) {
                stamp[v]=epoch; recovered[v]=NEVER; changed.push_back(v);
                if(eager) {
                    for(int j=0;j<int(children[v].size());++j) child(v,j);
                } else child(v,0);
            }
            if(pos<stop) push({g.edges[incoming[pos]].t,v,pos,false});
        }
        for(int v:changed) emit(out,v,w.first[v],recovered[v],q.deadline);
    }
};
