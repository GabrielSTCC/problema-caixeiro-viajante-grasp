"""Cliente HTTP para a OpenRouteService Directions API."""

import json
import os
import urllib.error
import urllib.request
from typing import TypedDict

ORS_DIRECTIONS_BASE_URL = "https://api.openrouteservice.org/v2/directions"


class PontoGeografico(TypedDict):
  latitude: float
  longitude: float


class OpcoesDirections(TypedDict, total=False):
  api_key: str
  profile: str


def obter_geometria_rota_vias(
  pontos_ordenados: list[PontoGeografico],
  opcoes: OpcoesDirections | None = None,
) -> list[list[float]]:
  """
  Obtem coordenadas da rota pelas ruas via ORS Directions API.

  Retorna lista de [latitude, longitude] pronta para Folium.
  """
  opcoes = opcoes or {}

  if len(pontos_ordenados) < 2:
    return [
      [ponto["latitude"], ponto["longitude"]]
      for ponto in pontos_ordenados
    ]

  api_key = opcoes.get("api_key") or os.getenv("ORS_API_KEY")
  profile = opcoes.get("profile") or os.getenv("ORS_PROFILE") or "driving-car"

  if not api_key:
    raise ValueError(
      "ORS_API_KEY nao configurada. Necessaria para geometria de rota pelas ruas."
    )

  coordinates = [
    [ponto["longitude"], ponto["latitude"]]
    for ponto in pontos_ordenados
  ]
  payload = json.dumps({"coordinates": coordinates}).encode("utf-8")

  request = urllib.request.Request(
    f"{ORS_DIRECTIONS_BASE_URL}/{profile}/geojson",
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

  features = data.get("features")
  if not features:
    raise ValueError("Resposta ORS invalida: nenhuma geometria de rota retornada")

  geometry = features[0].get("geometry", {})
  coordenadas = geometry.get("coordinates")
  if not coordenadas:
    raise ValueError("Resposta ORS invalida: geometria da rota ausente")

  return [[lat, lng] for lng, lat in coordenadas]


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

  return ValueError(f"Erro na ORS Directions API ({error.code}){detail}")
