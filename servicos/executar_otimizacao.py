"""Orquestracao do fluxo completo: matriz de custos + GRASP."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from dados.enderecos_russas import EnderecoRussas, obter_pontos_geograficos
from grasp import (
  construir_matriz_custos_haversine,
  construir_matriz_custos_rota,
  resolver_grasp,
)
from grasp.tipos import CostMatrix, Tour

TipoMatriz = Literal["ors", "haversine"]


@dataclass
class MelhoriaGrasp:
  """Registro de uma melhoria encontrada durante o GRASP."""

  iteracao: int
  custo_km: float
  tour: Tour


@dataclass
class ResultadoOtimizacao:
  """Resultado completo da otimizacao."""

  tour: Tour
  custo_km: float
  iteracoes: int
  matriz_custos: CostMatrix
  tipo_matriz: TipoMatriz
  melhorias: list[MelhoriaGrasp] = field(default_factory=list)
  aviso_matriz: str | None = None


def validar_enderecos(enderecos: list[EnderecoRussas]) -> list[str]:
  """Retorna lista de erros de validacao (vazia se tudo ok)."""
  erros: list[str] = []

  if len(enderecos) < 2:
    erros.append("Informe ao menos 2 pontos (deposito + 1 entrega).")

  for indice, item in enumerate(enderecos):
    if not item.get("nome", "").strip():
      erros.append(f"Linha {indice + 1}: nome obrigatorio.")
    if not item.get("endereco", "").strip():
      erros.append(f"Linha {indice + 1}: endereco obrigatorio.")

    lat = item.get("latitude")
    lng = item.get("longitude")
    if lat is None or lng is None:
      erros.append(f"Linha {indice + 1}: latitude e longitude obrigatorias.")
      continue

    if not (-90 <= lat <= 90):
      erros.append(f"Linha {indice + 1}: latitude deve estar entre -90 e 90.")
    if not (-180 <= lng <= 180):
      erros.append(f"Linha {indice + 1}: longitude deve estar entre -180 e 180.")

  return erros


def formatar_ordem_visita(
  tour: list[int],
  enderecos: list[EnderecoRussas],
) -> str:
  if not enderecos:
    return ""

  if len(tour) <= 1:
    return enderecos[0]["endereco"]

  paradas = " -> ".join(enderecos[indice]["endereco"] for indice in tour[1:])
  return f"{enderecos[0]['endereco']} -> {paradas} -> {enderecos[0]['endereco']}"


def _construir_matriz(
  enderecos: list[EnderecoRussas],
  *,
  usar_ors: bool,
) -> tuple[CostMatrix, TipoMatriz, str | None]:
  pontos = obter_pontos_geograficos(enderecos)
  aviso: str | None = None

  if usar_ors:
    try:
      return construir_matriz_custos_rota(pontos), "ors", None
    except ValueError as erro:
      aviso = f"Falha na ORS ({erro}). Usando distancias Haversine (aproximadas)."
      return construir_matriz_custos_haversine(pontos), "haversine", aviso

  return construir_matriz_custos_haversine(pontos), "haversine", None


def executar_otimizacao(
  enderecos: list[EnderecoRussas],
  *,
  alpha: float,
  max_iteracoes: int,
  usar_ors: bool = True,
  retornar_ao_deposito: bool = True,
  on_iteracao: Callable[[int, int], None] | None = None,
) -> ResultadoOtimizacao:
  """
  Executa o fluxo completo: validacao, matriz de custos e GRASP.

  Raises:
    ValueError: se os enderecos forem invalidos ou alpha estiver fora de [0, 1].
  """
  erros = validar_enderecos(enderecos)
  if erros:
    raise ValueError("\n".join(erros))

  if alpha < 0 or alpha > 1:
    raise ValueError(f"alpha deve estar no intervalo [0, 1], recebido: {alpha}")

  matriz, tipo_matriz, aviso = _construir_matriz(enderecos, usar_ors=usar_ors)
  melhorias: list[MelhoriaGrasp] = []

  def _on_melhoria(iteracao: int, custo: float, tour: Tour) -> None:
    melhorias.append(MelhoriaGrasp(iteracao=iteracao, custo_km=custo, tour=list(tour)))

  resultado = resolver_grasp(
    matriz,
    alpha=alpha,
    max_iteracoes=max_iteracoes,
    retornar_ao_deposito=retornar_ao_deposito,
    on_melhoria=_on_melhoria,
    on_iteracao=on_iteracao,
  )

  return ResultadoOtimizacao(
    tour=resultado.tour,
    custo_km=resultado.custo_km,
    iteracoes=resultado.iteracoes,
    matriz_custos=matriz,
    tipo_matriz=tipo_matriz,
    melhorias=melhorias,
    aviso_matriz=aviso,
  )
