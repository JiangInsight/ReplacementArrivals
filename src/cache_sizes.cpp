#define main source_cache_main
#include "source_cache.cpp"
#undef main

int main(int argc, char **argv) try {
    if (argc != 5) throw std::runtime_error("contacts vertices source release");
    Contacts graph;
    graph.n = std::stoi(argv[2]);
    graph.begin = std::stoi(argv[4]);
    auto bytes = std::filesystem::file_size(argv[1]);
    if (bytes % sizeof(Event)) throw std::runtime_error("invalid graph");
    graph.edges.resize(bytes / sizeof(Event));
    std::ifstream input(argv[1], std::ios::binary);
    if (!input.read(reinterpret_cast<char *>(graph.edges.data()), bytes))
        throw std::runtime_error("input");
    int source = std::stoi(argv[3]);
    { ComponentIndex index(graph, source, ComponentIndex::MIXED); std::cout << retained(index) << " "; }
    { PointStateIndex index(graph, source); std::cout << retained(index) << " "; }
    { Repair index(graph, source); std::cout << retained(index) << "\n"; }
    return 0;
} catch (const std::exception &e) { std::cerr << e.what() << "\n"; return 1; }
