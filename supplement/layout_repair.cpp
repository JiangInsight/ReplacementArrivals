
#include "expansion/baselines.hpp"
#include <windows.h>
#include <psapi.h>
#include <iostream>
#include <string>

struct Bytes {uint64_t size=0,capacity=0;};
Bytes operator+(Bytes a,Bytes b){return {a.size+b.size,a.capacity+b.capacity};}
template<class T> Bytes flat(const vector<T>& a){return {sizeof(T)*a.size(),sizeof(T)*a.capacity()};}
Bytes nested(const vector<vector<int>>& a){
    Bytes b=flat(a);  
    for(const auto& v:a)b=b+flat(v);
    return b;
}
uint64_t peak(){
    PROCESS_MEMORY_COUNTERS x{};
    if(!GetProcessMemoryInfo(GetCurrentProcess(),&x,sizeof(x)))throw std::runtime_error("working set");
    return x.PeakWorkingSetSize;
}
void report(const Contacts& g,Bytes witness,Bytes adj,Bytes state,size_t header,uint64_t pre,uint64_t hi){
    auto input=flat(g.edges), total=witness+adj+state;
    std::cout<<witness.size<<" "<<witness.capacity<<" "<<adj.size<<" "<<adj.capacity<<" "
        <<state.size<<" "<<state.capacity<<" "<<header<<" "<<input.size<<" "<<input.capacity<<" "
        <<sizeof(Contacts)<<" "<<pre<<" "<<hi<<" "<<total.size<<" "<<total.capacity<<"\n";
}
int main(int argc,char** argv)try{
    if(argc!=6)throw std::runtime_error("file n source release method");
    Contacts g;g.n=std::stoi(argv[2]);g.begin=std::stoi(argv[4]);int src=std::stoi(argv[3]);
    std::ifstream in(argv[1],std::ios::binary|std::ios::ate);
    auto length=in.tellg();if(length<=0 || length%sizeof(Event))throw std::runtime_error("input");
    in.seekg(0);g.edges.resize(size_t(length)/sizeof(Event));in.read(reinterpret_cast<char*>(g.edges.data()),length);
    if(!in)throw std::runtime_error("read");
    uint64_t pre=peak();
    if(std::string(argv[5])=="repair"){
        Repair x(g,src);uint64_t hi=peak();
        report(g,flat(x.w.first)+flat(x.w.via),nested(x.children)+flat(x.offsets)+flat(x.incoming),
               flat(x.stamp)+flat(x.recovered),sizeof(x),pre,hi);
    }else if(std::string(argv[5])=="decremental"){
        Decremental x(g,src);uint64_t hi=peak();
        report(g,flat(x.w.first)+flat(x.w.via),nested(x.incoming)+nested(x.outgoing),
               flat(x.dead)+flat(x.stamp)+flat(x.in_pos)+flat(x.out_pos)+flat(x.current),sizeof(x),pre,hi);
    }else throw std::runtime_error("method");
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}

