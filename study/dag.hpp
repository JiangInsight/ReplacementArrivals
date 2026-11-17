#pragma once
#include "contact.hpp"

 
 
struct DagReplay {
    const Contacts& g;
    Witness w;
    vector<int> times,owners,next_state,first_state,indegree,offsets,arcs,last_missing;
    DagReplay(const Contacts& graph,int source):g(graph),w(g,source),first_state(g.n,-1),last_missing(g.n,-1) {
        vector<int> degree;
        for(int pass=0;pass<2;++pass) {
            vector<int> latest(g.n,-1),prior(g.n,-1),cursor;
            if(pass) cursor=offsets;
            int count=0;
            auto link=[&](int from,int to){
                if(!pass){
                    ++indegree[to];if(from>=0) ++degree[from];
                }else if(from>=0) arcs[cursor[from]++]=to;
            };
            for(int i=g.begin;i<int(g.edges.size());++i){
                auto [u,v,t]=g.edges[i];
                if(v==source || w.first[u]>=t) continue;
                int sender=latest[u];
                if(sender>=0 && times[sender]==t) sender=prior[u];
                int dest=latest[v];
                if(dest<0 || times[dest]!=t){
                    int old=dest;dest=count++;
                    if(!pass) {
                        times.push_back(t);owners.push_back(v);next_state.push_back(-1);
                        degree.push_back(0);indegree.push_back(0);
                        if(old<0) first_state[v]=dest;else next_state[old]=dest;
                    }
                    prior[v]=old;latest[v]=dest;
                    if(old>=0) link(old,dest);
                }
                link(sender,dest);
            }
            if(!pass){
                offsets.resize(degree.size()+1);
                for(size_t j=0;j<degree.size();++j) offsets[j+1]=offsets[j]+degree[j];
                arcs.resize(offsets.back());
            }
        }
    }
    void report(Query q,vector<Row>& out,Work& work) {
        if(!w.relevant(g,q)) return;
        int root=first_state[g.edges[q.event].v];
        if(indegree[root]>1) return;
        vector<int> lost{root},changed,decremented;
        for(size_t pos=0;pos<lost.size();++pos){
            int id=lost[pos],v=owners[id];
            if(last_missing[v]<0) changed.push_back(v);
            last_missing[v]=std::max(id,last_missing[v]);
            for(int j=offsets[id];j<offsets[id+1];++j){
                ++work.probes;
                int to=arcs[j];
                if(times[to]>q.deadline) continue;
                decremented.push_back(to);
                if(--indegree[to]==0) lost.push_back(to);
            }
        }
        for(int v:changed){
            int alt=next_state[last_missing[v]];
            emit(out,v,w.first[v],alt<0?NEVER:times[alt],q.deadline);
            last_missing[v]=-1;
        }
        for(int id:decremented) ++indegree[id];
    }
};

