import os
import numpy as np
import pandas as pd
from math import radians, sin, cos, sqrt, atan2


# distância Haversine em metros
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # raio da Terra em metros
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def find_central_node(coords_df):
    """Retorna o ID do nó mais central usando geodesic median (soma mínima de distâncias)."""
    ids = coords_df["id"].tolist()
    n = len(ids)

    # matriz lat/lon
    lats = coords_df["lat"].to_numpy()
    lons = coords_df["lon"].to_numpy()

    # soma das distâncias geográficas
    total_distances = []

    for i in range(n):
        dist_sum = 0
        for j in range(n):
            if i == j:
                continue
            dist_sum += haversine(lats[i], lons[i], lats[j], lons[j])
        total_distances.append((ids[i], dist_sum))

    # menor soma → nó central
    central_node = min(total_distances, key=lambda x: x[1])[0]
    return int(central_node)


def build_adj_matrix(matrix_path=None, edges_path=None, coords_path=None):
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    MATRIX_PATH = matrix_path or os.path.join(BASE_DIR, "dados_processados", "matriz_adjacencia.csv")
    EDGES_PATH = edges_path or os.path.join(BASE_DIR, "dados_processados", "arestas_calc_test.csv")
    COORDS_PATH = coords_path or os.path.join(BASE_DIR, "dados_processados", "vertices_reordenados.csv")

    if not os.path.exists(MATRIX_PATH):
        raise FileNotFoundError(f"Matriz não encontrada: {MATRIX_PATH}")
    if not os.path.exists(EDGES_PATH):
        raise FileNotFoundError(f"Arquivo de arestas não encontrado: {EDGES_PATH}")
    if not os.path.exists(COORDS_PATH):
        raise FileNotFoundError(f"Arquivo de coordenadas não encontrado: {COORDS_PATH}")

    mat_df = pd.read_csv(MATRIX_PATH, index_col=0)
    nodes = [int(c) for c in mat_df.columns]
    nodes_sorted = sorted(nodes)
    N = len(nodes_sorted)

    edges_df = pd.read_csv(EDGES_PATH)
    coords_df = pd.read_csv(COORDS_PATH)

    # calcular nó central via distância geográfica
    central_node = find_central_node(coords_df)

    # lookup de arestas
    edge_lookup = {}
    for _, row in edges_df.iterrows():
        u = int(row["origem"])
        v = int(row["destino"])
        edge_lookup[(u, v)] = row
        edge_lookup[(v, u)] = row

    adj_ids = np.zeros((N, N), dtype=int)
    edges_mapping = {}
    next_id = 1

    # montar adj
    for i, u in enumerate(nodes_sorted):
        for j, v in enumerate(nodes_sorted):
            try:
                dist = float(mat_df.at[u, str(v)])
            except Exception:
                dist = float(mat_df.at[u, v])

            if dist and dist > 0.0:
                if adj_ids[i, j] != 0:
                    continue

                edge_row = edge_lookup.get((u, v))
                if edge_row is not None:
                    distancia_m = float(edge_row.get("distancia_m", dist))
                    n_casas = int(edge_row.get("n_casas", round(distancia_m / 8)))
                else:
                    distancia_m = float(dist)
                    n_casas = int(round(distancia_m / 8))

                eid = next_id
                next_id += 1

                edges_mapping[eid] = {
                    "origem": int(u),
                    "destino": int(v),
                    "distancia_m": distancia_m,
                    "n_casas": n_casas,
                }

                adj_ids[i, j] = eid
                adj_ids[j, i] = eid

    return adj_ids, edges_mapping, nodes_sorted, central_node