# ----------------------------------------------------------------------
# PASSO 1: EXTRAIR VÉRTICES (CRUZAMENTOS) DO MAPA
#
# Este script lê o arquivo .osm.pbf bruto, extrai a rede de ruas
# (driving) e identifica todos os cruzamentos (vértices do grafo).
#
# O principal desafio resolvido é o "agrupamento" (clustering):
# múltiplas pontas de rua que chegam em um mesmo cruzamento
# são agrupadas (com 3m de tolerância) e tratadas como um
# único vértice, cujo centroide é salvo.
#
# Entrada: dados_brutos/map.pbf
# Saída:   dados_processados/vertices_cruzamentos.csv

# ATENÇÃO!!! Essa é uma ferramenta de pré-processamento para gerar um candidato a lista de vértices!!!
# Depois, foi realizado um tratamento (manual) para filtrar/limpar esses vértices  
# de forma que a modelagem fique mais próxima da ortofoto do trabalho
# Sugestões e adaptações do script para filtrar os vértices e gerar um arquivo mais limpo são bem vindas!!!
# O ideal seria que essa etapa já fornecesse a lista de adjacencias e os vertices prontos! 
# ----------------------------------------------------------------------


import os
from pyrosm import OSM
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import linemerge
import pandas as pd

PBF_PATH = r"dados_brutos\map.pbf"
OUT_DIR = r"dados_processados"
NETWORK_TYPE = "driving"
NODE_CLUSTER_TOL_M = 3.0

def make_single_linestring(geom):
    if geom is None:
        return None
    if geom.geom_type == "LineString":
        return geom
    if geom.geom_type == "MultiLineString":
        merged = linemerge(geom)
        if merged.geom_type == "LineString":
            return merged
        return max(list(merged.geoms), key=lambda g: g.length)
    return None

def extract_endpoints(geom):
    coords = list(geom.coords)
    return coords[0], coords[-1]

def cluster_points(points_gdf, tol_m):
    if points_gdf.empty:
        return points_gdf

    buffers = points_gdf.geometry.buffer(tol_m)
    unioned = buffers.unary_union

    polys = list(unioned.geoms) if hasattr(unioned, "geoms") else [unioned]

    clusters = []
    cid = 1
    for poly in polys:
        clusters.append({
            "cluster_id": cid,
            "geometry": poly.centroid
        })
        cid += 1

    return gpd.GeoDataFrame(clusters, geometry="geometry", crs=points_gdf.crs)

def main():
    print("1) Carregando PBF…")
    osm = OSM(PBF_PATH)

    print("2) Extraindo rede…")
    edges = osm.get_network(network_type=NETWORK_TYPE)
    if edges.empty:
        raise RuntimeError("Rede vazia.")

    print("3) Garantindo CRS correto (EPSG:4326)...")
    if edges.crs is None:
        edges = edges.set_crs("EPSG:4326")
    else:
        edges = edges.to_crs("EPSG:4326")

    print("   Calculando centróide para UTM...")
    try:
        union_geom = edges.geometry.union_all()
    except:
        union_geom = edges.unary_union

    centroid = union_geom.centroid

    try:
        utm_crs = gpd.GeoSeries([centroid], crs="EPSG:4326").estimate_utm_crs()
    except:
        print("⚠️ estimate_utm_crs falhou, usando EPSG:3857 fallback")
        utm_crs = "EPSG:3857"

    print("4) Reprojetando para CRS métrico:", utm_crs)
    edges_m = edges.to_crs(utm_crs)

    print("5) Transformando todas geometrias em LineString…")
    edges_m["geom"] = edges_m.geometry.apply(make_single_linestring)
    edges_m = edges_m[~edges_m["geom"].isna()].copy()
    edges_m["geometry"] = edges_m["geom"]
    edges_m = edges_m.drop(columns=["geom"])

    print("6) Coletando endpoints…")
    endpoints = []
    for _, row in edges_m.iterrows():
        a, b = extract_endpoints(row.geometry)
        endpoints.extend([Point(a), Point(b)])

    endpoints_gdf = gpd.GeoDataFrame(geometry=endpoints, crs=edges_m.crs)

    print("7) Clusterizando nós…")
    clusters = cluster_points(endpoints_gdf, NODE_CLUSTER_TOL_M)
    clusters = clusters.reset_index(drop=True)

    print(f"   → nós finais detectados: {len(clusters)}")

    print("8) Exportando vértices (lat/lon)…")
    clusters_wgs = clusters.to_crs(4326)
    clusters_wgs["lon"] = clusters_wgs.geometry.x
    clusters_wgs["lat"] = clusters_wgs.geometry.y
    clusters_wgs["id"] = clusters_wgs["cluster_id"]

    out_csv = os.path.join(OUT_DIR, "vertices_cruzamentos.csv")
    clusters_wgs[["id", "lat", "lon"]].to_csv(out_csv, index=False)

    print("\n✅ Finalizado.")
    print("Arquivo salvo em:", out_csv)

if __name__ == "__main__":
    main()
