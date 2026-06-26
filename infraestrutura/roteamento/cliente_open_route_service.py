"""Cliente HTTP para a OpenRouteService Matrix API."""

import json
import os
import urllib.error
import urllib.request
from typing import TypedDict

from grasp.distancia_haversine import GeoPoint

CostMatrix = list[list[float]]

ORS_MATRIX_BASE_URL = "https://api.openrouteservice.org/v2/matrix"


class OpcoesOpenRouteService(TypedDict, total=False):
  api_key: str
  profile: str


def obter_matriz_distancias(
  pontos: list[GeoPoint],
  opcoes: OpcoesOpenRouteService | None = None,
) -> CostMatrix:
  """
  Obtem a matriz de distancias reais via OpenRouteService Matrix API.

  Complexidade: Tempo O(1) local (1 requisicao HTTP); Espaco O(n²)
  """
  opcoes = opcoes or {}
  n = len(pontos)

  if n == 0:
    return []

  if n == 1:
    return [[0.0]]

  api_key = opcoes.get("api_key") or os.getenv("ORS_API_KEY")
  profile = opcoes.get("profile") or os.getenv("ORS_PROFILE") or "driving-car"

  if not api_key:
    raise ValueError(
      "ORS_API_KEY nao configurada. Crie uma conta em https://openrouteservice.org/ "
      "e defina a chave no arquivo .env"
    )

  locations = [[ponto["longitude"], ponto["latitude"]] for ponto in pontos]
  payload = json.dumps({"locations": locations, "metrics": ["distance"]}).encode("utf-8")

  request = urllib.request.Request(
    f"{ORS_MATRIX_BASE_URL}/{profile}",
    data=payload,
    headers={
      "Authorization": api_key,
      "Content-Type": "application/json",
    },
    method="POST",
  )

  try:
    with urllib.request.urlopen(request) as response:
      data = json.loads(response.read().decode("utf-8"))
  except urllib.error.HTTPError as error:
    raise _mapear_erro_http(error) from error

  distances = data.get("distances")
  if distances is None:
    raise ValueError("Resposta ORS invalida: campo 'distances' ausente")

  return _normalizar_matriz_distancias(distances)


def _mapear_erro_http(error: urllib.error.HTTPError) -> ValueError:
  detail = ""

  try:
    body = json.loads(error.read().decode("utf-8"))
    if isinstance(body, dict):
      error_field = body.get("error")
      if isinstance(error_field, dict):
        message = error_field.get("message")
      elif isinstance(error_field, str):
        message = error_field
      else:
        message = body.get("message")
      if message:
        detail = f": {message}"
  except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
    detail = ""

  if error.code in (401, 403):
    return ValueError(f"ORS API key invalida ou sem permissao{detail}")

  if error.code == 429:
    return ValueError(f"ORS rate limit excedido{detail}")

  return ValueError(f"Erro na ORS Matrix API ({error.code}){detail}")


def _normalizar_matriz_distancias(
  distancias_metros: list[list[float | None]],
) -> CostMatrix:
  inalcancaveis: list[str] = []

  matrix: CostMatrix = []
  for i, row in enumerate(distancias_metros):
    normalized_row: list[float] = []
    for j, distancia_metros in enumerate(row):
      if i == j:
        normalized_row.append(0.0)
      elif distancia_metros is None:
        inalcancaveis.append(f"({i}, {j})")
        normalized_row.append(0.0)
      else:
        normalized_row.append(distancia_metros / 1000)
    matrix.append(normalized_row)

  if inalcancaveis:
    raise ValueError(
      "Coordenadas inalcancaveis na malha viaria ORS nos pares: "
      + ", ".join(inalcancaveis)
    )

  return matrix
