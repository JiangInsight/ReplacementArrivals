#pragma once
#include "histories.hpp"
#include "dictionary.hpp"
#ifdef _MSC_VER
#include <intrin.h>
#endif
inline int ones(uint64_t bits){
#ifdef _MSC_VER
    return int(__popcnt64(bits));
#else
    return __builtin_popcountll(bits);
#endif
}

struct CascadeIndex {
    enum Mode { BINARY, ALL, ADAPTIVE };
    struct Site {
        int vertex,before,begin,count;
        int left=-1,right=-1,ending=-1,skip=-1;
        int catalog=0,length=0,start_rank=0;
        uint64_t mask=0;
    };
    struct Link {int key,local,left,right;};
    vector<Site> sites;
    vector<std::pair<int,int>> entries;
    vector<Link> links;
    EventDictionary dict;
    Mode mode;
    size_t hard_sites=0;
    size_t bytes() const {
        return sizeof(*this)+sites.capacity()*sizeof(Site)+entries.capacity()*sizeof(entries[0])+
               links.capacity()*sizeof(Link)+dict.bytes();
    }
    explicit CascadeIndex(Mode choice):mode(choice){}
    CascadeIndex(const Contacts& g,int src,Mode choice):mode(choice){
        HistoryIndex h(g,src,false);
        assemble(g,h,nullptr,nullptr);
    }
    void assemble(const Contacts& g,const HistoryIndex& h,const vector<char>* selected,
                  vector<std::pair<int,int>>* external){
        auto allowed=[&](int n){return !selected || (*selected)[n];};
        if(selected && std::find(selected->begin(),selected->end(),1)==selected->end()) return;
        vector<int> left(g.n,-1),right(g.n,-1),owner(g.n,-1),pos(g.n,-1);
        auto representative=[&](int node){return g.edges[h.event_of[node]].v;};
        auto birth=[&](int v){return h.histories[v].changes.front().first;};
        for(int node=1;node<int(h.event_of.size());++node){
            if(!allowed(node)) continue;
            int p=representative(node),last=-1;
            const auto& leaves=h.births[node];
            const auto& kids=h.children[node];
            size_t i=1,j=0;
            if(leaves.front()!=p) throw std::logic_error("birth owner");
            while(i<leaves.size() || j<kids.size()){
                int child;
                if(j==kids.size() || (i<leaves.size() && birth(leaves[i])<=birth(representative(kids[j]))))
                    child=leaves[i++];
                else child=representative(kids[j++]);
                owner[child]=p;
                if(last<0) left[p]=child;else right[last]=child;
                last=child;
            }
        }
        for(int root:h.children[0]){
            if(!allowed(root)) continue;
            vector<int> pending{representative(root)};
            while(!pending.empty()){
                int v=pending.back();pending.pop_back();
                const auto& local=h.histories[v].changes;
                pos[v]=int(sites.size());
                sites.push_back({v,birth(v),int(entries.size()),int(local.size())});
                auto& s=sites.back();
                if(local.front().second-local.back().second<64){
                    for(auto [t,d]:local) s.mask|=uint64_t(1)<<(d-local.back().second);
                }
                entries.insert(entries.end(),local.begin(),local.end());
                if(right[v]>=0) pending.push_back(right[v]);
                if(left[v]>=0) pending.push_back(left[v]);
            }
        }
        vector<int> sizes(sites.size(),1);
        vector<std::pair<int,int>> keys;
        for(int n=1;n<int(h.event_of.size());++n) if(allowed(n)) keys.emplace_back(h.event_of[n],pos[representative(n)]);
        if(external) *external=std::move(keys);else dict.build(keys);
        for(int i=int(sites.size())-1;i>=0;--i){
            auto& s=sites[i];int v=s.vertex;
            if(owner[v]>=0) sizes[pos[owner[v]]]+=sizes[i];
            s.ending=i+sizes[i];
            s.left=left[v]<0?-1:pos[left[v]];
            s.right=right[v]<0?-1:pos[right[v]];
            if(mode!=BINARY) catalog(i);
        }
        for(auto& s:sites) s.skip=owner[s.vertex]<0?s.ending:sites[pos[owner[s.vertex]]].ending;
    }
    int child_length(int child) const {return child<0?0:sites[child].length;}
    int child_key(int child,int i) const {return links[sites[child].catalog+i].key;}
    bool need(const Site& s) const {return mode==ALL || (s.count>8 && !s.mask);}
    void catalog(int i){
        auto& s=sites[i];
        const int n=need(s)?s.count:0,nl=child_length(s.left),nr=child_length(s.right);
        if(mode==ADAPTIVE && n) ++hard_sites;
        s.catalog=int(links.size());
        int own=0,a=1,b=1,lb=0,rb=0;
        while(own<n || a<nl || b<nr){
            int key=NEVER;
            if(own<n) key=-entries[s.begin+own].second;
            if(a<nl) key=std::min(key,child_key(s.left,a));
            if(b<nr) key=std::min(key,child_key(s.right,b));
            if(own<n && -entries[s.begin+own].second==key) ++own;
            if(a<nl && child_key(s.left,a)==key) a+=2;
            if(b<nr && child_key(s.right,b)==key) b+=2;
            while(lb<nl && child_key(s.left,lb)<=key) ++lb;
            while(rb<nr && child_key(s.right,rb)<=key) ++rb;
            links.push_back({key,own,lb,rb});++s.length;
            if(key<=-entries[s.begin].second) s.start_rank=s.length;
        }
    }
    int local_rank(const Site& s,int depth,const Link& link) const {
        if(mode==BINARY){
            auto begin=entries.begin()+s.begin;
            return int(std::upper_bound(begin,begin+s.count,depth,
                [](int d,const auto& entry){return d>entry.second;})-begin);
        }
        if(need(s)) return link.local;
        if(s.count<=8){
            int i=0;while(i<s.count && entries[s.begin+i].second>=depth) ++i;
            return i;
        }
        int shift=std::max(0,depth-entries[s.begin+s.count-1].second);
        return shift>=64?0:ones(s.mask>>shift);
    }
    void report(Query q,vector<Row>& out,Work& work) const {
        report_from(dict.find(q.event),q.deadline,out,work);
    }
    void report_from(int root,int deadline,vector<Row>& out,Work& work,bool prune=true) const {
        if(root<0 || sites[root].before>deadline) return;
        int d=entries[sites[root].begin].second;
        auto output=[&](const Site& s,const Link& link){
            int rank=local_rank(s,d,link);
            int recovery=rank<s.count?entries[s.begin+rank].first:NEVER;
            emit(out,s.vertex,s.before,recovery,deadline);++work.probes;
        };
        const Link zero{0,0,0,0};
        if(links.empty()){
            for(int i=root;i<sites[root].ending;){
                const auto& s=sites[i];
                if(s.before>deadline) i=prune?s.skip:i+1;
                else {output(s,zero);++i;}
            }
            return;
        }
        vector<std::pair<int,int>> stack{{root,sites[root].start_rank}};
        while(!stack.empty()){
            auto [i,rank]=stack.back();stack.pop_back();
            const auto& s=sites[i];if(s.before>deadline && prune) continue;
            const Link& here=rank?links[s.catalog+rank-1]:zero;
            if(s.before<=deadline) output(s,here);
            auto descend=[&](int c,int bridge){
                if(c<0) return;
                if(bridge<sites[c].length && child_key(c,bridge)<=-d) ++bridge;
                stack.emplace_back(c,bridge);
            };
            if(i!=root) descend(s.right,here.right);
            descend(s.left,here.left);
        }
    }
};


struct FlatPairs {
    EventDictionary dict;
    vector<int> offsets;
    vector<Row> rows;
    FlatPairs(const Contacts& g,int src){
        HistoryIndex index(g,src,true);
        vector<std::pair<int,int>> keys;
        offsets.resize(index.pairs.size()+1);
        rows.reserve(index.pair_count);
        for(int x=1;x<int(index.pairs.size());++x){
            keys.emplace_back(index.event_of[x],x);
            offsets[x]=int(rows.size());
            rows.insert(rows.end(),index.pairs[x].begin(),index.pairs[x].end());
        }
        offsets.back()=int(rows.size());
        dict.build(keys);
    }
    size_t bytes() const {
        return sizeof(*this)+dict.bytes()+offsets.capacity()*sizeof(int)+rows.capacity()*sizeof(Row);
    }
    void report(Query q,vector<Row>& out,Work& work) const {
        int x=dict.find(q.event);if(x<0) return;
        for(int i=offsets[x];i<offsets[x+1];++i){
            auto r=rows[i];if(r.before>q.deadline) break;
            ++work.probes;emit(out,r.vertex,r.before,r.after,q.deadline);
        }
    }
};
