#pragma once
#include "contact.hpp"
#include <utility>


class EventDictionary {
    struct Bucket { uint64_t mul=1; int start=-1,bits=0; };
    vector<Bucket> buckets;
    vector<std::pair<int,int>> slots;
    uint64_t state=711,outer=1;
    int width=0;
    uint64_t multiplier(){
        uint64_t z=(state+=0x9e3779b97f4a7c15ULL);
        z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;
        z=(z^(z>>27))*0x94d049bb133111ebULL;
        return (z^(z>>31))|1ULL;
    }
    static size_t hash(int key,uint64_t mul,int bits){
        return bits ? (uint64_t(uint32_t(key))*mul)>>(64-bits) : 0;
    }
public:
    size_t bytes() const {return buckets.capacity()*sizeof(Bucket)+slots.capacity()*sizeof(slots[0]);}
    void build(const vector<std::pair<int,int>>& input){
        if(input.empty()) return;
        size_t n=1;
        while(n<input.size()) {n*=2;++width;}
        vector<int> count(n),offset(n+1);
        while(true){
            std::fill(count.begin(),count.end(),0);outer=multiplier();
            for(auto [key,value]:input) ++count[hash(key,outer,width)];
            uint64_t sum=0;for(int c:count) sum+=uint64_t(c)*c;
            if(sum<=6*input.size()) break;
        }
        for(size_t i=0;i<n;++i) offset[i+1]=offset[i]+count[i];
        auto cursor=offset;
        vector<std::pair<int,int>> ordered(input.size());
        for(auto p:input) ordered[cursor[hash(p.first,outer,width)]++]=p;
        buckets.resize(n);
        for(size_t i=0;i<n;++i){
            int c=count[i];if(!c) continue;
            auto& b=buckets[i];size_t size=1;
            const uint64_t target=c==1 ? 1:2ULL*c*c;
            while(size<target) {size*=2;++b.bits;}
            b.start=int(slots.size());
            slots.resize(slots.size()+size,{-1,-1});
            for(;;){
                b.mul=multiplier();
                bool good=true;
                for(int j=offset[i];j<offset[i+1];++j){
                    auto p=ordered[j];
                    auto& dest=slots[b.start+hash(p.first,b.mul,b.bits)];
                    if(dest.first!=-1){good=false;break;}
                    dest=p;
                }
                if(good) break;
                std::fill_n(slots.begin()+b.start,size,std::make_pair(-1,-1));
            }
        }
    }
    int find(int key) const {
        if(buckets.empty()) return -1;
        const auto& b=buckets[hash(key,outer,width)];
        if(b.start<0) return -1;
        auto p=slots[b.start+hash(key,b.mul,b.bits)];
        return p.first==key?p.second:-1;
    }
};
