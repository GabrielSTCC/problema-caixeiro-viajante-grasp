"""Tipos compartilhados do modulo GRASP."""

from typing import TypedDict

CostMatrix = list[list[float]]
Tour = list[int]


class RclCandidate(TypedDict):
  """Candidato avaliado durante a fase construtiva GRASP."""

  node_index: int
  cost: float
