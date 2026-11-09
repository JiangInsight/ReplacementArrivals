#pragma once
#include "contact.hpp"

struct History {
    vector<std::pair<int,int>> changes;
    int birth_node=0;
};
struct HistoryIndex {
    const Contacts& g;
    vector<int> node_of, event_of{-1}, parent{0}, depth{0};
    vector<vector<int>> children{1}, births{1};
    vector<History> histories;
    vector<vector<Row>> pairs;
    bool material;
    int64_t history_count=0, pair_count=0;
    explicit HistoryIndex(const Contacts& graph):g(graph),node_of(g.n),histories(g.n),material(false){}
    HistoryIndex(const Contacts& graph,int source,bool materialize,vector<int>* birth_order=nullptr,
                 const vector<std::pair<int,int>>* departures=nullptr):g(graph),node_of(g.n),histories(g.n),material(materialize) {
        vector<vector<int>> up(1,vector<int>{0});
        vector<int> head(g.n,-1),pending(g.n,-1),unique(g.n,-1),touched,first_order;
        head[source]=0;
        auto add=[&](int p,int e,int v){
            int x=int(parent.size()),d=depth[p]+1;
            while((1LL<<up.size())<=d) up.emplace_back(x,0);
            up[0].push_back(p);
            for(int j=1;j<int(up.size());++j) up[j].push_back(up[j-1][up[j-1][x]]);
            parent.push_back(p);depth.push_back(d);event_of.push_back(e);
            children.emplace_back();births.emplace_back();children[p].push_back(x);node_of[v]=x;
            return x;
        };
        auto meet=[&](int a,int b){
            if(depth[a]<depth[b]) std::swap(a,b);
            int diff=depth[a]-depth[b];
            for(int j=0;diff;++j,diff>>=1) if(diff&1) a=up[j][a];
            if(a==b) return a;
            for(int j=int(up.size())-1;j>=0;--j) if(up[j][a]!=up[j][b]) {a=up[j][a];b=up[j][b];}
            return parent[a];
        };
        size_t next_departure=0;
        vector<int> at_departure;
        if(departures) at_departure.assign(g.edges.size(),-1);
        for(int i=g.begin;i<int(g.edges.size());){
            int t=g.edges[i].t;

            while(departures && next_departure<departures->size() && (*departures)[next_departure].first<=t){
                int id=(*departures)[next_departure++].second;
                at_departure[id]=head[g.edges[id].u];
            }
            touched.clear();
            do {
                auto [u,v,unused]=g.edges[i];
                int sender=departures?at_departure[i]:head[u];
                if(sender>=0 && head[v]!=0) {
                    if(pending[v]<0) {
                        touched.push_back(v);
                        pending[v]=head[v]<0 ? sender:meet(head[v],sender);
                        unique[v]=head[v]<0 ? i:-1;
                    } else {
                        pending[v]=meet(pending[v],sender);unique[v]=-1;
                    }
                }
                ++i;
            } while(i<int(g.edges.size()) && g.edges[i].t==t);
            for(int v:touched) {
                int h=pending[v];
                if(unique[v]>=0) h=add(h,unique[v],v);
                if(head[v]<0 && h) {
                    births[h].push_back(v);histories[v].birth_node=h;first_order.push_back(v);
                }
                if(h!=head[v] && (h || head[v]>0)){
                    histories[v].changes.push_back({t,depth[h]});++history_count;
                }
                head[v]=h;pending[v]=-1;
            }
        }
        if(material){
            pairs.resize(parent.size());
            for(int v:first_order) {
                auto& h=histories[v];
                size_t next=1;
                for(int x=h.birth_node;x;x=parent[x]){
                    while(next<h.changes.size() && h.changes[next].second>=depth[x]) ++next;
                    int recovery=next<h.changes.size()?h.changes[next].first:NEVER;
                    pairs[x].push_back({v,h.changes.front().first,recovery});++pair_count;
                }
            }
            vector<History>().swap(histories);vector<vector<int>>().swap(births);
            vector<vector<int>>().swap(children);vector<int>().swap(parent);vector<int>().swap(depth);
        }
        if(birth_order) *birth_order=std::move(first_order);
    }
    void report(Query q,vector<Row>& out,Work& work) const {
        const auto e=g.edges[q.event];
        if(q.event<g.begin || e.t>q.deadline) return;
        int x=node_of[e.v];
        if(!x || event_of[x]!=q.event) return;
        if(material) {
            for(auto r:pairs[x]) {
                if(r.before>q.deadline) break;
                ++work.probes;emit(out,r.vertex,r.before,r.after,q.deadline);
            }
            return;
        }
        vector<int> stack{x};
        while(!stack.empty()) {
            int n=stack.back();stack.pop_back();
            for(int v:births[n]){
                const auto& h=histories[v].changes;
                if(h.front().first>q.deadline) break;
                auto it=std::upper_bound(h.begin(),h.end(),depth[x],
                    [](int d,const auto& entry){return d>entry.second;});
                ++work.probes;emit(out,v,h.front().first,it==h.end()?NEVER:it->first,q.deadline);
            }
            for(int c:children[n]){
                if(g.edges[event_of[c]].t>q.deadline) break;
                stack.push_back(c);
            }
        }
    }
};
