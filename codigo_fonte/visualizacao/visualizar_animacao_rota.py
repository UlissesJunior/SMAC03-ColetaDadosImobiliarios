# ----------------------------------------------------------------------
# VISUALIZAÇÃO: GERAR ANIMAÇÃO DA ROTA (MP4)
#
# Este script usa Matplotlib e MoviePy para gerar um vídeo (MP4)
# que mostra a rota do CPP sendo desenhada segmento por segmento
# sobre um mapa base (usando contextily).
#
# Ele cria uma função 'make_frame' que desenha o progresso da
# rota em um determinado tempo 't' e usa VideoClip para costurar
# todos os frames em um vídeo.
#
# Entrada: dados_processados/vertices_reordenados.csv (Coordenadas)
# Entrada: resultados_finais/relatorio_tour/tour.csv (A Rota)
# Saída:   resultados_finais/animacao_cpp.mp4
# ----------------------------------------------------------------------

import os
os.environ["MPLBACKEND"] = "Agg"   # força backend via env
import matplotlib
matplotlib.use("Agg")              # garante FigureCanvasAgg

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString
import contextily as ctx
import numpy as np
from moviepy import VideoClip

def mplfig_to_npimage(fig):
    fig.canvas.draw()
    w, h = fig.canvas.get_width_height()
    argb = np.frombuffer(fig.canvas.tostring_argb(), dtype=np.uint8)
    argb = argb.reshape((h, w, 4))
    rgba = argb[:, :, [1, 2, 3, 0]]
    rgb = rgba[:, :, :3]
    return rgb

# =============================
# 0. Definição de Caminhos
# =============================
PATH_VERTICES = r"dados_processados/vertices_reordenados.csv"
PATH_TOUR = r"resultados_finais/relatorio_tour/tour.csv"
PATH_SAIDA = r"resultados_finais/animacao_cpp.mp4"

# =============================
# 1. Configurações do Vídeo
# =============================
FPS = 30  # Frames por segundo
DUR = None # Duração (será calculada)

print("1. Carregando dados...")

# =============================
# 2. Leitura dos Dados
# =============================
vdf = pd.read_csv(PATH_VERTICES)
try:
    tdf = pd.read_csv(PATH_TOUR)
except FileNotFoundError:
    print(f"Erro: Arquivo {PATH_TOUR} não encontrado.")
    print("Por favor, execute o script 'resolver_cpp.py' primeiro.")
    exit()

coord = {
    int(r["id"]): (r["lon"], r["lat"])
    for _, r in vdf.iterrows()
}

tour = tdf["vertex"].tolist()

# =============================
# 3. Preparar Segmentos da Rota
# =============================
print("2. Processando segmentos da rota...")
segmentos = []
for i in range(len(tour) - 1):
    u = int(tour[i])
    v = int(tour[i + 1])
    if u in coord and v in coord and coord[u] != coord[v]:
        segmentos.append(LineString([coord[u], coord[v]]))

if not segmentos:
    raise RuntimeError("Nenhum segmento válido encontrado! Verifique os arquivos de entrada.")

gdf_seg = gpd.GeoDataFrame(geometry=segmentos, crs="EPSG:4326")
gdf_seg_web = gdf_seg.to_crs(epsg=3857)

xmin, ymin, xmax, ymax = gdf_seg_web.total_bounds
N = len(gdf_seg_web)
DUR = N / FPS

print(f"   → Total de frames: {N}")
print(f"   → Duração do vídeo: {DUR:.2f}s")

# =============================
# 4. Configurar Figura (Matplotlib)
# =============================
print("3. Configurando a figura base...")
fig, ax = plt.subplots(figsize=(10, 12))

ctx.add_basemap(ax, crs="EPSG:3857", source=ctx.providers.CartoDB.DarkMatter, zoom=15)
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
ax.axis("off") # Remove eixos


(line,) = ax.plot([], [], color="#FF0000", linewidth=3, alpha=0.8) # Vermelho

(point,) = ax.plot([], [], "o", color="#FFFF00", markersize=8) # Amarelo

plt.tight_layout()

# =============================
# 5. Função de Animação (Frame)
# =============================
def make_frame(t):
    i = int(t * FPS)
    if i >= N:
        i = N - 1

    current_segments = gdf_seg_web.iloc[:i+1]

    xs = []
    ys = []
    for geom in current_segments.geometry:
        x, y = geom.xy
        xs.extend(list(x))
        ys.extend(list(y))

    line.set_data(xs, ys)

    geom_last = gdf_seg_web.iloc[i].geometry
    x2, y2 = geom_last.xy
    point.set_data([x2[-1]], [y2[-1]])

    return mplfig_to_npimage(fig)

# =============================
# 6. Criação do Vídeo (MoviePy)
# =============================
print(f"4. Gerando vídeo ({FPS} FPS)... (Isso pode demorar!)")
os.makedirs(os.path.dirname(PATH_SAIDA), exist_ok=True)

clip = VideoClip(make_frame, duration=DUR)
clip.write_videofile(PATH_SAIDA, fps=FPS, codec="libx264")
plt.close(fig)

print(f"✅ Vídeo salvo com sucesso: {PATH_SAIDA}")