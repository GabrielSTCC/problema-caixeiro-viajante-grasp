"""Interface web Streamlit para GRASP/TSP — Russas-CE."""

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_folium import st_folium

from dados.enderecos_russas import EnderecoRussas
from grasp.construir_geometria_rota import obter_coordenadas_rota
from servicos.executar_otimizacao import (
  ResultadoOtimizacao,
  executar_otimizacao,
  formatar_ordem_visita,
  validar_enderecos,
)
from ui.componentes.editor_enderecos import renderizar_editor_enderecos
from ui.componentes.mapa_rota import criar_mapa_rota

load_dotenv(Path(__file__).resolve().parent / ".env")

CSS = """
<style>
  .block-container { padding-top: 1.5rem; max-width: 1200px; }
  .hero-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 0.25rem;
  }
  .hero-subtitle {
    color: #64748b;
    font-size: 1rem;
    margin-bottom: 1.5rem;
  }
  .metric-card {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
  }
  div[data-testid="stSidebar"] {
    background-color: #f8fafc;
  }
</style>
"""


def _inicializar_estado() -> None:
  if "resultado" not in st.session_state:
    st.session_state.resultado = None
  if "enderecos_execucao" not in st.session_state:
    st.session_state.enderecos_execucao = None


def _renderizar_css() -> None:
  st.markdown(CSS, unsafe_allow_html=True)


def _renderizar_cabecalho() -> None:
  st.markdown('<p class="hero-title">GRASP — Problema do Caixeiro Viajante</p>', unsafe_allow_html=True)
  st.markdown(
    '<p class="hero-subtitle">Otimizacao de rotas de entrega em Russas-CE com meta-heuristica GRASP + 2-opt</p>',
    unsafe_allow_html=True,
  )


def _renderizar_sidebar() -> tuple[float, int, bool, bool]:
  st.sidebar.header("Parametros GRASP")

  alpha = st.sidebar.slider(
    "Alpha (α)",
    min_value=0.0,
    max_value=1.0,
    value=float(os.getenv("GRASP_ALPHA", "0.3")),
    step=0.05,
    help=(
      "Controla a Lista de Candidatos Restrita (RCL). "
      "0 = guloso puro; 1 = maxima aleatoriedade."
    ),
  )

  max_iteracoes = st.sidebar.slider(
    "Iteracoes GRASP",
    min_value=10,
    max_value=500,
    value=int(os.getenv("GRASP_MAX_ITERATIONS", "100")),
    step=10,
    help="Numero de iteracoes construcao + 2-opt.",
  )

  api_key = os.getenv("ORS_API_KEY", "").strip()
  if api_key:
    st.sidebar.success("ORS API key configurada")
  else:
    st.sidebar.warning("ORS API key ausente — use Haversine ou configure .env")

  usar_ors = st.sidebar.toggle(
    "Usar distancias reais (ORS)",
    value=bool(api_key),
    disabled=not api_key,
    help="Distancias pela rede viaria via OpenRouteService.",
  )

  calcular = st.sidebar.button(
    "Calcular rota",
    type="primary",
    width="stretch",
  )

  return alpha, max_iteracoes, usar_ors, calcular


def _executar_calculo(
  enderecos: list[EnderecoRussas],
  alpha: float,
  max_iteracoes: int,
  usar_ors: bool,
) -> None:
  erros = validar_enderecos(enderecos)
  if erros:
    for erro in erros:
      st.error(erro)
    return

  progresso = st.progress(0, text="Calculando matriz de distancias...")
  status = st.empty()

  def on_iteracao(atual: int, total: int) -> None:
    progresso.progress(atual / total, text=f"GRASP: iteracao {atual}/{total}")

  try:
    status.info("Obtendo matriz de custos...")
    resultado = executar_otimizacao(
      enderecos,
      alpha=alpha,
      max_iteracoes=max_iteracoes,
      usar_ors=usar_ors,
      on_iteracao=on_iteracao,
    )
    progresso.progress(1.0, text="Concluido!")
    st.session_state.resultado = resultado
    st.session_state.enderecos_execucao = list(enderecos)

    if resultado.aviso_matriz:
      st.warning(resultado.aviso_matriz)
    else:
      tipo = "ORS (rotas reais)" if resultado.tipo_matriz == "ors" else "Haversine (aproximado)"
      st.success(f"Rota calculada com matriz {tipo}.")

  except ValueError as erro:
    st.error(str(erro))
  finally:
    progresso.empty()
    status.empty()


def _matriz_para_dataframe(
  matriz: list[list[float]],
  enderecos: list[EnderecoRussas],
) -> pd.DataFrame:
  nomes = [e["nome"] for e in enderecos]
  return pd.DataFrame(matriz, index=nomes, columns=nomes).round(3)


def _renderizar_aba_matriz(
  resultado: ResultadoOtimizacao,
  enderecos: list[EnderecoRussas],
) -> None:
  st.subheader("Matriz de distancias (km)")

  tipo = "OpenRouteService" if resultado.tipo_matriz == "ors" else "Haversine"
  st.caption(f"Fonte: {tipo}")

  df = _matriz_para_dataframe(resultado.matriz_custos, enderecos)
  st.dataframe(df, width="stretch")


def _renderizar_aba_resultado(
  resultado: ResultadoOtimizacao,
  enderecos: list[EnderecoRussas],
) -> None:
  st.subheader("Resultado GRASP")

  col1, col2, col3 = st.columns(3)
  with col1:
    st.metric("Custo total", f"{resultado.custo_km:.3f} km")
  with col2:
    st.metric("Iteracoes", resultado.iteracoes)
  with col3:
    st.metric("Paradas", len(resultado.tour))

  st.markdown("**Ordem de visita**")
  for ordem, indice in enumerate(resultado.tour):
    item = enderecos[indice]
    icone = "🏠" if indice == 0 else "📦"
    st.markdown(f"{ordem + 1}. {icone} **{item['nome']}** — {item['endereco']}")

  if resultado.tour:
    st.markdown(
      f"{len(resultado.tour) + 1}. 🏠 **{enderecos[0]['nome']}** — retorno ao deposito"
    )

  st.markdown("**Resumo da rota**")
  st.code(formatar_ordem_visita(resultado.tour, enderecos))

  with st.expander(f"Historico de melhorias ({len(resultado.melhorias)})"):
    for melhoria in resultado.melhorias:
      st.markdown(
        f"- Iteracao **{melhoria.iteracao}**: "
        f"**{melhoria.custo_km:.3f} km** — tour `{melhoria.tour}`"
      )


def _renderizar_aba_mapa(
  resultado: ResultadoOtimizacao,
  enderecos: list[EnderecoRussas],
) -> None:
  st.subheader("Mapa da rota")

  usar_vias = resultado.tipo_matriz == "ors" and bool(os.getenv("ORS_API_KEY", "").strip())

  with st.spinner("Carregando rota pelas ruas..."):
    coordenadas, segue_vias = obter_coordenadas_rota(
      enderecos,
      resultado.tour,
      usar_vias=usar_vias,
    )

  if segue_vias:
    st.caption("Rota desenhada pelas ruas via OpenRouteService Directions.")
  elif usar_vias:
    st.warning(
      "Nao foi possivel obter a geometria pelas ruas. "
      "Exibindo linhas retas entre os pontos."
    )
  else:
    st.caption(
      "Modo Haversine: linhas retas entre os pontos "
      "(configure ORS para rotas pelas ruas)."
    )

  mapa = criar_mapa_rota(
    enderecos,
    resultado.tour,
    coordenadas_rota=coordenadas,
    segue_vias=segue_vias,
  )
  st_folium(mapa, width=None, height=500, returned_objects=[])


def main() -> None:
  st.set_page_config(
    page_title="GRASP TSP Russas",
    page_icon="🗺️",
    layout="wide",
  )

  _inicializar_estado()
  _renderizar_css()
  _renderizar_cabecalho()

  alpha, max_iteracoes, usar_ors, calcular = _renderizar_sidebar()

  aba_enderecos, aba_matriz, aba_resultado, aba_mapa = st.tabs([
    "Enderecos",
    "Matriz de distancias",
    "Resultado GRASP",
    "Mapa",
  ])

  with aba_enderecos:
    enderecos = renderizar_editor_enderecos()

  if calcular:
    _executar_calculo(enderecos, alpha, max_iteracoes, usar_ors)

  resultado: ResultadoOtimizacao | None = st.session_state.resultado
  enderecos_resultado: list[EnderecoRussas] | None = st.session_state.enderecos_execucao

  with aba_matriz:
    if resultado and enderecos_resultado:
      _renderizar_aba_matriz(resultado, enderecos_resultado)
    else:
      st.info("Calcule uma rota na barra lateral para ver a matriz de distancias.")

  with aba_resultado:
    if resultado and enderecos_resultado:
      _renderizar_aba_resultado(resultado, enderecos_resultado)
    else:
      st.info("Calcule uma rota na barra lateral para ver o resultado do GRASP.")

  with aba_mapa:
    if resultado and enderecos_resultado:
      _renderizar_aba_mapa(resultado, enderecos_resultado)
    else:
      st.info("Calcule uma rota na barra lateral para visualizar o mapa.")


if __name__ == "__main__":
  main()
