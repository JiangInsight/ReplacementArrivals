#pragma once
#include "cascade.hpp"
#include <array>

class RankDictionary {
    EventDictionary sparse;
    vector<uint64_t> present;
    vector<int> prefix,values;
    int rank(int key) const {
        int word=key>>6,bit=key&63;
        return prefix[word]+ones(present[word]&((uint64_t(1)<<bit)-1));
    }
public:
    void build(const vector<std::pair<int,int>>& pairs){
        if(pairs.empty()) return;
        int largest=0;for(auto p:pairs) largest=std::max(largest,p.first);
        if(uint64_t(largest)+1>128*pairs.size()){sparse.build(pairs);return;}
        present.resize((largest>>6)+1);prefix.resize(present.size());values.resize(pairs.size());
        for(auto p:pairs) present[p.first>>6]|=uint64_t(1)<<(p.first&63);
        int count=0;
        for(size_t i=0;i<present.size();++i){prefix[i]=count;count+=ones(present[i]);}
        for(auto p:pairs) values[rank(p.first)]=p.second;
    }
    int find(int key) const {
        if(present.empty()) return sparse.find(key);
        if(key<0 || size_t(key>>6)>=present.size() || !(present[key>>6]&(uint64_t(1)<<(key&63)))) return -1;
        return values[rank(key)];
    }
    size_t bytes() const {return sparse.bytes()+present.capacity()*8+(prefix.capacity()+values.capacity())*4;}
};

struct ComponentIndex {
    enum Kind { EXPLICIT, DIRECT, CATALOG };
    enum Policy { MIXED, GLOBAL, ALL_PAIRS, NO_EXPLICIT, NO_DIRECT, NO_CATALOG,
                  NO_UNIFORM, NO_PRUNE, NO_LINKS };
    bool prune=true;
    struct Site {int vertex,before,end,skip,handle,depth;};
    struct Cost {
        std::array<int64_t,3> bytes{};
        void add(const Cost& other){for(int i=0;i<3;++i) bytes[i]+=other.bytes[i];}
        int best() const {return int(std::min_element(bytes.begin(),bytes.end())-bytes.begin());}
    };
    RankDictionary dict;
    CascadeIndex catalog{CascadeIndex::ADAPTIVE};
    vector<int> offsets,dense;
    vector<Row> rows;
    vector<Site> sites;
    int root_counts[3]{};
    int64_t possible_pairs=0;
    size_t bytes() const{
        return sizeof(*this)+dict.bytes()+catalog.bytes()-sizeof(catalog)+rows.capacity()*sizeof(Row)+
               sites.capacity()*sizeof(Site)+(offsets.capacity()+dense.capacity())*sizeof(int);
    }
    static bool uniform(const vector<std::pair<int,int>>& h){
        return h.size()==1 || (h.size()==2 && h.back().second==0);
    }
    ComponentIndex(const Contacts& g,int source,Policy policy,const vector<std::pair<int,int>>* departures=nullptr){
        vector<int> births;
        HistoryIndex h(g,source,false,&births,departures);
        encode(g,h,births,policy);
    }
    ComponentIndex(const Contacts& g,const HistoryIndex& h,const vector<int>& births,Policy policy){
        encode(g,h,births,policy);
    }
    void encode(const Contacts& g,const HistoryIndex& h,const vector<int>& births,Policy policy){
        prune=policy!=NO_PRUNE;
        if(policy==NO_LINKS) catalog.mode=CascadeIndex::BINARY;
        const int n=int(h.event_of.size());
        if(births.size()>size_t(NEVER/3)) throw std::length_error("dispatch ordinal exceeds this build");
        vector<int> root(n),mass(n),row_id(n,-1);
        vector<Cost> costs(n);
        for(int x=1;x<n;++x) {
            root[x]=h.parent[x]?root[h.parent[x]]:x;
            costs[root[x]].bytes[EXPLICIT]+=sizeof(int);
            mass[x]=int(h.births[x].size());
        }
        for(int v:births){
            const auto& history=h.histories[v];
            int x=history.birth_node,d=h.depth[x];
            const auto& changes=history.changes;
            auto& c=costs[root[x]];
            c.bytes[EXPLICIT]+=sizeof(Row)*int64_t(d);
            c.bytes[DIRECT]+=sizeof(Site)+(uniform(changes)?0:int64_t(d)*sizeof(int));
            c.bytes[CATALOG]+=sizeof(CascadeIndex::Site)+changes.size()*sizeof(changes[0]);
            if(changes.size()>8 && d-changes.back().second>=64)
                c.bytes[CATALOG]+=2*changes.size()*sizeof(CascadeIndex::Link);
            possible_pairs+=d;
        }
        Cost sum;
        for(int x:h.children[0]) sum.add(costs[x]);
        vector<int> kind(n);
        for(int x:h.children[0]){
            if(policy==NO_EXPLICIT) costs[x].bytes[EXPLICIT]=INT64_MAX;
            if(policy==NO_DIRECT) costs[x].bytes[DIRECT]=INT64_MAX;
            if(policy==NO_CATALOG) costs[x].bytes[CATALOG]=INT64_MAX;
            kind[x]=policy==ALL_PAIRS?int(EXPLICIT):(policy==GLOBAL?sum.best():costs[x].best());
            ++root_counts[kind[x]];
        }
        for(int x=n-1;x>0;--x) mass[h.parent[x]]+=mass[x];
        vector<char> direct_nodes(n),catalog_nodes(n);
        vector<std::pair<int,int>> keys;
        keys.reserve(n-1);
        int64_t total=0;
        for(int x=1;x<n;++x){
            int type=kind[root[x]];
            if(type==DIRECT){direct_nodes[x]=1;continue;}
            if(type==CATALOG){catalog_nodes[x]=1;continue;}
            if(total+mass[x]>NEVER) throw std::length_error("pair offset exceeds this build");
            row_id[x]=int(offsets.size());offsets.push_back(int(total));total+=mass[x];
            keys.emplace_back(h.event_of[x],row_id[x]*3+EXPLICIT);
        }
        offsets.push_back(int(total));rows.resize(size_t(total));
        auto write=offsets;
        for(int v:births){
            const auto& local=h.histories[v];
            if(kind[root[local.birth_node]]!=EXPLICIT) continue;
            size_t next=1;
            for(int x=local.birth_node;x;x=h.parent[x]){
                while(next<local.changes.size() && local.changes[next].second>=h.depth[x]) ++next;
                int after=next<local.changes.size()?local.changes[next].first:NEVER;
                rows[write[row_id[x]]++]={v,local.changes.front().first,after};
            }
        }
        vector<std::pair<int,int>> selected;
        if(root_counts[DIRECT]){
            CascadeIndex layout(CascadeIndex::BINARY);
            layout.assemble(g,h,&direct_nodes,&selected);
            sites.reserve(layout.sites.size());
            for(const auto& s:layout.sites){
                const auto& local=h.histories[s.vertex].changes;
                int depth=local.front().second;
                int handle;
                if(policy!=NO_UNIFORM && uniform(local)) handle=local.size()==1?NEVER:local[1].first;
                else {
                    if(dense.size()+depth>size_t(NEVER)) throw std::length_error("depth table exceeds this build");
                    handle=~int(dense.size());
                    dense.resize(dense.size()+depth);
                    size_t next=1;
                    for(int d=depth;d>=1;--d){
                        while(next<local.size() && local[next].second>=d) ++next;
                        dense[(~handle)+d-1]=next<local.size()?local[next].first:NEVER;
                    }
                }
                sites.push_back({s.vertex,s.before,s.ending,s.skip,handle,depth});
            }
            for(auto p:selected) keys.emplace_back(p.first,p.second*3+DIRECT);
        }
        if(root_counts[CATALOG]){
            catalog.assemble(g,h,&catalog_nodes,&selected);
            for(auto p:selected) keys.emplace_back(p.first,p.second*3+CATALOG);
        }
        dict.build(keys);
    }
    void report(Query q,vector<Row>& out,Work& work) const {
        int key=dict.find(q.event);if(key<0) return;
        int type=key%3,idx=key/3;
        if(type==CATALOG){catalog.report_from(idx,q.deadline,out,work,prune);return;}
        if(type==EXPLICIT){
            for(int j=offsets[idx];j<offsets[idx+1];++j){
                auto r=rows[j];if(r.before>q.deadline){if(prune)break;continue;}
                emit(out,r.vertex,r.before,r.after,q.deadline);++work.probes;
            }
            return;
        }
        int d=sites[idx].depth;
        for(int j=idx;j<sites[idx].end;){
            const auto& s=sites[j];
            if(s.before>q.deadline){j=prune?s.skip:j+1;continue;}
            int after=s.handle>=0?s.handle:dense[(~s.handle)+d-1];
            emit(out,s.vertex,s.before,after,q.deadline);++work.probes;++j;
        }
    }
};
