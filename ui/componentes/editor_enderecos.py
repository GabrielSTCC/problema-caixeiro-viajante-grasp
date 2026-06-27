"""Editor de enderecos com validacao para a interface Streamlit."""

import copy

import pandas as pd
import streamlit as st

from dados.enderecos_russas import ENDERECOS_RUSSAS, EnderecoRussas
from servicos.executar_otimizacao import validar_enderecos

COLUNAS = ["nome", "endereco", "latitude", "longitude"]


def _enderecos_para_dataframe(enderecos: list[EnderecoRussas]) -> pd.DataFrame:
  return pd.DataFrame(enderecos, columns=COLUNAS)


def _dataframe_para_enderecos(df: pd.DataFrame) -> list[EnderecoRussas]:
  registros: list[EnderecoRussas] = []
  for _, linha in df.iterrows():
    registros.append({
      "nome": str(linha["nome"]).strip(),
      "endereco": str(linha["endereco"]).strip(),
      "latitude": float(linha["latitude"]),
      "longitude": float(linha["longitude"]),
    })
  return registros


def _inicializar_session_state() -> None:
  if "enderecos" not in st.session_state:
    st.session_state.enderecos = copy.deepcopy(ENDERECOS_RUSSAS)


def renderizar_editor_enderecos() -> list[EnderecoRussas]:
  """Renderiza o editor e retorna a lista atual de enderecos."""
  _inicializar_session_state()

  st.subheader("Pontos de entrega")
  st.caption(
    "A linha 0 e sempre o deposito (ponto de partida e retorno). "
    "Edite nome, endereco e coordenadas conforme necessario."
  )

  col_reset, col_add = st.columns([1, 1])
  with col_reset:
    if st.button("Restaurar padrao Russas", width="stretch"):
      st.session_state.enderecos = copy.deepcopy(ENDERECOS_RUSSAS)
      st.rerun()

  with col_add:
    if st.button("Adicionar entrega", width="stretch"):
      st.session_state.enderecos.append({
        "nome": f"Entrega {len(st.session_state.enderecos)}",
        "endereco": "Novo endereco",
        "latitude": -4.94,
        "longitude": -37.97,
      })
      st.rerun()

  df = _enderecos_para_dataframe(st.session_state.enderecos)
  df_editado = st.data_editor(
    df,
    num_rows="dynamic",
    width="stretch",
    hide_index=False,
    column_config={
      "nome": st.column_config.TextColumn("Nome", required=True),
      "endereco": st.column_config.TextColumn("Endereco", required=True),
      "latitude": st.column_config.NumberColumn(
        "Latitude",
        format="%.6f",
        min_value=-90.0,
        max_value=90.0,
        required=True,
      ),
      "longitude": st.column_config.NumberColumn(
        "Longitude",
        format="%.6f",
        min_value=-180.0,
        max_value=180.0,
        required=True,
      ),
    },
    key="editor_enderecos",
  )

  enderecos = _dataframe_para_enderecos(df_editado)

  if enderecos and enderecos[0]["nome"].lower() != "deposito":
    st.info("Dica: mantenha a linha 0 como deposito/base de operacoes.")

  erros = validar_enderecos(enderecos)
  if erros:
    for erro in erros:
      st.error(erro)
  else:
    st.success(f"{len(enderecos)} pontos validos — deposito + {len(enderecos) - 1} entrega(s).")

  st.session_state.enderecos = enderecos
  return enderecos
