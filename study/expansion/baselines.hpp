#pragma once
#include "../contact.hpp"
#include "algorithms/TemporalDistances.h"
#include <memory>

struct IncidentReplay {
    using Graph=tglib::IncidentLists<tglib::TGNode,tglib::TemporalEdge>;
    const Contacts& g; Witness w; int source;
    vector<int> position; std::unique_ptr<Graph> graph;
    IncidentReplay(const Contacts& input,int s):g(input),w(g,s),source(s),position(g.n,-1){
        vector<tglib::TemporalEdge> edges;
        edges.reserve(g.edges.size()-g.begin); vector<int> next(g.n);
        for(int i=g.begin;i<int(g.edges.size());++i){
            auto [u,v,t]=g.edges[i];
            if(w.via[v]==i) position[v]=next[u];
            ++next[u]; tglib::TemporalEdge e; e.u=u;e.v=v;e.t=t;e.tt=1;edges.push_back(e);
        }
        graph=std::make_unique<Graph>(g.n,edges);
    }
    void report(Query q,vector<Row>& rows,Work&){
        if(!w.relevant(g,q))return;
        auto e=g.edges[q.event];
        auto& slot=const_cast<tglib::TemporalEdge&>(graph->getNode(e.u).outEdges[position[e.v]]);
        slot.v=e.u;
        auto alt=tglib::earliest_arrival_times(*graph,source,{0,tglib::Time(q.deadline)+1});
        slot.v=e.v;
        for(int v=0;v<g.n;++v)if(v!=source && w.first[v]<=q.deadline){
            int a=alt[v]==tglib::inf?NEVER:int(alt[v]-1);
            if(a!=w.first[v])emit(rows,v,w.first[v],a,q.deadline);
        }
    }
};

 
struct CalendarSearch {
    const Contacts& g; Witness w; int source;
    struct Route{int v,begin,end;};
    vector<int> ids,from; vector<Route> routes;
    CalendarSearch(const Contacts& input,int s):g(input),w(g,s),source(s),from(g.n+1){
        vector<int> count(g.n+1),tmp(g.edges.size()-g.begin);
        for(int i=g.begin;i<int(g.edges.size());++i)++count[g.edges[i].v+1];
        for(int j=0;j<g.n;++j)count[j+1]+=count[j];
        for(int i=g.begin;i<int(g.edges.size());++i)tmp[count[g.edges[i].v]++]=i;
        std::fill(count.begin(),count.end(),0);
        for(int i:tmp)++count[g.edges[i].u+1];
        for(int j=0;j<g.n;++j)count[j+1]+=count[j];
        ids.resize(tmp.size());
        for(int i:tmp)ids[count[g.edges[i].u]++]=i;
        for(int j=0;j<int(ids.size());){
            int first=j;auto e=g.edges[ids[j++]];
            while(j<int(ids.size()) && g.edges[ids[j]].u==e.u && g.edges[ids[j]].v==e.v)++j;
            routes.push_back({e.v,first,j});++from[e.u+1];
        }
        for(int j=0;j<g.n;++j)from[j+1]+=from[j];
    }
    void report(Query q,vector<Row>& rows,Work& work){
        if(!w.relevant(g,q))return;
        vector<int> best(g.n,NEVER);best[source]=-1;
        using Item=std::pair<int,int>;
        std::priority_queue<Item,vector<Item>,std::greater<Item>> heap;heap.emplace(-1,source);
        while(!heap.empty()){
            auto [t,u]=heap.top();heap.pop();if(t!=best[u])continue;
            for(int i=from[u];i<from[u+1];++i){
                auto route=routes[i];if(best[route.v]<=t)continue;
                ++work.probes;
                auto end=ids.begin()+route.end;
                auto it=std::upper_bound(ids.begin()+route.begin,end,t,[&](int key,int id){return key<g.edges[id].t;});
                if(it!=end && *it==q.event)++it;
                if(it==end)continue;
                int arrive=g.edges[*it].t;
                if(arrive<=q.deadline && arrive<best[route.v]){best[route.v]=arrive;heap.emplace(arrive,route.v);}
            }
        }
        for(int v=0;v<g.n;++v)if(w.first[v]<=q.deadline && best[v]!=w.first[v])
            emit(rows,v,w.first[v],best[v],q.deadline);
    }
};

 
 
 
struct Decremental {
    const Contacts& g;Witness w;
    vector<vector<int>> incoming,outgoing;
    vector<int> dead,stamp,in_pos,out_pos,current;
    int epoch=0;
    Decremental(const Contacts& input,int src):g(input),w(g,src),incoming(g.n),outgoing(g.n),
        dead(g.edges.size()),stamp(g.n),in_pos(g.n),out_pos(g.n),current(g.n){
        for(int i=g.begin;i<int(g.edges.size());++i){
            auto e=g.edges[i];
            if(e.v!=src && w.first[e.u]<e.t){incoming[e.v].push_back(i);outgoing[e.u].push_back(i);}
        }
    }
    void report(Query q,vector<Row>& rows,Work& work){
        if(!w.relevant(g,q))return;
        if(epoch==NEVER){std::fill(stamp.begin(),stamp.end(),0);std::fill(dead.begin(),dead.end(),0);epoch=0;}
        ++epoch;
        vector<int> todo{q.event},touched;
        while(!todo.empty()){
            int i=todo.back();todo.pop_back();
            if(dead[i]==epoch)continue;
            dead[i]=epoch;++work.probes;
            int v=g.edges[i].v;
            if(stamp[v]!=epoch){
                stamp[v]=epoch;in_pos[v]=out_pos[v]=0;current[v]=w.first[v];touched.push_back(v);
            }
            auto& in=incoming[v];int& pos=in_pos[v];
            if(pos==int(in.size()) || in[pos]!=i)continue;
            while(pos<int(in.size()) && dead[in[pos]]==epoch)++pos;
            int next=pos==int(in.size())?NEVER:g.edges[in[pos]].t;
            if(next==current[v])continue;
            current[v]=next;
            auto& out=outgoing[v];int& start=out_pos[v];
            while(start<int(out.size()) && g.edges[out[start]].t<=std::min(q.deadline,next))
                todo.push_back(out[start++]);
        }
        for(int v:touched)if(w.first[v]<=q.deadline && current[v]!=w.first[v])
            emit(rows,v,w.first[v],current[v],q.deadline);
    }
};

