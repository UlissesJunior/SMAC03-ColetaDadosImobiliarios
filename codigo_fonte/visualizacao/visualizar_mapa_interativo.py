# ----------------------------------------------------------------------
# VISUALIZAÇÃO: GERAR MAPA INTERATIVO (FOLIUM)
#
# Este script lê a solução final do CPP (a ordem dos vértices)
# e os dados geográficos (coordenadas dos vértices) para plotar
# a rota final sobre um mapa interativo usando a biblioteca Folium.
#
# O resultado é um arquivo HTML que pode ser aberto no navegador.
#
# Entrada: dados_processados/vertices_reordenados.csv (Coordenadas)
# Entrada: resultados_finais/relatorio_tour/tour.csv (A Rota)
# Saída:   resultados_finais/mapa_cpp.html
# ----------------------------------------------------------------------

<<<<<<< HEAD

import pandas as pd
import folium
=======
from datetime import datetime
import pandas as pd
import folium
from folium.plugins import BeautifyIcon
>>>>>>> b63bbed (feat(visualizacao): mapa interativo de rotas por agente)
import os  

# =============================
# 0. Definição de Caminhos
# =============================
<<<<<<< HEAD
PATH_VERTICES = r"dados_processados/vertices_reordenados.csv"
PATH_TOUR = r"resultados_finais/relatorio_tour/tour.csv"
PATH_SAIDA = r"resultados_finais/mapa_cpp.html"
=======
# Base do projeto: duas pastas acima (codigo_fonte/visualizacao -> projeto root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PATH_VERTICES = os.path.join(BASE_DIR, "dados_processados", "vertices_reordenados.csv")
PATH_TOUR = os.path.join(BASE_DIR, "resultados_finais", "relatorio_tour", "tour.csv")
# Timestamp seguro para usar em nomes de ficheiro (sem barras ou caracteres inválidos)
timestamp = datetime.now().strftime("%d-%m-%Y_%H%M%S")
PATH_SAIDA = os.path.join(BASE_DIR, "resultados_finais", f"mapa_cpp_{timestamp}.html")
>>>>>>> b63bbed (feat(visualizacao): mapa interativo de rotas por agente)

# =======================
# LER ARQUIVOS
# =======================
print("1. Lendo vértices e rota...")
vdf = pd.read_csv(PATH_VERTICES)
try:
    tdf = pd.read_csv(PATH_TOUR)
except FileNotFoundError:
    print(f"Erro: Arquivo {PATH_TOUR} não encontrado.")
    print("Por favor, execute o script 'resolver_cpp.py' primeiro.")
    exit()

print("2. Processando coordenadas...")
coord = {
    int(r["id"]): (r["lat"], r["lon"])
    for _, r in vdf.iterrows()
}

tour = tdf["vertex"].tolist()
if not tour:
    print("Erro: O arquivo 'tour.csv' está vazio.")
    exit()

# =======================
# CRIAR MAPA FOLIUM
# =======================
print("3. Criando mapa interativo...")
lat0, lon0 = coord[tour[0]]

<<<<<<< HEAD
m = folium.Map(location=[lat0, lon0], zoom_start=16, tiles="CartoDB dark_matter")

for v in tour:
    if v in coord:
        lat, lon = coord[v]
        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            popup=f"Vértice {v}",
            color="#FF0000", # Vermelho vivo
            fill=True,
            fill_color="#FF0000"
        ).add_to(m)
    else:
        print(f"Aviso: Vértice {v} do tour não encontrado na lista de vértices.")
=======
m = folium.Map(location=[lat0, lon0], zoom_start=16, tiles=None)

>>>>>>> b63bbed (feat(visualizacao): mapa interativo de rotas por agente)


polyline_coords = []
for v in tour:
    if v in coord:
        polyline_coords.append(coord[v])

folium.PolyLine(
    locations=polyline_coords,
    weight=4,
    color="#00A3FF",
    tooltip="Caminho CPP"
).add_to(m)

<<<<<<< HEAD

folium.TileLayer('openstreetmap').add_to(m)
=======
for v in tour:
    if v in coord:
        lat, lon = coord[v]
        # marcador pequeno (ponto) para destacar a posição
        # folium.CircleMarker(
        #     location=[lat, lon],
        #     radius=3,
        #     popup=f"Vértice {v}",
        #     color="#FF0000",
        #     fill=True,
        #     fill_color="#FF0000"
        # ).add_to(m)

        # ícone do tipo marcador com o número do vértice (mais legível)
        icon = BeautifyIcon(
            icon_shape="marker",
            border_color="#ffffff",
            border_width=1,
            text_color="#ffffff",
            background_color="#FF0000",
            number=str(v),
            inner_icon_style="font-size:12px;"
        )
        folium.Marker(location=[lat, lon], icon=icon, draggable=False).add_to(m)
    else:
        print(f"Aviso: Vértice {v} do tour não encontrado na lista de vértices.")

# Adiciona camada de imagens de satélite (Esri World Imagery)
esri_imagery_url = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
folium.TileLayer(
    tiles=esri_imagery_url,
    attr=(
        "Tiles &copy; Esri — Fonte: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping,"
        " Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
    ),
    name="Esri WorldImagery",
    overlay=False,
    control=True,
).add_to(m)

# Mantém o controle de camadas para ligar/desligar camadas base/overlays
>>>>>>> b63bbed (feat(visualizacao): mapa interativo de rotas por agente)
folium.LayerControl().add_to(m)

# =======================
# SALVAR MAPA
# =======================
print(f"4. Salvando mapa em {PATH_SAIDA}...")
os.makedirs(os.path.dirname(PATH_SAIDA), exist_ok=True)
m.save(PATH_SAIDA)

print(f"✅ Mapa interativo salvo com sucesso!")