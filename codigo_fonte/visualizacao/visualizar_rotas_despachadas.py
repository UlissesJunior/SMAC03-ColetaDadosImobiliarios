"""Gerar mapa interativo com as rotas despachadas por agente.

Esta função recebe a saída de `generate_agent_trail` (do módulo de despacho)
ou chama a função para gerar as trilhas, e plota no folium:
- uma PolyLine por agente (cor da `palette()` em `visualizar_mapa_k.py`)
- popup/tooltip com distância total e número de casas visitadas por agente
- marcadores para cada nó visitado (ícone numerado)

Baseado em `visualizar_mapa_interativo.py` e `visualizar_mapa_k.py`.
"""

from datetime import datetime
import os
import sys
import pandas as pd
import folium
from folium.plugins import BeautifyIcon

# garantir importações locais funcionarem quando executado como script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from codigo_fonte.despacho_rotas.depacho_rotas_k_agentes import generate_agent_trail
from codigo_fonte.visualizacao.visualizar_mapa_k import palette
from codigo_fonte.setup_grafo.build_adj_matrix_from_csv import build_adj_matrix


# paths relativos ao projeto
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PATH_VERTICES = os.path.join(BASE_DIR, 'dados_processados', 'vertices_reordenados.csv')


def visualize_agent_trails(results=None, n_agents=4, out_path=None, save=True, zoom_start=16, map_type='carto'):
    """Gera um `folium.Map` com as rotas dos agentes.

    - `results`: dicionário retornado por `generate_agent_trail`. Se None, chama `generate_agent_trail(n_agents)`.
    - `out_path`: caminho do arquivo HTML de saída. Se None, usa `resultados_finais/mapa_rotas_despachadas_{timestamp}.html`.
    - `save`: se True, grava o HTML em disco e retorna o path junto com o map.
    Retorna `(m, out_path)` quando `save` True, senão `(m, None)`.
    """
    # carregar dados se necessário
    if results is None:
        results = generate_agent_trail(n_agents)

    # ler vértices (lat, lon)
    if not os.path.exists(PATH_VERTICES):
        raise FileNotFoundError(f"Arquivo de vértices não encontrado: {PATH_VERTICES}")
    vdf = pd.read_csv(PATH_VERTICES)
    coord = {int(r['id']): (r['lat'], r['lon']) for _, r in vdf.iterrows()}

    # centralizar mapa na média dos nós visitados
    usados = set()
    for aid, info in results.items():
        for trail in info.get('trails', []):
            usados.update(trail.get('nodes', []))
    # filtrar apenas ids existentes
    usados_exist = [u for u in usados if u in coord]
    if usados_exist:
        lat0 = sum(coord[u][0] for u in usados_exist) / len(usados_exist)
        lon0 = sum(coord[u][1] for u in usados_exist) / len(usados_exist)
    else:
        # fallback: centro padrão
        lat0, lon0 = (-20.0, -44.0)
    
    

    m = folium.Map(location=[lat0, lon0], zoom_start=zoom_start, tiles=None, control_scale=True)

    # escolher camada base conforme `map_type`
    mt = (map_type or 'carto').strip().lower()
    if mt in ('satellite', 'sat', 's'):
        # Esri WorldImagery
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
    elif mt in ('carto', 'cartodb', 'pos', 'c'):
        # CartoDB Positron (clean map)
        folium.TileLayer('CartoDB positron', name='CartoDB Positron', control=True).add_to(m)
    else:
        # fallback para OpenStreetMap
        folium.TileLayer('OpenStreetMap', name='OpenStreetMap', control=True).add_to(m)

    cols = palette()

    legend_items = []

    # desenhar cada agente
    for aid, info in sorted(results.items()):
        idx = int(aid)
        color = cols[idx % len(cols)]

        # agregar métricas do agente
        total_dist = 0.0
        total_n_casas = 0
        all_nodes = []
        seen_edge_ids = set()
        # obter edges_mapping para consultar n_casas por eid (passando coords conhecidos)
        try:
            _, edges_mapping, _, _ = build_adj_matrix(coords_path=PATH_VERTICES)
        except Exception:
            edges_mapping = {}

        # cada 'trail' já contém nodes (sequência) e edge_ids
        for trail in info.get('trails', []):
            # distância deve ser acumulada por passagem
            total_dist += float(trail.get('distance_m', 0.0))
            # registrar nós
            all_nodes.extend(trail.get('nodes', []))
            # para n_casas: somar apenas por aresta única por agente
            for eid in trail.get('edge_ids', []):
                if eid in seen_edge_ids:
                    continue
                seen_edge_ids.add(eid)
                # procurar n_casas no edges_mapping (se disponível), senão tentar no objeto trail
                n_c = 0
                if edges_mapping and eid in edges_mapping:
                    try:
                        n_c = int(edges_mapping[eid].get('n_casas', 0))
                    except Exception:
                        n_c = 0
                else:
                    # fallback: usar n_casas agregado da trilha dividido proporcionalmente (não ideal)
                    # mas tentamos pegar 'n_casas' da trilha apenas se não houver mapa
                    pass
                total_n_casas += n_c

        # desenhar uma polyline por agente: concatenar as trilhas (separando componentes)
        # para simplicidade, vamos desenhar cada trail separadamente
        for trail in info.get('trails', []):
            nodes_seq = list(trail.get('nodes', []))
            # desenhar a trilha exatamente como gerada
            poly_coords = [coord[u] for u in nodes_seq if u in coord]
            if len(poly_coords) >= 2:
                # tooltip curto (resumo) e popup com rota completa (truncada se muito longa)
                tooltip_short = f"Agente {idx} — dist={trail.get('distance_m',0):.1f} m — casas={trail.get('n_casas',0)}"
                route_str = ','.join(str(x) for x in nodes_seq)
                popup_html = route_str
                popup = folium.Popup(popup_html, max_width=600,)
                folium.PolyLine(locations=poly_coords, weight=5, color=color, tooltip=tooltip_short, popup=popup, opacity=0.9).add_to(m)

        # marcadores para nós visitados (primeira aparição)
        seen = set()
        for seq_idx, u in enumerate(all_nodes):
            if u in seen:
                continue
            seen.add(u)
            if u not in coord:
                continue
            lat, lon = coord[u]
            icon = BeautifyIcon(
                icon_shape='marker',
                border_color='#ffffff',
                border_width=1,
                text_color='#ffffff',
                background_color=color,
                number=str(u),
                inner_icon_style='font-size:10px;'
            )
            popup = f"Agente {idx} — Vértice {u}"
            folium.Marker(location=[lat, lon], icon=icon, popup=popup, draggable=False).add_to(m)

        legend_items.append((f"Agente {idx}", color, f"dist={total_dist:.1f}m casas={total_n_casas}"))

    # legenda simples (estilo similar ao visualizar_mapa_k)
    html_legend = """
    <div style="position: fixed; bottom: 20px; right: 20px; z-index:9999; background: white; padding:10px; border:1px solid #ccc; border-radius:8px; font-size:13px;">
      <b>Agentes</b><br/>
      {}
    </div>
    """
    rows = []
    for name, color, extra in legend_items:
        rows.append(f'<div><span style="display:inline-block;width:12px;height:12px;background:{color};margin-right:6px;"></span>{name} — {extra}</div>')
    from folium import Element
    m.get_root().html.add_child(Element(html_legend.format('\n'.join(rows))))

    folium.LayerControl().add_to(m)

    

    # salvar
    if out_path is None:
        timestamp = datetime.now().strftime("%d-%m-%Y_%H%M%S")
        out_path = os.path.join(BASE_DIR, 'resultados_finais', f'mapa_rotas_despachadas_{n_agents}agentes_{timestamp}.html')
    if save:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        m.save(out_path)
        return m, out_path
    return m, None


def main():
    # modo interativo simples: perguntar ao usuário número de agentes
    try:
        s = input('Número de agentes (enter para 4): ').strip()
        n = int(s) if s else 4
    except Exception:
        n = 4

    # pedir tipo de mapa com opção numérica: 1 = satellite, 2 = carto
    try:
        sel = input('Escolha tipo de mapa: 1 - satellite, 2 - carto (enter para carto): ').strip()
        if sel == '1':
            mt = 'satellite'
        elif sel == '2':
            mt = 'carto'
        elif sel == '':
            mt = 'carto'
        else:
            # aceitar entradas textuais também
            mt = sel.lower()
    except Exception:
        mt = 'carto'

    # caminho de saída em resultados_finais/rotas_agentes
    out_dir = os.path.join(BASE_DIR, 'resultados_finais', 'rotas_agentes')
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%d-%m-%Y_%H%M%S')
    out_path = os.path.join(out_dir, f'Rota_{n}agentes_{mt}_{timestamp}.html')

    m, out = visualize_agent_trails(None, n_agents=n, out_path=out_path, save=True, map_type=mt)
    print(f"Mapa salvo em: {out}")


if __name__ == '__main__':
    main()
