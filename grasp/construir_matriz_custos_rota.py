"""Matriz de custos com distancias reais pela rede viaria."""

from infraestrutura.roteamento.cliente_open_route_service import (
  OpcoesOpenRouteService,
  obter_matriz_distancias,
)

from .distancia_haversine import GeoPoint
from .tipos import CostMatrix


def construir_matriz_custos_rota(
  pontos: list[GeoPoint],
  opcoes: OpcoesOpenRouteService | None = None,
) -> CostMatrix:
  """
  Constrói matriz de adjacencia com distancias reais pela rede viaria (ORS).

  Complexidade: Tempo O(1) local (1 requisicao HTTP); Espaco O(n²)
  """
  return obter_matriz_distancias(pontos, opcoes)
