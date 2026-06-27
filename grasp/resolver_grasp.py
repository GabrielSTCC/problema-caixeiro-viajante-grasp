"""Meta-heuristica GRASP completa: construcao + busca local 2-opt."""

from collections.abc import Callable
from dataclasses import dataclass

from .busca_local_2opt import busca_local_2opt
from .custo_tour import calcular_custo_tour
from .fase_construtiva_grasp import fase_construtiva_grasp
from .tipos import CostMatrix, Tour


@dataclass
class ResultadoGrasp:
  """Resultado da execucao do GRASP."""

  tour: Tour
  custo_km: float
  iteracoes: int


def resolver_grasp(
  matriz_custos: CostMatrix,
  *,
  alpha: float = 0.3,
  max_iteracoes: int = 100,
  retornar_ao_deposito: bool = True,
  verbose: bool = False,
  on_melhoria: Callable[[int, float, Tour], None] | None = None,
  on_iteracao: Callable[[int, int], None] | None = None,
) -> ResultadoGrasp:
  """
  Executa GRASP completo com multiplas iteracoes e busca local 2-opt.

  Complexidade: O(k * n²), onde k = max_iteracoes
  """
  melhor_tour: Tour | None = None
  melhor_custo = float("inf")

  if verbose:
    print(f"\nGRASP - {max_iteracoes} iteracoes (alpha={alpha})")
    print("-" * 60)

  # O(k)
  for iteracao in range(1, max_iteracoes + 1):
    construtivo_verbose = verbose and iteracao == 1
    tour = fase_construtiva_grasp(
      matriz_custos, alpha, verbose=construtivo_verbose
    )
    tour = busca_local_2opt(
      tour, matriz_custos, retornar_ao_deposito=retornar_ao_deposito
    )
    custo = calcular_custo_tour(
      tour, matriz_custos, retornar_ao_deposito=retornar_ao_deposito
    )

    if custo < melhor_custo:
      melhor_custo = custo
      melhor_tour = tour
      if on_melhoria is not None:
        on_melhoria(iteracao, custo, tour)
      if verbose:
        print(
          f"Iteracao {iteracao}: novo melhor custo = {custo:.3f} km, "
          f"tour = {tour}"
        )

    if on_iteracao is not None:
      on_iteracao(iteracao, max_iteracoes)

  if melhor_tour is None:
    return ResultadoGrasp(tour=[], custo_km=0.0, iteracoes=max_iteracoes)

  return ResultadoGrasp(
    tour=melhor_tour,
    custo_km=melhor_custo,
    iteracoes=max_iteracoes,
  )
