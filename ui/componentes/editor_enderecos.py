"""Editor de enderecos com SQLite, geocodificacao automatica e exclusao."""

import pandas as pd
import streamlit as st

from dados.enderecos_russas import EnderecoRussas
from dados.repositorio_enderecos import (
  EnderecoPersistido,
  inserir,
  listar_ativos,
  listar_para_grasp,
  para_endereco_grasp,
  restaurar_padrao,
  sincronizar_lista,
)
from servicos.contexto_geocodificacao import ContextoGeocodificacao, renderizar_seletor_localidade
from servicos.executar_otimizacao import validar_enderecos
from servicos.estado_enderecos import fingerprint_enderecos
from servicos.geocodificar_enderecos import (
  COORDENADAS_PADRAO,
  ENDERECOS_GENERICOS,
  _formatar_badge,
  detectar_coordenadas_duplicadas,
  geocodificar_lista,
  geocodificar_pendentes,
  precisa_geocodificar,
)

COLUNAS = ["id", "nome", "endereco", "latitude", "longitude"]


def _enderecos_para_dataframe(enderecos: list[EnderecoPersistido]) -> pd.DataFrame:
  return pd.DataFrame(enderecos, columns=COLUNAS)


def _dataframe_para_enderecos(df: pd.DataFrame) -> list[EnderecoPersistido | EnderecoRussas]:
  registros: list[EnderecoPersistido | EnderecoRussas] = []
  for _, linha in df.iterrows():
    item: EnderecoPersistido | EnderecoRussas = {
      "nome": str(linha["nome"]).strip(),
      "endereco": str(linha["endereco"]).strip(),
      "latitude": float(linha["latitude"]),
      "longitude": float(linha["longitude"]),
    }
    if pd.notna(linha.get("id")):
      item["id"] = int(linha["id"])
    registros.append(item)
  return registros


def _inicializar_session_state() -> None:
  if "enderecos_cache" not in st.session_state:
    st.session_state.enderecos_cache = listar_ativos()
  if "enderecos_texto_anterior" not in st.session_state:
    st.session_state.enderecos_texto_anterior = {
      item["id"]: item["endereco"] for item in st.session_state.enderecos_cache
    }
  if "resultado_fingerprint" not in st.session_state:
    st.session_state.resultado_fingerprint = None
  if "enderecos_fingerprint" not in st.session_state:
    st.session_state.enderecos_fingerprint = None


def invalidar_resultado_se_enderecos_mudaram(enderecos: list[EnderecoRussas]) -> None:
  fingerprint = fingerprint_enderecos(enderecos)
  if fingerprint != st.session_state.get("resultado_fingerprint"):
    st.session_state.resultado = None
    st.session_state.enderecos_execucao = None
  st.session_state.enderecos_fingerprint = fingerprint


def _geocodificar_e_persistir(
  persistidos: list[EnderecoPersistido],
  *,
  enderecos_alterados: list[str] | None = None,
  forcar_todos: bool = False,
  contexto: ContextoGeocodificacao | None = None,
) -> list[EnderecoPersistido]:
  if forcar_todos:
    grasp_list = [para_endereco_grasp(item) for item in persistidos]
    atualizados, relatorio = geocodificar_lista(grasp_list, contexto=contexto)
  else:
    grasp_list = [para_endereco_grasp(item) for item in persistidos]
    atualizados, relatorio = geocodificar_pendentes(
      grasp_list,
      enderecos_alterados=enderecos_alterados,
      contexto=contexto,
    )

  if not relatorio:
    return persistidos

  mesclados: list[EnderecoPersistido | EnderecoRussas] = []
  for indice, item in enumerate(persistidos):
    atualizado = dict(item)
    atualizado.update(atualizados[indice])
    atualizado["id"] = item["id"]
    mesclados.append(atualizado)

  sucesso = sum(1 for r in relatorio if r.sucesso)
  if sucesso:
    st.toast(f"{sucesso} endereco(s) geocodificado(s).")
  for item in relatorio:
    if item.sucesso:
      badge = _formatar_badge(item.fonte or "", item.precisao or "")
      detalhe = badge
      if item.endereco_resolvido:
        detalhe += f" — {item.endereco_resolvido}"
      st.caption(f"{item.nome}: {item.latitude:.6f}, {item.longitude:.6f} ({detalhe})")
      if item.precisao == "aproximado" and item.fonte in {"ORS", "Nominatim"}:
        st.warning(
          f"{item.nome}: numero do endereco nao confirmado pelo OpenStreetMap. "
          "Configure GOOGLE_MAPS_API_KEY no .env para maior precisao ou edite lat/lng manualmente."
        )
    else:
      st.warning(f"{item.nome}: {item.mensagem}")

  return sincronizar_lista(mesclados)


def renderizar_editor_enderecos() -> list[EnderecoRussas]:
  """Renderiza o editor e retorna enderecos ativos para o GRASP."""
  _inicializar_session_state()

  st.subheader("Pontos de entrega")
  st.caption(
    "A linha 0 e sempre o deposito. Ao editar o endereco, as coordenadas "
    "sao buscadas automaticamente. Enderecos excluidos somem da lista."
  )

  contexto = renderizar_seletor_localidade()

  if st.session_state.get("geocod_regeocodificar_pendente"):
    st.session_state.geocod_regeocodificar_pendente = False
    with st.spinner("Atualizando coordenadas para a nova localidade..."):
      persistidos_local = _geocodificar_e_persistir(
        st.session_state.enderecos_cache,
        forcar_todos=True,
        contexto=contexto,
      )
      st.session_state.enderecos_cache = persistidos_local
      st.session_state.enderecos_texto_anterior = {
        item["id"]: item["endereco"] for item in persistidos_local
      }
      invalidar_resultado_se_enderecos_mudaram(listar_para_grasp())
    st.rerun()

  col_reset, col_add, col_geo = st.columns([1, 1, 1])
  with col_reset:
    if st.button("Restaurar padrao Russas", width="stretch"):
      st.session_state.enderecos_cache = restaurar_padrao()
      st.session_state.enderecos_texto_anterior = {
        item["id"]: item["endereco"] for item in st.session_state.enderecos_cache
      }
      st.session_state.resultado = None
      st.session_state.enderecos_execucao = None
      st.session_state.resultado_fingerprint = None
      st.rerun()

  with col_add:
    if st.button("Adicionar entrega", width="stretch"):
      inserir(
        nome=f"Entrega {len(listar_ativos())}",
        endereco="Novo endereco",
        latitude=COORDENADAS_PADRAO[0],
        longitude=COORDENADAS_PADRAO[1],
      )
      st.session_state.enderecos_cache = listar_ativos()
      invalidar_resultado_se_enderecos_mudaram(listar_para_grasp())
      st.rerun()

  df = _enderecos_para_dataframe(st.session_state.enderecos_cache)
  df_editado = st.data_editor(
    df,
    num_rows="dynamic",
    width="stretch",
    hide_index=False,
    column_config={
      "id": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
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

  enderecos_editados = _dataframe_para_enderecos(df_editado)
  texto_anterior: dict[int, str] = st.session_state.enderecos_texto_anterior
  enderecos_alterados: list[str] = []

  for item in enderecos_editados:
    endereco_id = item.get("id")
    endereco_texto = item["endereco"].strip()
    if endereco_id and texto_anterior.get(endereco_id) != endereco_texto:
      enderecos_alterados.append(endereco_texto)

  persistidos = sincronizar_lista(enderecos_editados)

  deve_geocodificar = bool(enderecos_alterados)

  if deve_geocodificar:
    persistidos = _geocodificar_e_persistir(
      persistidos,
      enderecos_alterados=enderecos_alterados,
      contexto=contexto,
    )

  st.session_state.enderecos_cache = persistidos
  st.session_state.enderecos_texto_anterior = {
    item["id"]: item["endereco"] for item in persistidos
  }

  enderecos_grasp = listar_para_grasp()
  invalidar_resultado_se_enderecos_mudaram(enderecos_grasp)

  with col_geo:
    if st.button("Regeocodificar todos", width="stretch"):
      with st.spinner("Buscando coordenadas..."):
        persistidos = _geocodificar_e_persistir(
          persistidos,
          forcar_todos=True,
          contexto=contexto,
        )
        st.session_state.enderecos_cache = persistidos
        invalidar_resultado_se_enderecos_mudaram(listar_para_grasp())
      st.rerun()

  pendentes = sum(1 for item in enderecos_grasp if precisa_geocodificar(item))
  if pendentes:
    st.info(
      f"{pendentes} ponto(s) ainda sem coordenadas reais. "
      "Preencha o endereco completo para geocodificar automaticamente."
    )

  if (
    st.session_state.get("resultado_fingerprint")
    and st.session_state.get("enderecos_fingerprint")
    != st.session_state.get("resultado_fingerprint")
  ):
    st.warning("Enderecos alterados. Recalcule a rota na barra lateral.")

  if enderecos_grasp and enderecos_grasp[0]["nome"].lower() != "deposito":
    st.info("Dica: mantenha a linha 0 como deposito/base de operacoes.")

  erros = validar_enderecos(enderecos_grasp)
  if erros:
    for erro in erros:
      st.error(erro)
  else:
    st.success(
      f"{len(enderecos_grasp)} pontos validos — deposito + {len(enderecos_grasp) - 1} entrega(s)."
    )

  duplicatas = detectar_coordenadas_duplicadas(enderecos_grasp)
  for coords, nomes in duplicatas:
    lat, lng = coords
    st.warning(
      f"Coordenadas duplicadas ({lat:.5f}, {lng:.5f}) em: {', '.join(nomes)}. "
      "Edite manualmente ou use **Restaurar padrao Russas**."
    )

  return enderecos_grasp
