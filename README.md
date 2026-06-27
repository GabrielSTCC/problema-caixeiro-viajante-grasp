# Problema do Caixeiro Viajante usando GRASP (PAA)

Trabalho acadêmico de **Projeto e Análise de Algoritmos (PAA)** que resolve o **Problema do Caixeiro Viajante (PCV/TSP)** com a meta-heurística **GRASP** e busca local **2-opt**, usando um caso de estudo de rotas de entrega em **Russas-CE**.

O sistema calcula a ordem de visita que minimiza a distância total percorrida, usando distâncias reais de estrada (via [OpenRouteService](https://openrouteservice.org/)) e a meta-heurística **GRASP** com busca local **2-opt**.

---

## Problema

Dado um depósito e vários pontos de entrega, encontrar a rota mais curta que:

1. Parte do depósio (índice 0)
2. Visita cada entrega exatamente uma vez
3. Retorna ao depósio ao final

Esse é um caso clássico de **TSP (Traveling Salesman Problem)**, NP-difícil. Por isso usamos **GRASP** — uma meta-heurística que combina construção gulosa aleatorizada com melhoria local.

---

## Como funciona o algoritmo

### 1. Matriz de custos (distâncias reais)

As coordenadas dos endereços são enviadas à **OpenRouteService Matrix API**, que retorna distâncias de condução em metros. O projeto converte para quilômetros e monta uma matriz `n × n`.

> Existe também um fallback com distância **Haversine** (linha reta) em `grasp/construir_matriz_custos_haversine.py`, útil para testes sem API.

### 2. Fase construtiva GRASP

A cada iteração, a rota é construída passo a passo a partir do depósito:

- Para cada nó atual, calcula-se o custo até todos os não visitados
- Monta-se a **Lista de Candidatos Restrita (RCL)** com nós cujo custo ≤ `C_min + α × (C_max - C_min)`
- Escolhe-se **aleatoriamente** um candidato da RCL
- Repete até visitar todos os nós

O parâmetro **α** (alpha) controla o equilíbrio entre gula e diversificação:

| α | Comportamento |
|---|---------------|
| 0 | Sempre escolhe o mais barato (guloso puro) |
| 1 | Considera todos os candidatos (máxima aleatoriedade) |
| 0.3 | Padrão — boa diversificação com viés para custos menores |

### 3. Busca local 2-opt

Após cada construção, aplica-se **2-opt**: troca pares de arestas da rota enquanto houver melhoria. Isso elimina cruzamentos e reduz o custo localmente.

### 4. Iterações

O processo (construção + 2-opt) repete por `GRASP_MAX_ITERATIONS` vezes. A melhor rota encontrada é retornada.

**Complexidade:** O(k × n²), onde `k` = número de iterações e `n` = número de pontos.

---

## Interface web (Streamlit)

Além do CLI, o projeto oferece uma interface visual em [`app.py`](app.py) para configurar, executar e analisar a otimização.

### Fluxo na interface

1. **Endereços** — visualize e edite depósito + entregas (nome, endereço, latitude, longitude). É possível restaurar o caso padrão de Russas-CE ou adicionar novos pontos.
2. **Calcular rota** (barra lateral) — informe **α**, **iterações GRASP** e se deseja distâncias reais (ORS) ou Haversine.
3. O serviço [`servicos/executar_otimizacao.py`](servicos/executar_otimizacao.py) monta a matriz de custos, executa o GRASP e guarda o resultado na sessão.
4. As abas **Matriz**, **Resultado** e **Mapa** exibem os dados calculados.

### Mapa da rota

A aba **Mapa** usa [Folium](https://python-visualization.github.io/folium/) para mostrar:

- Marcador verde no **depósito** (início e fim da rota)
- Marcadores numerados nas **entregas**, na ordem do tour encontrado pelo GRASP
- Traçado da rota sobre o mapa

**Distância vs. visualização:** o algoritmo usa a **Matrix API** da OpenRouteService (distâncias reais entre pares de pontos). O desenho no mapa usa a **Directions API** (geometria pelas ruas), quando a chave ORS está configurada e o toggle de distâncias reais está ativo.

| Modo | Matriz de custos | Linha no mapa |
|------|------------------|---------------|
| ORS (padrão com API key) | Distâncias de condução (km) | Rota sólida seguindo as ruas |
| Haversine (sem key ou fallback) | Distância em linha reta (km) | Linha tracejada entre os pontos |

Se a Directions API falhar, a interface exibe linhas retas como fallback, sem interromper a execução.

---

## Estrutura do projeto

```
.
├── app.py                                # Interface web Streamlit
├── principal.py                          # Ponto de entrada CLI — executa o fluxo completo
├── servicos/
│   └── executar_otimizacao.py            # Orquestracao matriz + GRASP
├── ui/
│   └── componentes/                      # Editor de enderecos e mapa Folium
├── dados/
│   └── enderecos_russas.py               # Endereços e coordenadas em Russas-CE
├── grasp/
│   ├── resolver_grasp.py                 # Loop GRASP (construção + 2-opt + melhor global)
│   ├── fase_construtiva_grasp.py         # Fase construtiva com RCL
│   ├── busca_local_2opt.py               # Melhoria local 2-opt
│   ├── custo_tour.py                     # Cálculo do custo total de uma rota
│   ├── construir_matriz_custos_rota.py   # Matriz via OpenRouteService
│   ├── construir_matriz_custos_haversine.py
│   ├── construir_geometria_rota.py       # Geometria da rota para o mapa
│   └── distancia_haversine.py            # Distância geodésica (fallback)
├── infraestrutura/
│   └── roteamento/
│       ├── cliente_open_route_service.py # Cliente ORS Matrix API
│       └── cliente_ors_directions.py     # Cliente ORS Directions API (mapa)
├── requirements.txt
├── .env.example                          # Modelo de variáveis de ambiente
└── .gitignore                            # .env está ignorado — nunca commite chaves!
```

---

## Pré-requisitos

- **Python 3.10+**
- Conta gratuita na [OpenRouteService](https://openrouteservice.org/dev/#/signup) para obter uma API key

---

## Instalação e execução

### 1. Clone o repositório

```bash
git clone https://github.com/GabrielSTCC/problema-caixeiro-viajante-grasp.git
cd problema-caixeiro-viajante-grasp
```

### 2. Instale as dependências

```bash
py -m pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente

Copie o arquivo de exemplo e preencha **sua** chave da API:

```bash
copy .env.example .env
```

Edite `.env`:

```env
ORS_API_KEY=sua_chave_aqui
GRASP_ALPHA=0.3
GRASP_MAX_ITERATIONS=100
```

> **Importante:** O arquivo `.env` **não** é versionado. Nunca commite sua chave de API.

### 4. Execute

**Linha de comando:**

```bash
py principal.py
```

A saída inclui a matriz de distâncias, o progresso do GRASP e a melhor rota encontrada com a ordem de visita.

**Interface web (Streamlit):**

```bash
py -m streamlit run app.py
```

A interface abre no navegador com quatro abas:

- **Endereços** — edite a lista de pontos (depósito + entregas) ou restaure o padrão Russas-CE
- **Matriz de distâncias** — tabela interativa com distâncias em km entre todos os pares
- **Resultado GRASP** — custo total, ordem de visita e histórico de melhorias por iteração
- **Mapa** — rota visual com marcadores numerados; segue as ruas quando ORS está ativo

Na barra lateral, ajuste **α**, **iterações GRASP** e escolha entre distâncias reais (ORS) ou Haversine (fallback). Um indicador mostra se a API key está configurada.

---

## Variáveis de ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `ORS_API_KEY` | Chave da OpenRouteService | *(obrigatória para ORS; Haversine funciona sem)* |
| `GRASP_ALPHA` | Parâmetro α da RCL (0 a 1) | `0.3` |
| `GRASP_MAX_ITERATIONS` | Número de iterações GRASP | `100` |

---

## Endereços de exemplo

Os pontos de entrega estão em `dados/enderecos_russas.py`:

- **Depósito:** R. Maciel Pereira, 1054 — Vila Matoso
- **7 entregas** espalhadas pelo centro e bairros de Russas-CE

Para usar outros endereços, edite a lista `ENDERECOS_RUSSAS` com nome, endereço e coordenadas (latitude/longitude).

---

## Disciplina

**Projeto e Análise de Algoritmos (PAA)** — trabalho sobre meta-heurísticas aplicadas a problemas de otimização combinatória.

---

## Licença

Projeto acadêmico — uso livre para fins educacionais.
