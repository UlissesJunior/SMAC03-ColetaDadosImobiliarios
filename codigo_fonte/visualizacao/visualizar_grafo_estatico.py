# ----------------------------------------------------------------------
# VISUALIZAÇÃO: GERAR IMAGEM ESTÁTICA DO GRAFO
#
# Este script lê os vértices (com coordenadas) e as arestas
# (com distâncias) e plota o grafo completo em uma imagem PNG.
#
# Ele usa a biblioteca Geopandas para lidar com as coordenadas e
# o Matplotlib para desenhar. As arestas são coloridas com base
# em sua distância (peso), de verde (curto) a vermelho (longo).
#
# Entrada: 3_dados_processados/vertices_reordenados.csv
# Entrada: 3_dados_processados/arestas_calc.csv
# Saída:   4_resultados_finais/grafo_final.png
# ----------------------------------------------------------------------

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString
import os  

# =============================
# 0. Definição de Caminhos
# =============================
PATH_VERTICES = r"dados_processados/vertices_reordenados.csv"
PATH_ARESTAS = r"dados_processados/arestas_calc.csv"
PATH_SAIDA = r"resultados_finais/grafo_final.png"

# =============================
# 1. Carregar dados
# =============================
vertices = pd.read_csv(PATH_VERTICES)  
arestas = pd.read_csv(PATH_ARESTAS)  

gdf_vertices = gpd.GeoDataFrame(
    vertices,
    geometry=gpd.points_from_xy(vertices.lon, vertices.lat),
    crs="EPSG:4326"
)

# reprojetar para metros
gdf_vertices = gdf_vertices.to_crs(epsg=32723)

# criar lookup rápido: id → geometry
geom_dict = dict(zip(gdf_vertices["id"], gdf_vertices.geometry))

# =============================
# 2. Construir geometria das linhas
# =============================
def make_line(row):
    u = row["origem"]
    v = row["destino"]

    if u not in geom_dict or v not in geom_dict:
        print(f"[WARNING] Vértice {u} ou {v} não encontrado!")
        return None

    return LineString([geom_dict[u], geom_dict[v]])

arestas["geometry"] = arestas.apply(make_line, axis=1)

# remover arestas inválidas (caso algum vértice não exista)
arestas = arestas[arestas["geometry"].notnull()].copy()

gdf_arestas = gpd.GeoDataFrame(
    arestas,
    geometry="geometry",
    crs=gdf_vertices.crs
)

# =============================
# 3. Normalizar por distância
# =============================
dist = gdf_arestas["distancia_m"]
norm = (dist - dist.min()) / (dist.max() - dist.min() + 1e-9)

cmap = plt.get_cmap("RdYlGn_r")

# =============================
# 4. Plot
# =============================
fig, ax = plt.subplots(figsize=(14, 12))

for i, row in gdf_arestas.iterrows():
    color = cmap(norm.loc[i])
    x, y = row.geometry.xy
    ax.plot(x, y, color=color, linewidth=2, alpha=0.9)

# =============================
# 5. Desenhar nós
# =============================
node_radius = 6

for _, row in gdf_vertices.iterrows():
    ax.add_patch(plt.Circle(
        (row.geometry.x, row.geometry.y),
        node_radius,
        facecolor="#ff5555",
        edgecolor="black",
        lw=0.6,
        zorder=3
    ))
    ax.text(
        row.geometry.x, row.geometry.y,
        str(int(row["id"])),
        fontsize=5,
        ha="center", va="center",
        color="white",
        fontweight="bold",
        zorder=4
    )

ax.set_title("🗺️ Grafo Eloi Mendes — Pesos por Distância (m)", fontsize=16, pad=20)
ax.axis("equal")
ax.axis("off")
plt.tight_layout()

# =============================
# 6. Salvar
# =============================
# Garante que o diretório de saída exista
os.makedirs(os.path.dirname(PATH_SAIDA), exist_ok=True)

plt.savefig(PATH_SAIDA, dpi=300, bbox_inches="tight", pad_inches=0.05)
plt.close()

print(f"✅ Grafo exportado com sucesso: {PATH_SAIDA}")