import os
import pandas as pd

# projeto root: duas pastas acima (codigo_fonte/setup_grafo -> projeto root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CSV_PATH = os.path.join(BASE_DIR, "dados_processados", "arestas_calc_test.csv")

if not os.path.exists(CSV_PATH):
	print(f"Erro: arquivo não encontrado: {CSV_PATH}")
	print("Verifique se o arquivo existe em 'dados_processados' na raiz do projeto")
	raise FileNotFoundError(CSV_PATH)

df = pd.read_csv(CSV_PATH)

# usar casas pequenas (~8 metros por casa)
df['n_casas'] = (df['distancia_m'] / 8).round().astype(int)

# salvar no MESMO arquivo
df.to_csv(CSV_PATH, index=False)
