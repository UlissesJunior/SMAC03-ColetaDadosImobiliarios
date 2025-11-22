from typing import Dict, List, Tuple
import networkx as nx
import math

from fleury_optimizer import FleuryRouteOptimizer

def _nearest_to_centroid(pos: Dict[int, Tuple[float,float]]) -> int:
    # pos[u] = (lon, lat)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
    return min(pos.keys(), key=lambda u: (pos[u][0]-cx)**2 + (pos[u][1]-cy)**2)

def clusterizar_vertices(adj: Dict[int, List[int]],
                         pos: Dict[int, Tuple[float, float]],
                         k: int,
                         pesos: Dict[Tuple[int,int], float] = None,
                         start_node: int = None) -> List[List[int]]:
    """
    adj: {u: [v,...]} (grafo não-dirigido)
    pos: {u: (lon, lat)}
    k:   número de agentes/partições
    pesos: {(min(u,v),max(u,v)): peso} opcional (tempo/distância). Se None, peso=1.
    start_node: opcional; se None usa vértice mais perto do centróide
    """
    G = nx.Graph()
    # adiciona nós com coordenadas (x=lon, y=lat) para compatibilidade
    for u, (lon, lat) in pos.items():
        G.add_node(u, x=lon, y=lat)
    # adiciona arestas com peso
    for u, viz in adj.items():
        for v in viz:
            if u == v:
                continue
            a, b = (u, v) if u < v else (v, u)
            w = 1.0
            if pesos is not None:
                w = float(pesos.get((a, b), 1.0))
            if not G.has_edge(u, v) or w < G[u][v].get('weight', float('inf')):
                G.add_edge(u, v, weight=w)

    if start_node is None:
        start_node = _nearest_to_centroid(pos)

    # usa só a parte de clusterização do Fleury (guloso por Dijkstra)
    fro = FleuryRouteOptimizer()
    clusters_sets = fro._assign_vertices_to_agents(G, start_node, k)  # <- reutilização direta
    # converte para listas ordenadas (opcional)
    clusters = [sorted(list(s)) for s in clusters_sets]
    return clusters
