import os, csv, sys, glob, math
import folium

BASE = "dados_processados"
OUT  = "resultados_finais/rotas_k_clusters"

def ler_vertices(path):
    pos = {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            u  = int(row["id"])
            lat= float(row["lat"])
            lon= float(row["lon"])
            pos[u] = (lat, lon)  # folium usa (lat, lon)
    return pos

def ler_tour_detalhado(path):
    segs = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        # tenta colunas usuais: u/v, origem/destino, from/to
        cand_u=("u","origem","from")
        cand_v=("v","destino","to")
        hdr = [h.lower() for h in r.fieldnames]
        def col(cands):
            for c in cands:
                if c in hdr: return c
            return None
        cu, cv = col(cand_u), col(cand_v)
        if not (cu and cv):
            return segs
        for row in r:
            u = int(row[cu]); v = int(row[cv])
            segs.append((u,v))
    return segs

def media_coord(ids, pos):
    xs, ys = [], []
    for u in ids:
        if u in pos:
            xs.append(pos[u][0]); ys.append(pos[u][1])
    if not xs: return (-20.0, -44.0)
    return (sum(xs)/len(xs), sum(ys)/len(ys))

def palette():
    # 12 cores distintas; se k>12, repete
    return [
        "#1f77b4","#ff7f0e","#2ca02c","#d62728",
        "#9467bd","#8c564b","#e377c2","#7f7f7f",
        "#bcbd22","#17becf","#4c78a8","#f58518"
    ]

def main():
    k = int(sys.argv[1]) if len(sys.argv)>1 else 2
    pos = ler_vertices(os.path.join(BASE, "vertices_reordenados.csv"))

    root_k = os.path.join(OUT, f"k={k}")
    clusters = sorted(glob.glob(os.path.join(root_k, "cluster_*")))
    if not clusters:
        print(f"Nada encontrado em {root_k}")
        sys.exit(0)

    # centraliza o mapa nos vértices usados
    usados = set()
    for cdir in clusters:
        for det in glob.glob(os.path.join(cdir, "detalhes", "comp_*", "relatorio_tour", "tour_detalhado.csv")):
            for u,v in ler_tour_detalhado(det):
                usados.add(u); usados.add(v)
    center = media_coord(usados, pos)
    m = folium.Map(location=center, zoom_start=16, control_scale=True)

    cols = palette()
    legend_items = []

    for idx, cdir in enumerate(clusters, start=1):
        color = cols[(idx-1)%len(cols)]
        # custo do agente (cluster)
        custo = ""
        cost_file = os.path.join(cdir, "tour_cost.txt")
        if os.path.exists(cost_file):
            with open(cost_file, encoding="utf-8", errors="ignore") as f:
                custo = f.read().strip()

        # junta todos os segmentos das componentes desse cluster
        segs_tot = []
        dets = sorted(glob.glob(os.path.join(cdir, "detalhes", "comp_*", "relatorio_tour", "tour_detalhado.csv")))
        for det in dets:
            segs_tot.extend(ler_tour_detalhado(det))

        # desenha
        for (u,v) in segs_tot:
            if u in pos and v in pos:
                folium.PolyLine([pos[u], pos[v]], color=color, weight=4, opacity=0.9).add_to(m)

        # marca início “representativo” do agente (primeiro nó que aparecer)
        start_u = segs_tot[0][0] if segs_tot else None
        if start_u and start_u in pos:
            folium.CircleMarker(
                location=pos[start_u], radius=5, color=color, fill=True, fill_opacity=1.0,
                popup=f"Agente {idx} | custo={custo}"
            ).add_to(m)

        legend_items.append((f"Agente {idx}", color, custo))

    # legenda simples
    html_legend = """
    <div style="position: fixed; bottom: 20px; right: 20px; z-index:9999; background: white; padding:10px; border:1px solid #ccc; border-radius:8px; font-size:13px;">
      <b>Agentes</b><br/>
      {}
    </div>
    """
    rows = []
    for name, color, custo in legend_items:
        extra = f" — {custo}" if custo else ""
        rows.append(f'<div><span style="display:inline-block;width:12px;height:12px;background:{color};margin-right:6px;"></span>{name}{extra}</div>')
    from folium import Element
    m.get_root().html.add_child(Element(html_legend.format("\n".join(rows))))

    out_html = os.path.join("resultados_finais", f"mapa_k={k}.html")
    os.makedirs(os.path.dirname(out_html), exist_ok=True)
    m.save(out_html)
    print(f"[OK] Mapa salvo em {out_html}")

if __name__ == "__main__":
    main()
