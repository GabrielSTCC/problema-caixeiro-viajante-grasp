"""Busca local 2-opt para refinamento de tours TSP."""

from .custo_tour import calcular_custo_tour
from .tipos import CostMatrix, Tour


def _aplicar_troca_2opt(tour: Tour, i: int, j: int) -> Tour:
  """Inverte o segmento tour[i+1:j+1], mantendo o deposito fixo em tour[0]."""
  return tour[: i + 1] + tour[i + 1 : j + 1][::-1] + tour[j + 1 :]


def busca_local_2opt(
  tour: Tour,
  matriz_custos: CostMatrix,
  *,
  retornar_ao_deposito: bool = True,
) -> Tour:
  """
  Aplica busca local 2-opt ate atingir otimo local.

  Complexidade: O(n²) por passada; multiplas passadas ate convergencia
  """
  n = len(tour)
  if n <= 3:
    return tour[:]

  melhor_tour = tour[:]
  melhor_custo = calcular_custo_tour(
    melhor_tour, matriz_custos, retornar_ao_deposito=retornar_ao_deposito
  )
  melhorou = True

  while melhorou:
    melhorou = False

    # O(n²)
    for i in range(n - 1):
      for j in range(i + 1, n - 1):
        candidato = _aplicar_troca_2opt(melhor_tour, i, j)
        custo_candidato = calcular_custo_tour(
          candidato, matriz_custos, retornar_ao_deposito=retornar_ao_deposito
        )

        if custo_candidato < melhor_custo:
          melhor_tour = candidato
          melhor_custo = custo_candidato
          melhorou = True
          break

      if melhorou:
        break

  return melhor_tour
