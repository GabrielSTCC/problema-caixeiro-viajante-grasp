"""Construcao da matriz de adjacencia com distancias Haversine."""

from .distancia_haversine import GeoPoint, calcular_haversine
from .tipos import CostMatrix


def construir_matriz_custos_haversine(pontos: list[GeoPoint]) -> CostMatrix:
  """
  Constrói matriz de adjacencia com distancias geodesicas (linha reta).

  Complexidade: Tempo O(n²), Espaco O(n²)
  """
  n = len(pontos)

  if n == 0:
    return []

  # O(n)
  matrix: CostMatrix = [[0.0] * n for _ in range(n)]

  # O(n²)
  for i in range(n):
    # O(n)
    for j in range(i + 1, n):
      distancia = calcular_haversine(pontos[i], pontos[j])
      matrix[i][j] = distancia
      matrix[j][i] = distancia

  return matrix
