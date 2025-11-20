"""
Otimizador de rotas multi-agente usando algoritmo de Fleury
para cobertura de áreas urbanas baseado em grafos de redes viárias.
"""

import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.lines import Line2D
import osmnx as ox
from shapely.geometry import Polygon
from itertools import combinations
import math
import numpy as np

matplotlib.use("Agg")


class FleuryRouteOptimizer:
    """
    Classe para otimização de rotas de múltiplos agentes usando
    o algoritmo de Fleury em grafos eulerianos.
    """
    
    def __init__(self, reduction_radius_m=800):
        """
        Inicializa o otimizador.
        
        Args:
            reduction_radius_m: Raio em metros para redução da área de processamento
        """
        self.reduction_radius_m = reduction_radius_m
        self.original_graph = None
        self.processed_graph = None
        self.start_node = None
        
    def _calculate_haversine_distance(self, lon1, lat1, lon2, lat2):
        """
        Calcula distância entre duas coordenadas usando fórmula de Haversine.
        
        Args:
            lon1, lat1: Longitude e latitude do ponto 1
            lon2, lat2: Longitude e latitude do ponto 2
            
        Returns:
            Distância em metros
        """
        earth_radius = 6371000.0  # Raio da Terra em metros
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_phi / 2.0) ** 2 + 
             math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
        
        return 2 * earth_radius * math.asin(math.sqrt(a))
    
    def load_graph_from_coordinates(self, coordinates, network_type="walk"):
        """
        Carrega grafo de uma área delimitada por 4 coordenadas.
        
        Args:
            coordinates: Lista de 4 tuplas [(lat1, lon1), (lat2, lon2), (lat3, lon3), (lat4, lon4)]
            network_type: Tipo de rede (walk, drive, bike, all)
            
        Returns:
            Grafo NetworkX da área delimitada
        """
        if len(coordinates) != 4:
            raise ValueError("É necessário fornecer exatamente 4 coordenadas")
        
        # Cria polígono com as coordenadas (formato: lon, lat para Shapely)
        polygon_coords = [(lon, lat) for lat, lon in coordinates]
        polygon = Polygon(polygon_coords)
        
        print(f"Baixando grafo da área delimitada...")
        print(f"Coordenadas: {coordinates}")
        print(f"Área aproximada do polígono: ~{polygon.area * 111**2:.2f} km²")
        
        # Extrai grafo do polígono
        graph = ox.graph_from_polygon(polygon, network_type=network_type, simplify=True)
        
        # Converte para grafo não-direcionado
        try:
            graph = ox.utils_graph.get_undirected(graph)
        except Exception:
            graph = ox.convert.to_undirected(graph)
        
        self.original_graph = graph
        return graph
    
    def load_graph_from_place(self, place_name, network_type="walk"):
        """
        Carrega grafo de um lugar/cidade por nome.
        
        Args:
            place_name: Nome do lugar (ex: "Eloi Mendes, Minas Gerais")
            network_type: Tipo de rede (walk, drive, bike, all)
            
        Returns:
            Grafo NetworkX do lugar
        """
        print(f"Baixando grafo de: {place_name}")
        
        graph = ox.graph_from_place(place_name, network_type=network_type, simplify=True)
        
        # Converte para grafo não-direcionado
        try:
            graph = ox.utils_graph.get_undirected(graph)
        except Exception:
            graph = ox.convert.to_undirected(graph)
        
        self.original_graph = graph
        return graph
    
    def _reduce_graph_by_radius(self, graph, center_node, radius_m):
        """
        Reduz o grafo mantendo apenas nós dentro de um raio do centro.
        
        Args:
            graph: Grafo a ser reduzido
            center_node: Nó central
            radius_m: Raio em metros
            
        Returns:
            Subgrafo reduzido
        """
        center_lon = graph.nodes[center_node]['x']
        center_lat = graph.nodes[center_node]['y']
        
        nodes_within_radius = []
        for node in graph.nodes():
            node_lon = graph.nodes[node]['x']
            node_lat = graph.nodes[node]['y']
            distance = self._calculate_haversine_distance(
                center_lon, center_lat, node_lon, node_lat
            )
            if distance <= radius_m:
                nodes_within_radius.append(node)
        
        subgraph = graph.subgraph(nodes_within_radius).copy()
        return subgraph
    
    def _build_simple_graph(self, multigraph):
        """
        Converte multigrafo em grafo simples mantendo arestas de menor peso.
        
        Args:
            multigraph: MultiGraph do OSMnx
            
        Returns:
            Grafo simples NetworkX
        """
        simple_graph = nx.Graph()
        
        for u, v, data in multigraph.edges(data=True):
            length = data.get("length", data.get("weight", 1.0))
            
            if simple_graph.has_edge(u, v):
                if length < simple_graph[u][v]["weight"]:
                    simple_graph[u][v]["weight"] = length
            else:
                simple_graph.add_edge(u, v, weight=length)
        
        return simple_graph
    
    def _get_edge_length_from_multigraph(self, multigraph, u, v):
        """
        Obtém o menor comprimento de aresta entre dois nós em um multigrafo.
        
        Args:
            multigraph: MultiGraph
            u, v: Nós da aresta
            
        Returns:
            Comprimento mínimo da aresta
        """
        try:
            edge_data = multigraph.get_edge_data(u, v)
            if not edge_data:
                return 1.0
            
            lengths = [
                data.get("length", data.get("weight", 1.0)) 
                for data in edge_data.values()
            ]
            return min(lengths) if lengths else 1.0
        except Exception:
            return 1.0
    
    def _assign_vertices_to_agents(self, simple_graph, start_node, num_agents):
        """
        Particiona vértices do grafo entre agentes balanceando custos.
        
        Args:
            simple_graph: Grafo simples
            start_node: Nó inicial
            num_agents: Número de agentes
            
        Returns:
            Lista de conjuntos de vértices para cada agente
        """
        # Calcula distâncias a partir do nó inicial
        distances = nx.single_source_dijkstra_path_length(
            simple_graph, start_node, weight='weight'
        )
        sorted_nodes = sorted(distances.items(), key=lambda x: x[1])
        sorted_nodes = [node for node, _ in sorted_nodes]
        
        # Inicializa agentes
        agents = [
            {
                'vertices': set([start_node]), 
                'cost': 0.0, 
                'current': start_node
            } 
            for _ in range(num_agents)
        ]
        assigned = set([start_node])
        
        # Atribui vértices aos agentes de forma gulosa
        for vertex in sorted_nodes:
            if vertex in assigned:
                continue
            
            best_agent_idx = None
            best_total_cost = float('inf')
            best_increment = float('inf')
            
            for idx, agent in enumerate(agents):
                try:
                    increment = nx.dijkstra_path_length(
                        simple_graph, agent['current'], vertex, weight='weight'
                    )
                except nx.NetworkXNoPath:
                    increment = float('inf')
                
                total_cost = agent['cost'] + increment
                
                if total_cost < best_total_cost:
                    best_total_cost = total_cost
                    best_agent_idx = idx
                    best_increment = increment
            
            if best_agent_idx is None:
                best_agent_idx = 0
                best_increment = 0
            
            agents[best_agent_idx]['vertices'].add(vertex)
            agents[best_agent_idx]['cost'] += (
                best_increment if best_increment != float('inf') else 0
            )
            agents[best_agent_idx]['current'] = vertex
            assigned.add(vertex)
        
        return [agent['vertices'] for agent in agents]
    
    def _build_connected_subgraph(self, multigraph, simple_graph, vertices_set, start_node):
        """
        Constrói subgrafo conexo contendo os vértices especificados.
        
        Args:
            multigraph: MultiGraph original
            simple_graph: Versão simplificada do grafo
            vertices_set: Conjunto de vértices a incluir
            start_node: Nó inicial
            
        Returns:
            MultiGraph conexo
        """
        subgraph = nx.MultiGraph()
        subgraph.add_nodes_from(vertices_set)
        
        # Conecta vértices via caminhos mínimos
        for vertex in vertices_set:
            if vertex == start_node:
                continue
            
            try:
                path = nx.dijkstra_path(simple_graph, start_node, vertex, weight='weight')
            except nx.NetworkXNoPath:
                # Tenta conectar a partir de outro vértice já no conjunto
                path_found = False
                for source in vertices_set:
                    if source == vertex:
                        continue
                    try:
                        path = nx.dijkstra_path(simple_graph, source, vertex, weight='weight')
                        path_found = True
                        break
                    except nx.NetworkXNoPath:
                        continue
                
                if not path_found:
                    continue
            
            # Adiciona arestas do caminho ao subgrafo
            for i in range(len(path) - 1):
                u = path[i]
                v = path[i + 1]
                weight = self._get_edge_length_from_multigraph(multigraph, u, v)
                subgraph.add_edge(u, v, weight=weight)
        
        # Adiciona arestas diretas entre vértices do conjunto
        for u, v, data in multigraph.edges(data=True):
            if u in vertices_set and v in vertices_set:
                weight = self._get_edge_length_from_multigraph(multigraph, u, v)
                subgraph.add_edge(u, v, weight=weight)
        
        return subgraph
    
    def _make_eulerian_via_matching(self, graph):
        """
        Torna o grafo euleriano adicionando arestas via matching de peso mínimo.
        
        Args:
            graph: Grafo a ser tornado euleriano
            
        Returns:
            MultiGraph euleriano
        """
        # Simplifica para grafo simples
        simple_graph = nx.Graph()
        for u, v, data in graph.edges(data=True):
            weight = data.get('weight', 1.0)
            
            if simple_graph.has_edge(u, v):
                if weight < simple_graph[u][v]['weight']:
                    simple_graph[u][v]['weight'] = weight
            else:
                simple_graph.add_edge(u, v, weight=weight)
        
        # Encontra vértices de grau ímpar
        odd_degree_nodes = [
            node for node in simple_graph.nodes() 
            if simple_graph.degree(node) % 2 == 1
        ]
        
        if not odd_degree_nodes:
            return nx.MultiGraph(simple_graph)
        
        # Constrói grafo completo entre vértices ímpares
        complete_graph = nx.Graph()
        for u, v in combinations(odd_degree_nodes, 2):
            try:
                distance = nx.dijkstra_path_length(
                    simple_graph, u, v, weight='weight'
                )
            except Exception:
                distance = float('inf')
            complete_graph.add_edge(u, v, weight=distance)
        
        # Encontra matching de peso mínimo
        matching = nx.algorithms.matching.min_weight_matching(
            complete_graph, weight="weight"
        )
        
        # Cria multigrafo euleriano
        eulerian_graph = nx.MultiGraph(simple_graph)
        
        # Duplica caminhos mínimos para pares do matching
        for u, v in matching:
            path = nx.dijkstra_path(simple_graph, u, v, weight='weight')
            for i in range(len(path) - 1):
                a = path[i]
                b = path[i + 1]
                weight = simple_graph[a][b].get('weight', 1.0)
                eulerian_graph.add_edge(a, b, weight=weight)
        
        return eulerian_graph
    
    def _get_eulerian_trail(self, multigraph, start_node=None):
        """
        Obtém trilha euleriana a partir de um grafo euleriano.
        
        Args:
            multigraph: MultiGraph euleriano
            start_node: Nó inicial (opcional)
            
        Returns:
            Lista de nós formando a trilha euleriana
        """
        nodes_with_edges = [
            node for node in multigraph.nodes() 
            if multigraph.degree(node) > 0
        ]
        
        if not nodes_with_edges:
            return [start_node] if start_node is not None else []
        
        subgraph = multigraph.subgraph(nodes_with_edges).copy()
        
        if not nx.is_eulerian(subgraph):
            subgraph = self._make_eulerian_via_matching(subgraph)
        
        circuit = list(nx.eulerian_circuit(subgraph, source=start_node))
        
        if not circuit:
            return [start_node] if start_node is not None else []
        
        # Constrói trilha a partir do circuito
        trail = [circuit[0][0]]
        for u, v in circuit:
            trail.append(v)
        
        return trail
    
    def optimize_routes(self, graph, start_node, num_agents):
        """
        Otimiza rotas para múltiplos agentes usando algoritmo de Fleury.
        
        Args:
            graph: Grafo da rede viária
            start_node: Nó inicial para todos os agentes
            num_agents: Número de agentes
            
        Returns:
            Lista de trilhas (uma por agente)
        """
        print(f"\nOtimizando rotas para {num_agents} agentes...")
        
        # Reduz grafo se necessário
        if self.reduction_radius_m is not None:
            graph = self._reduce_graph_by_radius(
                graph, start_node, self.reduction_radius_m
            )
            print(f"Grafo reduzido para raio de {self.reduction_radius_m}m")
        
        # Constrói grafo simples para particionamento
        simple_graph = self._build_simple_graph(graph)
        
        # Particiona vértices entre agentes
        partitions = self._assign_vertices_to_agents(
            simple_graph, start_node, num_agents
        )
        
        # Gera trilha euleriana para cada agente
        agents_trails = []
        for partition_idx, vertices in enumerate(partitions):
            if not vertices:
                agents_trails.append([start_node])
                continue
            
            # Constrói subgrafo conexo para a partição
            subgraph = self._build_connected_subgraph(
                graph, simple_graph, vertices, start_node
            )
            
            # Torna euleriano e obtém trilha
            eulerian_graph = self._make_eulerian_via_matching(subgraph)
            
            # Escolhe nó inicial apropriado
            trail_start = (
                start_node if start_node in eulerian_graph.nodes() 
                else next(iter(eulerian_graph.nodes()))
            )
            
            trail = self._get_eulerian_trail(eulerian_graph, start_node=trail_start)
            agents_trails.append(trail)
        
        self.processed_graph = graph
        return agents_trails
    
    def plot_routes(self, graph, agents_trails, filename="rotas_otimizadas.png"):
        """
        Gera visualização das rotas dos agentes no mapa.
        
        Args:
            graph: Grafo da rede viária
            agents_trails: Lista de trilhas dos agentes
            filename: Nome do arquivo de saída
        """
        print(f"\nGerando visualização...")
        
        # Obtém posições dos nós
        node_positions = {
            node: (graph.nodes[node]['x'], graph.nodes[node]['y']) 
            for node in graph.nodes()
        }
        
        # Identifica nós visitados
        visited_nodes = set()
        for trail in agents_trails:
            for node in trail:
                if node in node_positions:
                    visited_nodes.add(node)
        
        # Calcula limites do mapa
        x_coords = [node_positions[node][0] for node in visited_nodes]
        y_coords = [node_positions[node][1] for node in visited_nodes]
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        # Cria figura
        fig, ax = plt.subplots(figsize=(12, 12))
        ax.set_facecolor("white")
        
        # Desenha grafo base (cinza claro)
        for u, v, data in graph.edges(data=True):
            if u in node_positions and v in node_positions:
                x1, y1 = node_positions[u]
                x2, y2 = node_positions[v]
                ax.plot((x1, x2), (y1, y2), color="lightgray", linewidth=0.4, alpha=0.8)
        
        # Prepara cores para agentes
        cmap = matplotlib.colormaps.get_cmap("tab10")
        agent_colors = [cmap(i) for i in range(len(agents_trails))]
        
        legend_handles = []
        
        def get_edge_length(u, v):
            """Obtém comprimento da aresta"""
            data = graph.get_edge_data(u, v)
            if not data:
                return 0
            return min([d.get("length", d.get("weight", 0)) for d in data.values()])
        
        # Desenha trilhas dos agentes
        for agent_idx, trail in enumerate(agents_trails):
            color = agent_colors[agent_idx]
            edges = [(trail[j], trail[j + 1]) for j in range(len(trail) - 1)]
            
            total_distance = 0.0
            
            # Desenha cada aresta
            for u, v in edges:
                if u in node_positions and v in node_positions:
                    total_distance += get_edge_length(u, v)
                    x1, y1 = node_positions[u]
                    x2, y2 = node_positions[v]
                    ax.plot((x1, x2), (y1, y2), linewidth=2.0, color=color, alpha=0.9)
            
            # Desenha nós únicos
            unique_nodes = set(trail)
            xs = [node_positions[node][0] for node in unique_nodes if node in node_positions]
            ys = [node_positions[node][1] for node in unique_nodes if node in node_positions]
            ax.scatter(xs, ys, color=color, s=8, zorder=5)
            
            # Adiciona à legenda
            legend_handles.append(
                Line2D([0], [0], color=color, lw=3,
                       label=f"Agente {agent_idx + 1} — {total_distance / 1000:.2f} km")
            )
        
        # Ajusta limites com padding
        padding = 0.002
        ax.set_xlim(min_x - padding, max_x + padding)
        ax.set_ylim(min_y - padding, max_y + padding)
        
        # Adiciona legenda
        ax.legend(handles=legend_handles, loc="upper right", fontsize=9)
        
        # Remove eixos
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect("equal")
        
        # Salva figura
        fig.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close(fig)
        
        print(f">>> Arquivo gerado: {filename}")
    
    def get_start_node_from_centroid(self, graph):
        """
        Calcula nó inicial a partir do centróide do grafo.
        
        Args:
            graph: Grafo NetworkX
            
        Returns:
            ID do nó mais próximo ao centróide
        """
        x_coords = [graph.nodes[node]['x'] for node in graph.nodes()]
        y_coords = [graph.nodes[node]['y'] for node in graph.nodes()]
        
        centroid_x = float(np.mean(x_coords))
        centroid_y = float(np.mean(y_coords))
        
        start_node = ox.nearest_nodes(graph, centroid_x, centroid_y)
        self.start_node = start_node
        
        return start_node

