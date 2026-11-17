#include "cascade.hpp"
#include "components.hpp"
#include "dag.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>

template<class Index>
void enumerate(Index& index,int count,int horizon,std::ofstream& wire,int64_t& positives,int64_t& changed,int& largest){
    vector<Row> rows;
    Work work;
    for(int i=0;i<count;++i){
        rows.clear();
        index.report({i,horizon},rows,work);
        if(rows.empty()) continue;
        std::sort(rows.begin(),rows.end(),[](Row a,Row b){return a.vertex<b.vertex;});
        int size=int(rows.size());
        ++positives;changed+=size;largest=std::max(largest,size);
        wire.write(reinterpret_cast<const char*>(&i),sizeof i);
        wire.write(reinterpret_cast<const char*>(&size),sizeof size);
        wire.write(reinterpret_cast<const char*>(rows.data()),sizeof(Row)*size);
    }
}

int main(int argc,char** argv) try {
    if(argc!=7) throw std::runtime_error("census INPUT N SOURCE HORIZON_INDEX METHOD WIRE");
    std::ifstream in(argv[1],std::ios::binary|std::ios::ate);
    auto bytes=in.tellg();
    if(bytes<=0 || bytes%sizeof(Event)) throw std::runtime_error("invalid input");
    Contacts g;g.begin=0;g.n=std::stoi(argv[2]);g.edges.resize(size_t(bytes)/sizeof(Event));
    in.seekg(0);in.read(reinterpret_cast<char*>(g.edges.data()),bytes);
    if(!in) throw std::runtime_error("read failed");
    int src=std::stoi(argv[3]),h=g.edges.at(std::stoi(argv[4])).t;
     
    int count=int(std::upper_bound(g.edges.begin(),g.edges.end(),h,
        [](int t,const Event& e){return t<e.t;})-g.edges.begin());
    int64_t positives=0,changed=0;int largest=0;
    std::ofstream wire(argv[6],std::ios::binary);
    std::string arm=argv[5];
    auto run=[&](auto&& index){enumerate(index,count,h,wire,positives,changed,largest);};
    if(arm=="dag") run(DagReplay(g,src));
    else if(arm=="repair") run(Repair(g,src));
    else if(arm=="flatpairs") run(FlatPairs(g,src));
    else if(arm=="adaptive") run(CascadeIndex(g,src,CascadeIndex::ADAPTIVE));
    else if(arm=="mix") run(ComponentIndex(g,src,ComponentIndex::MIXED));
    else throw std::runtime_error("unknown method");
    wire.close();if(!wire) throw std::runtime_error("write failed");
    std::cout<<"{\"eligible\":"<<count<<",\"positive\":"<<positives<<",\"rows\":"<<changed
             <<",\"max_rows\":"<<largest<<",\"deadline\":"<<h<<"}\n";
    return 0;
} catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}

