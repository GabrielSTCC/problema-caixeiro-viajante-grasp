"""Fase construtiva GRASP com Lista de Candidatos Restrita (LCR/RCL)."""

import random

from .tipos import CostMatrix, RclCandidate, Tour


def _validar_alpha(alpha: float) -> None:
  if alpha < 0 or alpha > 1:
    raise ValueError(f"alpha deve estar no intervalo [0, 1], recebido: {alpha}")


def _coletar_candidatos(
  matriz_custos: CostMatrix,
  no_atual: int,
  visitados: list[bool],
) -> list[RclCandidate]:
  """Coleta candidatos nao visitados a partir do no atual. Complexidade: O(n)"""
  candidatos: list[RclCandidate] = []

  # O(n)
  for j in range(len(visitados)):
    if not visitados[j]:
      candidatos.append({
        "node_index": j,
        "cost": matriz_custos[no_atual][j],
      })

  return candidatos


def _montar_lista_candidatos_restrita(
  candidatos: list[RclCandidate],
  alpha: float,
) -> tuple[list[RclCandidate], float, float, float]:
  """Monta a LCR/RCL. Limiar = C_min + alpha * (C_max - C_min). Complexidade: O(n)"""
  custo_min = candidatos[0]["cost"]
  custo_max = candidatos[0]["cost"]

  # O(n)
  for i in range(1, len(candidatos)):
    custo = candidatos[i]["cost"]
    if custo < custo_min:
      custo_min = custo
    if custo > custo_max:
      custo_max = custo

  limiar = custo_min + alpha * (custo_max - custo_min)

  # O(n)
  restritos = [c for c in candidatos if c["cost"] <= limiar]

  return restritos, custo_min, custo_max, limiar


def fase_construtiva_grasp(
  matriz_custos: CostMatrix,
  alpha: float,
  *,
  verbose: bool = False,
) -> Tour:
  """
  Fase construtiva GRASP com LCR/RCL. Parte do deposito (indice 0).

  Complexidade: Tempo O(n²), Espaco O(n)
  """
  _validar_alpha(alpha)

  n = len(matriz_custos)

  if n == 0:
    return []

  if n == 1:
    return [0]

  tour: Tour = [0]
  visitados: list[bool] = [False] * n
  visitados[0] = True
  no_atual = 0
  passo = 1

  if verbose:
    print("=" * 60)
    print("GRASP - Fase Construtiva (modo estudo)")
    print(f"alpha = {alpha}")
    print("=" * 60)
    print(f"\nPasso inicial: tour = {tour} (partindo do deposito, no 0)")

  # O(n) iteracoes; cada iteracao O(n) -> O(n²) total
  while len(tour) < n:
    candidatos = _coletar_candidatos(matriz_custos, no_atual, visitados)
    restritos, custo_min, custo_max, limiar = _montar_lista_candidatos_restrita(
      candidatos, alpha
    )

    if verbose:
      print(f"\n--- Passo {passo}: saindo do no {no_atual} ---")
      print("Candidatos nao visitados:")
      for c in candidatos:
        print(f"  no {c['node_index']}: custo = {c['cost']:.3f} km")
      print(f"C_min = {custo_min:.3f} km | C_max = {custo_max:.3f} km")
      print(
        f"Limiar = C_min + alpha * (C_max - C_min)"
        f" = {custo_min:.3f} + {alpha} * ({custo_max:.3f} - {custo_min:.3f})"
        f" = {limiar:.3f} km"
      )
      print("RCL (candidatos com custo <= limiar):")
      for c in restritos:
        print(f"  no {c['node_index']}: custo = {c['cost']:.3f} km")

    escolhido = random.choice(restritos)
    proximo_no = escolhido["node_index"]

    if verbose:
      print(f"Sorteado da RCL: no {proximo_no} (custo = {escolhido['cost']:.3f} km)")

    tour.append(proximo_no)
    visitados[proximo_no] = True
    no_atual = proximo_no
    passo += 1

    if verbose:
      print(f"Tour atual: {tour}")

  if verbose:
    print("\n" + "=" * 60)
    print(f"Tour final: {tour}")
    print("=" * 60)

  return tour
