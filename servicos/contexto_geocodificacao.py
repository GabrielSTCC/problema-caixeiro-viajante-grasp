"""Contexto de cidade/estado para geocodificacao na interface."""

from dataclasses import dataclass

import streamlit as st

from dados.localidades_brasil import (
  CIDADE_PADRAO,
  CIDADES_POR_ESTADO,
  ESTADO_PADRAO,
  ESTADOS_BR,
  NOMES_ESTADOS,
  OPCAO_OUTRA_CIDADE,
)


@dataclass(frozen=True)
class ContextoGeocodificacao:
  cidade: str
  estado: str


def _indice_estado(estado: str) -> int:
  try:
    return ESTADOS_BR.index(estado)
  except ValueError:
    return ESTADOS_BR.index(ESTADO_PADRAO)


def _indice_cidade(estado: str, cidade: str) -> int:
  opcoes = CIDADES_POR_ESTADO.get(estado, []) + [OPCAO_OUTRA_CIDADE]
  if cidade in opcoes:
    return opcoes.index(cidade)
  return len(opcoes) - 1


def renderizar_seletor_localidade() -> ContextoGeocodificacao:
  """Renderiza seletores de estado e cidade para geocodificacao."""
  if "geocod_estado" not in st.session_state:
    st.session_state.geocod_estado = ESTADO_PADRAO
  if "geocod_cidade" not in st.session_state:
    st.session_state.geocod_cidade = CIDADE_PADRAO
  if "geocod_cidade_custom" not in st.session_state:
    st.session_state.geocod_cidade_custom = CIDADE_PADRAO

  col_estado, col_cidade = st.columns(2)

  with col_estado:
    estado = st.selectbox(
      "Estado (UF)",
      ESTADOS_BR,
      index=_indice_estado(st.session_state.geocod_estado),
      format_func=lambda uf: f"{uf} — {NOMES_ESTADOS[uf]}",
      key="select_estado_geocod",
    )

  cidades_estado = CIDADES_POR_ESTADO.get(estado, [])
  opcoes_cidade = cidades_estado + [OPCAO_OUTRA_CIDADE]

  cidade_atual = st.session_state.geocod_cidade
  if estado != st.session_state.geocod_estado:
    cidade_atual = cidades_estado[0] if cidades_estado else CIDADE_PADRAO

  with col_cidade:
    cidade_opcao = st.selectbox(
      "Cidade",
      opcoes_cidade,
      index=_indice_cidade(estado, cidade_atual),
      key="select_cidade_geocod",
    )

  cidade = cidade_opcao
  if cidade_opcao == OPCAO_OUTRA_CIDADE:
    cidade = st.text_input(
      "Digite o nome da cidade",
      value=st.session_state.geocod_cidade_custom,
      key="input_cidade_custom_geocod",
    ).strip() or CIDADE_PADRAO

  contexto = ContextoGeocodificacao(cidade=cidade, estado=estado)
  contexto_anterior = ContextoGeocodificacao(
    cidade=st.session_state.geocod_cidade,
    estado=st.session_state.geocod_estado,
  )

  if contexto != contexto_anterior:
    st.session_state.resultado = None
    st.session_state.enderecos_execucao = None
    st.session_state.resultado_fingerprint = None
    st.session_state.geocod_regeocodificar_pendente = True
    st.warning(
      f"Localidade alterada para **{cidade} — {estado}**. "
      "Regeocodificando todos os enderecos..."
    )

  st.session_state.geocod_estado = estado
  st.session_state.geocod_cidade = cidade
  if cidade_opcao == OPCAO_OUTRA_CIDADE:
    st.session_state.geocod_cidade_custom = cidade

  st.caption(
    f"Geocodificacao usara: **{cidade}, {estado}, Brasil**"
  )

  return contexto


def obter_contexto_geocodificacao() -> ContextoGeocodificacao:
  """Retorna contexto salvo na sessao (ou padrao)."""
  return ContextoGeocodificacao(
    cidade=st.session_state.get("geocod_cidade", CIDADE_PADRAO),
    estado=st.session_state.get("geocod_estado", ESTADO_PADRAO),
  )
