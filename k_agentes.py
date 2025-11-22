# -*- coding: utf-8 -*-
import os
import re
import csv
import math
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict, deque

BASE = "dados_processados"
OUT  = "resultados_finais/rotas_k_clusters"
SOLVER = os.path.join("codigo_fonte", "algoritmo_cpp", "resolver_cpp.py")


# -----------------------------
# Leitura dos dados do projeto
# -----------------------------

def ler_adj(path: str) -> Dict[int, List[int]]:
    adj: Dict[int, List[int]] = {}
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            if ":" not in s:
                raise ValueError(f"adjacency.txt linha {ln}: faltou ':' → {s}")
            u_str, rest = s.split(":", 1)
            u = int(u_str.strip())
            tokens = [t for t in re.split(r"[,\s]+", rest.strip()) if t]
            vs: List[int] = []
            for t in tokens:
                if not t.isdigit():
                    raise ValueError(f"adjacency.txt linha {ln}: vizinho inválido {t!r}")
                v = int(t)
                if v != u:
                    vs.append(v)
            adj[u] = vs
    # torna simétrico (grafo não-dirigido)
    for u, vs in list(adj.items()):
        for v in vs:
            adj.setdefault(v, [])
            if u not in adj[v]:
                adj[v].append(u)
    return adj


def ler_pos(vertices_csv: str) -> Dict[int, Tuple[float, float]]:
    # headers esperados: id,lat,lon
    pos: Dict[int, Tuple[float, float]] = {}
    with open(vertices_csv, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            u = int(row["id"])
            lat = float(row["lat"])
            lon = float(row["lon"])
            pos[u] = (lon, lat)  # (x=lon, y=lat)
    return pos


def ler_pesos(arestas_csv: str) -> Dict[Tuple[int, int], float]:
    # headers esperados: origem,destino,distancia_m
    W: Dict[Tuple[int, int], float] = {}
    with open(arestas_csv, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            u = int(row["origem"])
            v = int(row["destino"])
            w = float(row["distancia_m"])  # troque para "tempo" quando atualizar o modelo de custo
            a, b = (u, v) if u < v else (v, u)
            W[(a, b)] = w
    return W


# -----------------------------
# Utilidades geométricas
# -----------------------------

def centroid(pos: Dict[int, Tuple[float, float]], vertices: List[int]) -> Tuple[float, float]:
    xs = [pos[u][0] for u in vertices if u in pos]
    ys = [pos[u][1] for u in vertices if u in pos]
    if not xs:  # fallback raro
        return (0.0, 0.0)
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def dist2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


# -----------------------------
# Componentes por lista de arestas
# -----------------------------

def componentes_por_arestas(E: List[Tuple[int, int, float]]) -> List[set]:
    adj_local = defaultdict(list)
    V = set()
    for u, v, _ in E:
        adj_local[u].append(v)
        adj_local[v].append(u)
        V.add(u)
        V.add(v)
    vis = set()
    comps: List[set] = []
    for s in V:
        if s in vis:
            continue
        q = deque([s])
        vis.add(s)
        comp = {s}
        while q:
            u = q.popleft()
            for w in adj_local[u]:
                if w not in vis:
                    vis.add(w)
                    q.append(w)
                    comp.add(w)
        comps.append(comp)
    return comps


# -----------------------------
# Clusterização (adaptador)
# -----------------------------

def clusterizar_vertices(adj, pos, k, pesos=None) -> List[List[int]]:
    from codigo_fonte.cluster.usar_cluster import clusterizar_vertices as impl
    return impl(adj, pos, k, pesos=pesos)


# -----------------------------
# Execução do solver por matriz
# -----------------------------

def rodar_solver(matriz_csv: Path) -> float:
    # limpa saída global antes de rodar
    global_out = Path("resultados_finais/relatorio_tour")
    if global_out.exists():
        shutil.rmtree(global_out)

    subprocess.run(["python", SOLVER, str(matriz_csv)], check=True)

    # captura custo
    cost_file = global_out / "tour_cost.txt"
    custo = 0.0
    if cost_file.exists():
        txt = cost_file.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", txt.replace(",", "."))
        if m:
            custo = float(m.group(1))
    return custo, global_out


# -----------------------------
# Pipeline k-agentes
# -----------------------------

def main(k: int):
    # 1) ler base
    adj = ler_adj(os.path.join(BASE, "adjacency.txt"))
    pos = ler_pos(os.path.join(BASE, "vertices_reordenados.csv"))
    W   = ler_pesos(os.path.join(BASE, "arestas_calc.csv"))

    # 2) clusterizar vértices (k grupos)
    clusters = clusterizar_vertices(adj, pos, k, pesos=W)
    centroids = [centroid(pos, c) for c in clusters]

    # 3) distribuir arestas para clusters (cada aresta tem exatamente um dono)
    edges: List[Tuple[int, int, float]] = []
    for u, vs in adj.items():
        for v in vs:
            if u < v:
                w = float(W.get((u, v), W.get((v, u), 0.0)))
                edges.append((u, v, w))

    v2c: Dict[int, int] = {}
    for ci, C in enumerate(clusters):
        for u in C:
            v2c[u] = ci

    edges_by_cluster: List[List[Tuple[int, int, float]]] = [[] for _ in range(k)]
    for (u, v, w) in edges:
        cu = v2c.get(u, None)
        cv = v2c.get(v, None)
        if cu is not None and cv is not None and cu == cv:
            edges_by_cluster[cu].append((u, v, w))
        else:
            mx = (pos.get(u, (0.0, 0.0))[0] + pos.get(v, (0.0, 0.0))[0]) / 2.0
            my = (pos.get(u, (0.0, 0.0))[1] + pos.get(v, (0.0, 0.0))[1]) / 2.0
            mid = (mx, my)
            best_c = None
            best_d = float("inf")
            for ci, ccent in enumerate(centroids):
                d = dist2(mid, ccent)
                if d < best_d:
                    best_d = d
                    best_c = ci
            edges_by_cluster[best_c].append((u, v, w))

    # 4) para cada cluster, rodar solver por componente e consolidar
    root_out = Path(OUT) / f"k={k}"
    root_out.mkdir(parents=True, exist_ok=True)

    total_geral = 0.0

    for i in range(k):
        E = edges_by_cluster[i]
        if not E:
            print(f"[AVISO] cluster_{i+1} sem arestas (pulado).")
            continue

        root_cluster = root_out / f"cluster_{i+1}"
        root_cluster.mkdir(parents=True, exist_ok=True)

        comps = componentes_por_arestas(E)
        custos_comp: List[Tuple[int, float]] = []

        detalhes_dir = root_cluster / "detalhes"
        detalhes_dir.mkdir(parents=True, exist_ok=True)

        for j, compV in enumerate(comps, start=1):
            if len(compV) < 2:
                continue

            E_comp = [(u, v, w) for (u, v, w) in E if (u in compV and v in compV)]
            if not E_comp:
                continue

            Vc_comp = sorted(set([u for u, _, _ in E_comp] + [v for _, v, _ in E_comp]))
            id2i = {u: idx for idx, u in enumerate(Vc_comp)}
            n = len(Vc_comp)

            M = [[0.0] * n for _ in range(n)]
            for (u, v, w) in E_comp:
                iu, iv = id2i[u], id2i[v]
                M[iu][iv] = w
                M[iv][iu] = w

            work = detalhes_dir / f"comp_{j}"
            work.mkdir(parents=True, exist_ok=True)
            mat_path = work / "matriz_adjacencia.csv"

            with mat_path.open("w", newline="", encoding="utf-8") as f:
                wtr = csv.writer(f)
                wtr.writerow([""] + Vc_comp)
                for r, u in enumerate(Vc_comp):
                    wtr.writerow([u] + M[r])

            custo, global_out = rodar_solver(mat_path)
            custos_comp.append((j, custo))

            destino_comp = work / "relatorio_tour"
            if destino_comp.exists():
                shutil.rmtree(destino_comp)
            shutil.copytree(global_out, destino_comp)

            if global_out.exists():
                shutil.rmtree(global_out)

        total_cluster = sum(c for _, c in custos_comp)
        total_geral += total_cluster

        with (root_cluster / "tour_cost.txt").open("w", encoding="utf-8") as f:
            f.write(f"{total_cluster:.3f}\n")

        with (root_cluster / "summary_cluster.txt").open("w", encoding="utf-8") as f:
            f.write(f"cluster={i+1}\n")
            for idxc, c in custos_comp:
                f.write(f"comp_{idxc}: {c:.3f}\n")
            f.write(f"TOTAL_CLUSTER: {total_cluster:.3f}\n")

    with (root_out / "summary_k.txt").open("w", encoding="utf-8") as f:
        f.write(f"k={k}\nTOTAL_GERAL={total_geral:.3f}\n")

    print(f"TOTAL_GERAL (k={k}): {total_geral:.3f}")


if __name__ == "__main__":
    import sys
    kk = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    main(kk)
