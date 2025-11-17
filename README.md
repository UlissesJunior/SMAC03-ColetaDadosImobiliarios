# Coletas de dados imobiliários 

O Recadastramento Imobiliário Multifinalitário Georreferenciado tem como propósito atualizar o cadastro Técnico Multifinalitário (CTM) de um dado município. 
Um CTM visa apoiar a tomada de decisão de gestores públicos, facilitar o acesso às informações sobre propriedades imobiliárias para o cidadão, auxiliar no cálculo de taxas (ex. IPTU) entre outros benefícios. 
A Figura 1 mostra o processo em alto nível de um projeto de recadastramento. A partir de imagens aéreas obtidas por drone, é realizada a vetorização das parcelas, que consiste na delimitação dos lotes e respectivas edificações através de um software CAD (Computer Aided Design). 
Um Sistema de Informação Geográfico (SIG) armazena os dados de geolocalização dos imóveis, além do polígono correspondente definido na fase de vetorização. Baseado no conceito de eGov, os dados são disponibilizados para a população. 

Uma das etapas previstas no projeto de recadastramento envolve a coleta de dados em campo, cujo propósito é obter dados de elementos que não são possíveis de serem vistos pela ortofoto aérea. 
Através de um aplicativo e um Tablet um Agente de Coleta obtém as características de todo imóvel da região que ele ficou responsável (ex. tipo, fachada, acesso, piso interno etc.). 

Visando melhorar o planejamento da coleta e reduzir o esforço desta tarefa, o coordenador do projeto solicita um estudo em uma região da cidade de Elói Mendes/MG, para auxiliar na programação da coleta, definição docronograma e custos. 
O estudo deverá comparar o cronograma e custos quando se tem um ou dois agentes de coleta.

No caso de dois agentes o planejamento deverá considerar uma divisão similar da quantidade de imóveis a serem
coletados por cada um. A base dos Agentes Coletores corresponde a edificação com um círculo amarelo, que é o
local de onde eles partem para iniciar a coleta e retornam ao final do expediente para upload dos dados coletados.

<a href="https://geo.eloimendes.mg.gov.br/">
    <img src="assets/Cen%C3%A1rio%202%20-%20Edifica%C3%A7%C3%B5es.jpg" alt="Cidade Eloi Mendes">
</a>



## 2. Fluxo de Trabalho do Código-Fonte

Os scripts estão na pasta `codigo_fonte` e devem ser executados na ordem.

### 2.1. `setup_grafo/extrair_vertices_osm.py`

Este é o primeiro script do pipeline. Ele é responsável por ler o arquivo `.osm.pbf` bruto e extrair os **vértices (nós)** do grafo.

* **Entrada:** `dados_brutos/map.pbf`
* **Processo:**
    1.  Carrega o mapa com a biblioteca `pyrosm`.
    2.  Identifica os pontos de início e fim de todas as ruas da rede `driving`.
    3.  Agrupa (clusteriza) pontos que estão a menos de 3 metros de distância, tratando-os como um único cruzamento.
* **Saída:** `dados_processados/vertices_cruzamentos.csv` (Uma lista de IDs de vértices com suas coordenadas `lat/lon`).

### 2.2. `setup_grafo/calcular_pesos_arestas.py`

Este script "junta" a lista de vértices (com suas coordenadas) com a estrutura de conexões do grafo (lista de adjacência) para criar a lista final de **arestas ponderadas**.

Ambos os arquivos de entrada são o **resultado de um tratamento manual** para garantir a integridade da modelagem.

* **Entrada 1:** `dados_processados/vertices_reordenados.csv` (A lista de vértices "final" com suas coordenadas `lat/lon`, pós-tratamento).
* **Entrada 2:** `dados_processados/adjacency.txt` (Um arquivo de texto que define a estrutura do grafo, listando os vizinhos de cada nó, também tratado manualmente).
* **Processo:**
    1.  Carrega todos os vértices e suas coordenadas para a memória.
    2.  Lê a lista de adjacência.
    3.  Para cada aresta `(u, v)` encontrada, calcula a distância real (fórmula de Haversine) entre os dois pontos geográficos.
* **Saída:** `dados_processados/arestas_calc.csv` (Um CSV com as colunas: `origem`, `destino`, `distancia_m`).

### 2.3. `setup_grafo/gerar_matriz_adjacencia.py`

Este é o script final da fase de preparação de dados. Ele pega a lista de arestas ponderadas e a transforma em uma **matriz de adjacência** completa, que é o formato de entrada exato exigido pelo algoritmo principal do CPP.

* **Entrada 1:** `dados_processados/vertices_reordenados.csv` (Usado para garantir que a matriz tenha todos os vértices, mesmo os isolados, como linhas/colunas).
* **Entrada 2:** `dados_processados/arestas_calc.csv` (A lista `origem`, `destino`, `distancia_m`).
* **Processo:**
    1.  Cria um `DataFrame` quadrado de zeros, indexado pelos IDs dos vértices.
    2.  Itera sobre a lista de arestas e preenche a matriz de forma simétrica (o valor de `(u, v)` e `(v, u)` é a `distancia_m`).
* **Saída:** `dados_processados/matriz_adjacencia.csv` (O arquivo final que será lido pelo script `EdmondsJohnson(CPP).py`).

## 3. Algoritmo Principal (Solução do CPP)

Esta é a etapa central do projeto, localizada em `codigo_fonte/algoritmo_cpp/`.

### 3.1. `algoritmo_cpp/resolver_cpp.py`

Este script resolve o Problema do Carteiro Chinês (CPP) para o grafo de entrada. Ele é totalmente independente (Python puro) e implementa o algoritmo de Edmonds-Johnson.

* **Entrada:** `dados_processados/matriz_adjacencia.csv` (Fornecido como argumento na linha de comando).
* **Processo:**
    1.  **Leitura:** Carrega a matriz como um grafo (`dict` de `dict`).
    2.  **Análise:** Identifica todos os vértices de grau ímpar (`odd_nodes`) e verifica a conectividade.
    3.  **Caminhos Mínimos:** Executa o algoritmo de Dijkstra *apenas* a partir de cada nó ímpar (otimizado).
    4.  **Emparelhamento:** Constrói um grafo completo `K` com os nós ímpares e encontra o **emparelhamento perfeito de custo mínimo** (`min_weight_perfect_matching`) para "consertar" o grafo.
    5.  **Multigrafo:** Cria um multigrafo (baseado em `Counter`) que inclui as arestas originais mais as arestas duplicadas (do emparelhamento).
    6.  **Circuito Euleriano:** Usa o algoritmo de Hierholzer para extrair o circuito final do multigrafo.
    7.  **Cálculo de Custo:** Calcula o custo total otimizado (`Custo(G) + Custo(Matching)`).
* **Saídas:** Salva um relatório completo na pasta `4_resultados_finais/relatorio_tour/`, contendo:
    * `tour.csv`: A lista de vértices na ordem da rota.
    * `tour_cost.txt`: O custo total da rota.
    * `tour_detalhado.csv`: A lista de *arestas* percorridas, com custo acumulado.
    * `matching_paths.csv`: Os caminhos que foram duplicados para resolver os nós ímpares.

## 4. Fluxo de Trabalho de Visualização

Scripts na pasta `codigo_fonte/visualizacao/` usam os dados processados para gerar mapas e imagens.

### 4.1. `visualizacao/visualizar_grafo_estatico.py`

Este script gera uma visualização estática (imagem PNG) de todo o grafo para análise.

* **Entrada 1:** `dados_processados/vertices_reordenados.csv`
* **Entrada 2:** `dados_processados/arestas_calc.csv`
* **Processo:**
    1.  Carrega os vértices e arestas usando `geopandas`.
    2.  Plota todas as arestas, colorindo-as com base na sua distância (peso) normalizada.
    3.  Plota todos os nós (vértices) com seus IDs por cima das arestas.
* **Saída:** `resultados_finais/grafo_final.png` (Uma imagem de alta resolução do grafo).

### 4.2. `visualizacao/visualizar_mapa_interativo.py`

Este script gera um mapa interativo (arquivo HTML) que plota a rota final do Carteiro Chinês sobre um mapa geográfico.

* **Entrada 1:** `dados_processados/vertices_reordenados.csv` (Para obter as coordenadas `lat/lon` de cada vértice).
* **Entrada 2:** `resultados_finais/relatorio_tour/tour.csv` (A saída principal do script `resolver_cpp.py`, contendo a ordem dos vértices a visitar).
* **Processo:**
    1.  Usa `pandas` para carregar os vértices e a rota.
    2.  Cria um mapa `folium` centrado no primeiro ponto da rota.
    3.  Desenha a rota como uma `PolyLine` (linha azul) e marca cada vértice com um `CircleMarker` (círculo vermelho).
* **Saída:** `resultados_finais/mapa_cpp.html` (Um arquivo HTML que você pode abrir no navegador para explorar a rota).

### 4.3. `visualizacao/visualizar_animacao_rota.py`

Este script gera uma animação dinâmica (arquivo MP4) que "desenha" a rota do CPP sobre um mapa, sendo ideal para apresentações.

* **Entrada 1:** `dados_processados/vertices_reordenados.csv` (Para as coordenadas).
* **Entrada 2:** `resultados_finais/relatorio_tour/tour.csv` (A ordem da rota).
* **Processo:**
    1.  Carrega a rota e as coordenadas.
    2.  Cria um plot `matplotlib` com um mapa base (usando `contextily`).
    3.  Define uma função `make_frame(t)` que desenha a rota progressivamente até o tempo `t`.
    4.  Usa `moviepy.VideoClip` para chamar essa função para cada frame e renderizar o resultado em um vídeo.
* **Saída:** `resultados_finais/animacao_cpp.mp4` (Um vídeo da rota sendo percorrida).