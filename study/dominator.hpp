#pragma once
#include "components.hpp"
#include <memory>

 
 
struct DominatorIndex {
    struct Node {int parent,jump,depth,mark;};
    vector<Node> dom{{0,0,0,0}};
    std::unique_ptr<ComponentIndex> result;
    int64_t state_count=0,intersections=0;
    int next(int parent,int mark){
        int j=dom[parent].jump,k=dom[j].jump;
        int skip=dom[parent].depth-dom[j].depth==dom[j].depth-dom[k].depth ? k:parent;
        dom.push_back({parent,skip,dom[parent].depth+1,mark});return int(dom.size())-1;
    }
    int lca(int a,int b){
        ++intersections;
        if(dom[a].depth<dom[b].depth) std::swap(a,b);
        while(dom[a].depth>dom[b].depth){
            int j=dom[a].jump;a=dom[j].depth>=dom[b].depth?j:dom[a].parent;
        }
        while(a!=b){
            if(dom[a].jump!=dom[b].jump){a=dom[a].jump;b=dom[b].jump;}
            else {a=dom[a].parent;b=dom[b].parent;}
        }
        return a;
    }
    DominatorIndex(const Contacts& g,int src,bool trim){
        Witness witness(g,src);
        HistoryIndex h(g);
        vector<int> state(g.n,-1),pending(g.n,-1),touched,births;
        vector<int> event{-1},parent_mark{0},mark_depth{0};
        state[src]=0;
        for(int i=g.begin;i<int(g.edges.size());){
            int t=g.edges[i].t;
            touched.clear();
            do {
                auto [u,v,ignored]=g.edges[i];
                if(state[u]>=0 && v!=src && !(trim && state[v]==0)){
                    int p=state[u];
                    if(witness.via[v]==i){
                        int prior=dom[p].mark;
                        int marker=int(event.size());event.push_back(i);parent_mark.push_back(prior);
                        mark_depth.push_back(mark_depth[prior]+1);p=next(p,marker);
                    }
                    if(pending[v]==-1) {
                        touched.push_back(v);
                        pending[v]=state[v]<0?p:lca(state[v],p);
                    }else pending[v]=lca(pending[v],p);
                }
                ++i;
            }while(i<int(g.edges.size()) && g.edges[i].t==t);
            for(int v:touched){
                int p=pending[v],marker=dom[p].mark,old=state[v]<0?-1:dom[state[v]].mark;
                if(old<0 && marker){
                    h.histories[v].birth_node=marker;births.push_back(v);
                }
                if(old!=marker && (marker || old>0)) {
                    h.histories[v].changes.emplace_back(t,mark_depth[marker]);++h.history_count;
                }
                state[v]=trim && !marker?0:next(p,marker);pending[v]=-1;
            }
        }
        state_count=dom.size()-1;
        vector<Node>().swap(dom);
        vector<int> ordinal(event.size(),-1);ordinal[0]=0;
        for(int v:births) ordinal[h.histories[v].birth_node]=0;
        for(int m=1;m<int(event.size());++m) if(ordinal[m]==0){
            int id=int(h.event_of.size()),p=ordinal[parent_mark[m]];
            if(p<0) throw std::logic_error("unreachable dominating event");
            ordinal[m]=id;h.event_of.push_back(event[m]);h.parent.push_back(p);
            h.depth.push_back(h.depth[p]+1);h.children.emplace_back();h.children[p].push_back(id);
            h.births.emplace_back();h.node_of[g.edges[event[m]].v]=id;
            if(mark_depth[m]!=h.depth[id]) throw std::logic_error("unmapped ancestor");
        }
        for(int v:births){
            int& marker=h.histories[v].birth_node;marker=ordinal[marker];h.births[marker].push_back(v);
        }
        result=std::make_unique<ComponentIndex>(g,h,births,ComponentIndex::MIXED);
    }
    void report(Query q,vector<Row>& rows,Work& work) const {result->report(q,rows,work);}
};

