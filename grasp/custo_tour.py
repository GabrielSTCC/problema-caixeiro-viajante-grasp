"""Calculo do custo total de um tour."""

from .tipos import CostMatrix, Tour


def calcular_custo_tour(
  tour: Tour,
  matriz_custos: CostMatrix,
  *,
  retornar_ao_deposito: bool = True,
) -> float:
  """
  Calcula o custo total de um tour na matriz de adjacencia.

  Complexidade: Tempo O(n), Espaco O(1)
  """
  if len(tour) <= 1:
    return 0.0

  total = 0.0

  # O(n)
  for k in range(len(tour) - 1):
    total += matriz_custos[tour[k]][tour[k + 1]]

  if retornar_ao_deposito:
    total += matriz_custos[tour[-1]][tour[0]]

  return total
