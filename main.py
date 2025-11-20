"""
Script principal para otimização de rotas usando algoritmo de Fleury.
Permite extrair grafos por coordenadas específicas ou por nome de cidade.
"""

from datetime import datetime
import time
import os
from fleury_optimizer import FleuryRouteOptimizer

# ============= CONSTANTES =============

# Raio de redução para processamento (em metros) - usado APENAS no modo "ByPlace"
# None = processar grafo completo
# Valor numérico = limitar área ao redor do ponto inicial
REDUCTION_RADIUS_M = 800

# Coordenadas da área de Eloi Mendes (formato: latitude, longitude)
ELOIMENDES_UPLEFT = (-21.608187, -45.571433)    # Ponta esquerda cima (noroeste)
ELOIMENDES_UPRIGHT = (-21.607853, -45.563601)   # Ponta direita cima (nordeste)
ELOIMENDES_DOWNRIGHT = (-21.611558, -45.563553) # Ponta direita baixo (sudeste)
ELOIMENDES_DOWNLEFT = (-21.611553, -45.571562)  # Ponta esquerda baixo (sudoeste)

def main():
    """
    Função principal do programa.
    """
    # ============= CONFIGURAÇÃO =============
    
    # Escolha o modo de operação
    USE_COORDINATES = False  # True = usar coordenadas | False = usar nome de cidade
    
    # Número de agentes para otimização
    NUM_AGENTS = 3
    
    # Tipo de rede viária (walk, drive, bike, all)
    NETWORK_TYPE = "walk"
    
    # ============= INICIALIZAÇÃO =============
    
    print("\n" + "=" * 70)
    print("OTIMIZADOR DE ROTAS - ALGORITMO DE FLEURY MULTI-AGENTE")
    print("=" * 70)
    
    # Cria instância do otimizador
    optimizer = FleuryRouteOptimizer(reduction_radius_m=REDUCTION_RADIUS_M)
    
    # ============= CARREGAMENTO DO GRAFO =============
    
    start_time = time.time()
    
    if USE_COORDINATES:
        # Modo: Extração por coordenadas
        print("\n[MODO] Extração por coordenadas\n")
        
        # Define coordenadas da área
        coordinates = [
            ELOIMENDES_UPLEFT,    # Ponta esquerda cima (noroeste)
            ELOIMENDES_UPRIGHT,   # Ponta direita cima (nordeste)
            ELOIMENDES_DOWNRIGHT, # Ponta direita baixo (sudeste)
            ELOIMENDES_DOWNLEFT,  # Ponta esquerda baixo (sudoeste)
        ]
        
        print("Coordenadas da área:")
        print(f"  • Noroeste (cima-esquerda):  {ELOIMENDES_UPLEFT}")
        print(f"  • Nordeste (cima-direita):   {ELOIMENDES_UPRIGHT}")
        print(f"  • Sudeste (baixo-direita):   {ELOIMENDES_DOWNRIGHT}")
        print(f"  • Sudoeste (baixo-esquerda): {ELOIMENDES_DOWNLEFT}")
        print()
        
        # Carrega grafo das coordenadas
        graph = optimizer.load_graph_from_coordinates(
            coordinates, 
            network_type=NETWORK_TYPE
        )
        
    else:
        # Modo: Extração por nome de cidade
        city = "Eloi Mendes"
        state = "Minas Gerais"
        place_name = f"{city}, {state}"
        
        print(f"\n[MODO] Extração por cidade/lugar\n")
        print(f"Local: {place_name}\n")
        
        # Carrega grafo do lugar
        graph = optimizer.load_graph_from_place(
            place_name, 
            network_type=NETWORK_TYPE
        )
    
    download_time = time.time() - start_time
    
    # Calcula nó inicial (centróide)
    start_node = optimizer.get_start_node_from_centroid(graph)
    
    print(f"\n[INFORMAÇÕES DO GRAFO]")
    print(f"  • Nós (vértices): {len(graph.nodes())}")
    print(f"  • Arestas: {len(graph.edges())}")
    print(f"  • Nó inicial (centróide): {start_node}")
    print(f"  • Tempo de download: {download_time:.2f}s")
    
    # ============= OTIMIZAÇÃO DE ROTAS =============
    
    print("\n" + "-" * 70)
    optimization_start = time.time()
    
    # Escolhe método de otimização baseado no modo
    if USE_COORDINATES:
        # Modo coordenadas: usa cobertura total (todas as ruas)
        agents_trails = optimizer.optimize_routes_full_coverage(
            graph, 
            start_node, 
            NUM_AGENTS
        )
    else:
        # Modo cidade: usa método com particionamento e redução de raio
        agents_trails = optimizer.optimize_routes(
            graph, 
            start_node, 
            NUM_AGENTS
        )
    
    optimization_time = time.time() - optimization_start
    
    print(f"\n[RESULTADOS]")
    print(f"  • {NUM_AGENTS} agentes processados")
    print(f"  • Tempo de otimização: {optimization_time:.2f}s")
    
    # Calcula estatísticas
    total_edges_walked = sum(len(trail) - 1 for trail in agents_trails)
    
    # Conta arestas únicas cobertas
    covered_edges = set()
    for trail in agents_trails:
        for i in range(len(trail) - 1):
            u, v = trail[i], trail[i+1]
            edge = tuple(sorted([u, v]))  # Normaliza a aresta
            covered_edges.add(edge)
    
    total_graph_edges = len(graph.edges())
    coverage_percent = (len(covered_edges) / total_graph_edges * 100) if total_graph_edges > 0 else 0
    
    print(f"  • Total de arestas percorridas: {total_edges_walked}")
    print(f"  • Arestas únicas cobertas: {len(covered_edges)} de {total_graph_edges} ({coverage_percent:.1f}%)")
    
    # Aviso de cobertura incompleta apenas no modo coordenadas (onde é esperado 100%)
    if USE_COORDINATES and coverage_percent < 100:
        print(f"  ATENÇÃO: {total_graph_edges - len(covered_edges)} arestas NÃO foram cobertas!")
    
    # ============= VISUALIZAÇÃO =============
    
    print("\n" + "-" * 70)
    
    # Cria pasta para salvar os grafos
    graphs_folder = "graphs"
    if not os.path.exists(graphs_folder):
        os.makedirs(graphs_folder)
        print(f"Pasta '{graphs_folder}' criada.")
    
    # Define nome do método usado
    method_name = "ByCoordinates" if USE_COORDINATES else "ByPlace"
    
    # Gera nome do arquivo com método e timestamp
    current_timestamp = time.time()
    formatted_datetime = datetime.fromtimestamp(current_timestamp).strftime(
        "%d-%m-%Y_%H-%M-%S"
    )
    output_filename = os.path.join(graphs_folder, f"{method_name}_{formatted_datetime}.png")
    
    # Plota rotas
    optimizer.plot_routes(graph, agents_trails, output_filename)
    
    # ============= FINALIZAÇÃO =============
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 70)
    print(f"[CONCLUÍDO] Tempo total: {total_time:.2f}s")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()