import os
import sys
# garantir que o root do projeto esteja no sys.path para permitir imports locais
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from codigo_fonte.setup_grafo.build_adj_matrix_from_csv import build_adj_matrix

import networkx as nx
from networkx.algorithms.community import kernighan_lin_bisection

def build_multigraph_from_adj(adj_ids, edges_mapping, nodes):
    """Constrói MultiGraph a partir da matriz `adj_ids` e do dicionário `edges_mapping`.

    - `adj_ids`: numpy array N x N onde cada entrada é um eid (0 = sem aresta)
    - `nodes`: lista de nós ordenada correspondendo às linhas/colunas de `adj_ids`
    - `edges_mapping`: dicionário eid -> atributos
    """
    G = nx.MultiGraph()
    N = adj_ids.shape[0]
    for i in range(N):
        for j in range(i + 1, N):
            eid = int(adj_ids[i, j])
            if eid and eid in edges_mapping:
                u = int(nodes[i])
                v = int(nodes[j])
                e = edges_mapping[eid]
                dist = float(e.get("distancia_m", 0.0))
                n_casas = int(e.get("n_casas", 0))
                G.add_edge(u, v, key=eid, eid=eid, distancia_m=dist, n_casas=n_casas)
    return G


def recursive_kernighan_lin(G, k):
    if k <= 1:
        return [set(G.nodes())]
    if k == 2:
        try:
            A, B = kernighan_lin_bisection(G)
            return [set(A), set(B)]
        except Exception:
            nodes_local = list(G.nodes())
            h = len(nodes_local) // 2
            return [set(nodes_local[:h]), set(nodes_local[h:])]

    try:
        A, B = kernighan_lin_bisection(G)
    except Exception:
        nodes_local = list(G.nodes())
        h = len(nodes_local) // 2
        A = set(nodes_local[:h])
        B = set(nodes_local[h:])

    kA = k // 2
    kB = k - kA
    GA = G.subgraph(A).copy()
    GB = G.subgraph(B).copy()
    return recursive_kernighan_lin(GA, kA) + recursive_kernighan_lin(GB, kB)


def make_eulerian_multigraph(G):
    H = nx.MultiGraph(G)
    odd = [n for n, d in H.degree() if d % 2 == 1]
    if not odd:
        return H

    # preparar grafo simples com pesos mínimos entre pares
    W = nx.Graph()
    for u, v, data in H.edges(data=True):
        w = data.get("distancia_m", 1.0)
        if W.has_edge(u, v):
            if w < W[u][v]["weight"]:
                W[u][v]["weight"] = w
        else:
            W.add_edge(u, v, weight=w)

    odd_set = set(odd)
    while odd_set:
        u = odd_set.pop()
        best_v = None
        best_dist = float("inf")
        for v in list(odd_set):
            try:
                d = nx.shortest_path_length(W, u, v, weight="weight")
                if d < best_dist:
                    best_dist = d
                    best_v = v
            except nx.NetworkXNoPath:
                continue
        if best_v is None:
            continue
        odd_set.remove(best_v)
        path = nx.shortest_path(W, u, best_v, weight="weight")
        for a, b in zip(path[:-1], path[1:]):
            found = False
            if H.has_edge(a, b):
                for key, data in H[a][b].items():
                    attrs = dict(data)
                    H.add_edge(a, b, **attrs)
                    found = True
                    break
            if not found:
                H.add_edge(a, b, distancia_m=W[a][b]["weight"], n_casas=round(W[a][b]["weight"]/8))
    return H


def hierholzer_circuit(H):
    if any(d % 2 == 1 for _, d in H.degree()):
        raise ValueError("Grafo não é Euleriano")
    circuit = []
    for u, v, key in nx.eulerian_circuit(H, keys=True):
        # preferir o atributo 'eid' se presente; caso contrário usar a key
        data = H.get_edge_data(u, v, key)
        eid = None
        if data is not None:
            eid = data.get("eid", key)
        else:
            eid = key
        circuit.append((u, v, eid))
    return circuit


def circuits_to_trails(H, circuits):
    """Converter uma lista de circuitos (cada circuito = lista de (u,v,eid))
    em trilhas reutilizáveis: dict com 'edge_ids', 'nodes', 'distance_m', 'n_casas'.
    Aceita opcionalmente um prefixo (approach_edges) que representa o caminho
    a partir do nó central até o início do circuito. Quando fornecido, inclui
    a informação de 'approach' no dicionário de cada trilha.
    """
    trails = []
    for circ in circuits:
        if not circ:
            continue
        # construir sequência de nós e arestas
        nodes_seq = [circ[0][0]]
        edge_ids = []
        total_dist = 0.0
        total_n_casas = 0
        for u, v, eid in circ:
            nodes_seq.append(v)
            edge_ids.append(eid)
            # procurar atributos da aresta no MultiGraph H
            data_found = None
            if H.has_edge(u, v):
                for key_k, dat in H[u][v].items():
                    if dat.get("eid") == eid or key_k == eid:
                        data_found = dat
                        break
                if data_found is None:
                    # fallback: pegar a primeira aresta entre u,v
                    key_k, data_found = next(iter(H[u][v].items()))
            if data_found is not None:
                total_dist += float(data_found.get("distancia_m", 0.0))
                total_n_casas += int(data_found.get("n_casas", 0))
        trails.append({
            "nodes": nodes_seq,
            "edge_ids": edge_ids,
            "distance_m": total_dist,
            "n_casas": total_n_casas,
        })
    return trails


def divide_graphs(n_parts):
    # obter dados somente quando necessário
    adj_ids, edges_mapping, nodes,centrl = build_adj_matrix()
    G = build_multigraph_from_adj(adj_ids, edges_mapping, nodes)
    parts = recursive_kernighan_lin(G, n_parts)
    return parts


def generate_agent_trail(n_agents=2):
    # carregar dados quando a função é chamada (evita import-time side-effects)
    adj_ids, edges_mapping, nodes, central_node = build_adj_matrix()
    print(central_node)
    G = build_multigraph_from_adj(adj_ids, edges_mapping, nodes)
    # construir grafo simples com peso mínimo entre pares para cálculo de caminhos
    G_simple = nx.Graph()
    for u, v, data in G.edges(data=True):
        w = data.get("distancia_m", 1.0)
        if G_simple.has_edge(u, v):
            if w < G_simple[u][v]["weight"]:
                G_simple[u][v]["weight"] = w
        else:
            G_simple.add_edge(u, v, weight=w)
    parts = recursive_kernighan_lin(G, n_agents)
    results = {}
    for i, part_nodes in enumerate(parts):
        Gi = G.subgraph(part_nodes).copy()
        Hi = make_eulerian_multigraph(Gi)
        circuits = []
        trails = []
        for comp in nx.connected_components(Hi):
            subH = Hi.subgraph(comp).copy()
            if len(subH.edges()) == 0:
                continue
            if any(d % 2 == 1 for _, d in subH.degree()):
                subH = make_eulerian_multigraph(subH)
            circ = hierholzer_circuit(subH)

            # Garantir que o circuito comece em `central_node`.
            # Se o componente contém `central_node`, apenas rotacionamos o circuito.
            # Caso contrário, encontramos o nó do componente mais próximo de `central_node`
            # (pelo menor caminho no `G_simple`) e precedemos o circuito com o caminho desde
            # `central_node` até esse nó, usando arestas existentes em `G`.
            if central_node is not None:
                nodes_in_sub = set(subH.nodes())
                if central_node in nodes_in_sub:
                    # rotacionar circ para começar em central_node
                    # construir sequência de nós do circuito
                    nodes_seq = [c[0] for c in circ]
                    try:
                        pos = nodes_seq.index(central_node)
                        circ = circ[pos:] + circ[:pos]
                    except ValueError:
                        pass
                else:
                    # encontrar nó alvo no componente com menor distância a central_node
                    best_target = None
                    best_dist = float('inf')
                    for v in nodes_in_sub:
                        try:
                            d = nx.shortest_path_length(G_simple, central_node, v, weight='weight')
                            if d < best_dist:
                                best_dist = d
                                best_target = v
                        except Exception:
                            continue
                    if best_target is not None:
                        try:
                            path = nx.shortest_path(G_simple, central_node, best_target, weight='weight')
                            # converter path em arestas (u,v,eid) usando G
                            path_edges = []
                            for a, b in zip(path[:-1], path[1:]):
                                if G.has_edge(a, b):
                                    # escolher a primeira aresta entre a e b
                                    key = next(iter(G[a][b].keys()))
                                    data = G[a][b][key]
                                    eid = data.get('eid', key)
                                    path_edges.append((a, b, eid))
                            # preceder o circuito com o caminho encontrado
                            circ = path_edges + circ
                        except Exception:
                            pass

            circuits.append(circ)
            # converter circuito em trilha reutilizável
            trails_comp = circuits_to_trails(subH, [circ])
            trails.extend(trails_comp)
        results[i] = {"nodes": set(part_nodes), "circuits": circuits, "trails": trails}
    print(results[0])
    print(results[1])
    return results


if __name__ == "__main__":
    out = generate_agent_trail(n_agents=4)
    for agent, info in out.items():
        total_edges = sum(len(c) for c in info.get("circuits", []))
        total_trails = len(info.get("trails", []))
        print(f"Agente {agent}: nós={len(info['nodes'])}, componentes com circuito={len(info.get('circuits', []))}, arestas percorridas~={total_edges}, trilhas={total_trails}")

