# ----------------------------------------------------------------------
# PASSO 2: CALCULAR PESOS (DISTÂNCIAS) DAS ARESTAS
#
# Este script é o segundo passo do setup do grafo. Ele "junta" a
# estrutura do grafo (quem se conecta com quem) com as
# coordenadas geográficas de cada vértice.
#
# Ele lê a lista de adjacência e o CSV de vértices, ambos resultados
# de um tratamento manual (TRABAIERA ZzzZZZzz !!!), e para cada aresta (u, v) definida,
# calcula a distância geodésica (Haversine) entre os dois pontos.
#
# Entrada: dados_processados/vertices_reordenados.csv (Tratado manualmente)
# Entrada: dados_processados/adjacency.txt (Tratado manualmente)
# Saída:   dados_processados/arestas_calc.csv (Lista: u, v, distancia_m)
# ----------------------------------------------------------------------


import os
import csv
import math
import sys


ADJ_PATH = r"dados_processados/adjacency.txt"
VERT_PATH = r"dados_processados/vertices_reordenados.csv"
OUT_DIR   = r"dados_processados"

# Arquivo final
OUT_CSV = os.path.join(OUT_DIR, "arestas_calc.csv")



def read_vertices(path):
    verts = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = [h.strip().lower() for h in next(reader)]

        try:
            id_i = header.index("id")
        except ValueError:
            id_i = 0

        if "lat" in header and "lon" in header:
            lat_i = header.index("lat")
            lon_i = header.index("lon")
        else:
            lat_i = id_i + 1
            lon_i = id_i + 2

        for row in reader:
            if not row or len(row) <= max(id_i, lat_i, lon_i):
                continue
            try:
                vid = int(row[id_i])
                lat = float(row[lat_i])
                lon = float(row[lon_i])
                # correção se lat/lon vierem invertidos
                if abs(lat) > 90 and abs(lon) <= 90:
                    lat, lon = lon, lat
                verts[vid] = (lat, lon)
            except Exception:
                continue
    return verts


def parse_adj_text(text):
    adj = {}
    for line in text.strip().splitlines():
        if ":" not in line:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].isdigit():
                key = int(parts[0])
                vals = " ".join(parts[1:])
            else:
                continue
        else:
            key, vals = line.split(":", 1)
            key = key.strip()
            vals = vals.strip()

        try:
            k = int(key)
        except:
            continue

        nums = []
        for token in vals.replace(";", ",").split(","):
            for sub in token.strip().split():
                try:
                    nums.append(int(sub))
                except:
                    pass

        adj[k] = sorted(set(nums))
    return adj


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c



def main():

    base = os.getcwd()

    adj_file  = os.path.join(base, ADJ_PATH)
    vert_file = os.path.join(base, VERT_PATH)
    out_csv   = os.path.join(base, OUT_CSV)

    if not os.path.exists(adj_file):
        print("❌ adjacency.txt não encontrado em:", adj_file)
        sys.exit(1)

    if not os.path.exists(vert_file):
        print("❌ vertices_reordenados.csv não encontrado em:", vert_file)
        sys.exit(1)

    os.makedirs(os.path.join(base, OUT_DIR), exist_ok=True)

    print("1) Lendo vértices…")
    verts = read_vertices(vert_file)
    print(f"   → {len(verts)} vértices lidos.")

    print("2) Lendo lista de adjacência…")
    with open(adj_file, "r", encoding="utf-8") as fh:
        adj = parse_adj_text(fh.read())
    print(f"   → {len(adj)} linhas de adjacência lidas.")

    print("3) Calculando arestas…")
    edges = []
    seen = set()

    for u, neighs in adj.items():
        if u not in verts:
            print(f"⚠️ vértice {u} presente na adjacência mas ausente nos vértices.")
            continue

        lat_u, lon_u = verts[u]

        for v in neighs:
            if v not in verts:
                print(f"⚠️ vizinho {v} não está na lista de vértices.")
                continue

            pair = tuple(sorted((u, v)))
            if pair in seen:
                continue
            seen.add(pair)

            lat_v, lon_v = verts[v]
            d = haversine_m(lat_u, lon_u, lat_v, lon_v)
            edges.append((pair[0], pair[1], d))

    edges.sort(key=lambda x: (x[0], x[1]))

    print("4) Salvando CSV de arestas…")
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["origem", "destino", "distancia_m"])
        for u, v, d in edges:
            w.writerow([u, v, f"{d:.3f}"])

    print("\n✅ Finalizado.")
    print("Arquivo salvo em:", out_csv)


if __name__ == "__main__":
    main()
