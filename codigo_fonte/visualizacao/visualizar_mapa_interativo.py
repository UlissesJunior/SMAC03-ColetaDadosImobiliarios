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


import pandas as pd
import folium
import os  

# =============================
# 0. Definição de Caminhos
# =============================
PATH_VERTICES = r"dados_processados/vertices_reordenados.csv"
PATH_TOUR = r"resultados_finais/relatorio_tour/tour.csv"
PATH_SAIDA = r"resultados_finais/mapa_cpp.html"

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


folium.TileLayer('openstreetmap').add_to(m)
folium.LayerControl().add_to(m)

# =======================
# SALVAR MAPA
# =======================
print(f"4. Salvando mapa em {PATH_SAIDA}...")
os.makedirs(os.path.dirname(PATH_SAIDA), exist_ok=True)
m.save(PATH_SAIDA)

print(f"✅ Mapa interativo salvo com sucesso!")