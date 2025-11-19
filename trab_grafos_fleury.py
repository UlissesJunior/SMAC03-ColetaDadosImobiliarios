
from datetime import datetime
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
from itertools import combinations
import math
import time
import matplotlib
from matplotlib.lines import Line2D
matplotlib.use("Agg")

# statics
REDUCTION_RADIUS_M = 800  

# calcula dist de duas coords
def haversine(lon1, lat1, lon2, lat2):
    R = 6371000.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    return 2*R*math.asin(math.sqrt(a))


def build_simple_graph_from_osm(G_osm):
    G_simple = nx.Graph()
    for u, v, data in G_osm.edges(data=True):
        length = data.get("length", data.get("weight", 1.0))
        if G_simple.has_edge(u, v):
            if length < G_simple[u][v]["weight"]:
                G_simple[u][v]["weight"] = length
        else:
            G_simple.add_edge(u, v, weight=length)
    return G_simple

def get_edge_length_multigraph(G_multi, u, v):
    try:
        data_dict = G_multi.get_edge_data(u, v)
        if not data_dict:
            return 1.0
        lengths = [d.get("length", d.get("weight", 1.0)) for d in data_dict.values()]
        return min(lengths) if lengths else 1.0
    except Exception:
        return 1.0

def assign_vertices_to_agents(G_simple, start, n_agents):
    dist = nx.single_source_dijkstra_path_length(G_simple, start, weight='weight')
    nodes_sorted = sorted(dist.items(), key=lambda x: x[1])
    nodes_sorted = [v for v, _ in nodes_sorted]

    agents = [{'vertices': set([start]), 'cost': 0.0, 'current': start} for _ in range(n_agents)]
    assigned = set([start])

    for v in nodes_sorted:
        if v in assigned:
            continue
        best_agent = None
        best_total = float('inf')
        best_inc = float('inf')

        for idx, a in enumerate(agents):
            try:
                inc = nx.dijkstra_path_length(G_simple, a['current'], v, weight='weight')
            except nx.NetworkXNoPath:
                inc = float('inf')
            total = a['cost'] + inc
            if total < best_total:
                best_total = total
                best_agent = idx
                best_inc = inc

        if best_agent is None:
            best_agent = 0
            best_inc = 0

        agents[best_agent]['vertices'].add(v)
        agents[best_agent]['cost'] += best_inc if best_inc != float('inf') else 0
        agents[best_agent]['current'] = v
        assigned.add(v)

    return [a['vertices'] for a in agents]


def reduce_graph_by_radius(G_osm, start_node, radius_m):
    lon0 = G_osm.nodes[start_node]['x']; lat0 = G_osm.nodes[start_node]['y']
    nodes_in = []
    for n in G_osm.nodes():
        lon = G_osm.nodes[n]['x']; lat = G_osm.nodes[n]['y']
        d = haversine(lon0, lat0, lon, lat)
        if d <= radius_m:
            nodes_in.append(n)
    SG = G_osm.subgraph(nodes_in).copy()
    return SG

def build_connected_subgraph(G_osm, G_simple, vertices_set, start):
    SG = nx.MultiGraph()
    SG.add_nodes_from(vertices_set)
    for v in vertices_set:
        if v == start:
            continue
        try:
            path = nx.dijkstra_path(G_simple, start, v, weight='weight')
        except nx.NetworkXNoPath:
            found = False
            for s in vertices_set:
                if s == v:
                    continue
                try:
                    path = nx.dijkstra_path(G_simple, s, v, weight='weight')
                    found = True
                    break
                except nx.NetworkXNoPath:
                    continue
            if not found:
                continue
        for i in range(len(path)-1):
            u = path[i]; w = path[i+1]
            wt = get_edge_length_multigraph(G_osm, u, w)
            SG.add_edge(u, w, weight=wt)
    for u, v, data in G_osm.edges(data=True):
        if u in vertices_set and v in vertices_set:
            wt = get_edge_length_multigraph(G_osm, u, v)
            SG.add_edge(u, v, weight=wt)
    return SG


def make_eulerian_via_matching(G):
    S = nx.Graph()
    for u, v, data in G.edges(data=True):
        w = data.get('weight', 1.0)
        if S.has_edge(u, v):
            if w < S[u][v]['weight']:
                S[u][v]['weight'] = w
        else:
            S.add_edge(u, v, weight=w)

    odd = [n for n in S.nodes() if S.degree(n) % 2 == 1]
    if not odd:
        return nx.MultiGraph(S)
    # constroi grafo completo entre impares com pesos = shortest path length
    K = nx.Graph()
    for u, v in combinations(odd, 2):
        try:
            d = nx.dijkstra_path_length(S, u, v, weight='weight')
        except Exception:
            d = float('inf')
        K.add_edge(u, v, weight=d)

    matching = nx.algorithms.matching.min_weight_matching(K, weight="weight")
    MG = nx.MultiGraph(S)  # começar com simple convertido para multigafp

    # duplica caminho mimimo nos nos paread
    for u, v in matching:
        path = nx.dijkstra_path(S, u, v, weight='weight')
        for i in range(len(path)-1):
            a = path[i]; b = path[i+1]
            w = S[a][b].get('weight', 1.0)
            MG.add_edge(a, b, weight=w)
    return MG
 
def get_eulerian_trail(MG, start=None):
    nodes_with_edges = [n for n in MG.nodes() if MG.degree(n) > 0]
    if not nodes_with_edges:
        return [start] if start is not None else []
    H = MG.subgraph(nodes_with_edges).copy()
    if not nx.is_eulerian(H):
        H = make_eulerian_via_matching(H)
    circuit = list(nx.eulerian_circuit(H, source=start) )
    if not circuit:
        return [start] if start is not None else []
    trail = [circuit[0][0]]
    for u, v in circuit:
        trail.append(v)
    return trail


def plot_agents_on_map(G_osm, agents_trails, filename="mapa_rotas_opt.png"):
    import matplotlib
    from matplotlib.lines import Line2D
    matplotlib.use("Agg")


    pos = {n: (G_osm.nodes[n]['x'], G_osm.nodes[n]['y']) for n in G_osm.nodes()} 
    visited_nodes = set()
    for trail in agents_trails:
        for n in trail:
            if n in pos:
                visited_nodes.add(n)

    xs = [pos[n][0] for n in visited_nodes]
    ys = [pos[n][1] for n in visited_nodes]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_facecolor("white")
    
    for u, v, data in G_osm.edges(data=True):
        if u in pos and v in pos:
            x1, y1 = pos[u]; x2, y2 = pos[v]
            ax.plot((x1, x2), (y1, y2), color="lightgray", linewidth=0.4, alpha=0.8)

    cmap = matplotlib.colormaps.get_cmap("tab10")
    colors = [cmap(i) for i in range(len(agents_trails))]

    legend_handles = []

    def get_length(u, v):
        data = G_osm.get_edge_data(u, v)
        if not data:
            return 0
        return min([d.get("length", d.get("weight", 0)) for d in data.values()])

    # desenho trilhas dos agentes
    for i, trail in enumerate(agents_trails):
        color = colors[i]
        edges = [(trail[j], trail[j+1]) for j in range(len(trail)-1)]

        total_dist = 0.0

        # desenha cada aresta do agente
        for u, v in edges:
            if u in pos and v in pos:
                total_dist += get_length(u, v)
                x1, y1 = pos[u]; x2, y2 = pos[v]
                ax.plot((x1, x2), (y1, y2), linewidth=2.0, color=color, alpha=0.9)

        # desenha os nos discretos
        unique_nodes = set(trail)
        xs = [pos[n][0] for n in unique_nodes if n in pos]
        ys = [pos[n][1] for n in unique_nodes if n in pos]
        ax.scatter(xs, ys, color=color, s=8, zorder=5) 

        # legenda (km)
        legend_handles.append(
            Line2D([0], [0], color=color, lw=3,
                   label=f"Agente {i+1} — {total_dist/1000:.2f} km")
        )

    # calculo bouding
    padding = 0.002  # margem pequena ao redor
    ax.set_xlim(min_x - padding, max_x + padding)
    ax.set_ylim(min_y - padding, max_y + padding)

    # legenda
    ax.legend(handles=legend_handles, loc="upper right", fontsize=9)

    # remove eixos (estética)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")

    fig.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f">>> arquivo gerado: {filename}")



def multi_agent_fleury_partitioned_fast(G_osm, start, n_agents, reduction_radius_m=REDUCTION_RADIUS_M):
    # reduz grafo para área local (evita processamento massivo)
    if reduction_radius_m is not None:
        G_osm = reduce_graph_by_radius(G_osm, start, reduction_radius_m)
    G_simple = build_simple_graph_from_osm(G_osm)

    partitions = assign_vertices_to_agents(G_simple, start, n_agents)

    agents_trails = []
    for p_idx, vertices in enumerate(partitions):
        if not vertices:
            agents_trails.append([start])
            continue
        SG = build_connected_subgraph(G_osm, G_simple, vertices, start)
        EG = make_eulerian_via_matching(SG)
        # escolher start adequado
        start_node = start if start in EG.nodes() else next(iter(EG.nodes()))
        trail = get_eulerian_trail(EG, start=start_node)
        agents_trails.append(trail)
    return agents_trails

if __name__ == "__main__":
    bairro = "Eloi Mendes, Minas Gerais"
    n_agents = 10

    print("baixando grafo (pode demorar alguns segundos)...")
    t_start = time.time()
    G = ox.graph_from_place(bairro, network_type="walk", simplify=True)
    # conserta direcao
    try:
        G = ox.utils_graph.get_undirected(G)
    except Exception:
        G = ox.convert.to_undirected(G)
    xs = [G.nodes[n]['x'] for n in G.nodes()]
    ys = [G.nodes[n]['y'] for n in G.nodes()]
    centroid_x = float(np.mean(xs)); centroid_y = float(np.mean(ys))
    start = ox.nearest_nodes(G, centroid_x, centroid_y)
    print(f"nós no grafo: {len(G.nodes())}, start: {start}, tempo download: {time.time() - t_start:.1f}s")

    # roda pipeline
    t0 = time.time()
    trails = multi_agent_fleury_partitioned_fast(G, start, n_agents, reduction_radius_m=REDUCTION_RADIUS_M)
    print("tempo total pipeline (s):", time.time() - t0)

    # gera imagem
    file_timestamp = time.time()
    file_datetime = datetime.fromtimestamp(file_timestamp).strftime("%d-%m-%Y_%H-%M-%S")

    plot_agents_on_map(G,trails,f"teste_rotas_{file_datetime}.png")

