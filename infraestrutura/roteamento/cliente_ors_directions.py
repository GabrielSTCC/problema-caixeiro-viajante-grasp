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


class ResultadoGeometriaRota(TypedDict):
  coordenadas: list[list[float]]
  segue_vias: bool
  avisos: list[str]


def _obter_credenciais(opcoes: OpcoesDirections | None) -> tuple[str, str]:
  opcoes = opcoes or {}
  api_key = opcoes.get("api_key") or os.getenv("ORS_API_KEY", "")
  profile = opcoes.get("profile") or os.getenv("ORS_PROFILE") or "driving-car"
  if not api_key:
    raise ValueError(
      "ORS_API_KEY nao configurada. Necessaria para geometria de rota pelas ruas."
    )
  return api_key, profile


def _requisitar_geometria_trecho(
  origem: PontoGeografico,
  destino: PontoGeografico,
  *,
  api_key: str,
  profile: str,
) -> list[list[float]]:
  coordinates = [
    [origem["longitude"], origem["latitude"]],
    [destino["longitude"], destino["latitude"]],
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
    with urllib.request.urlopen(request, timeout=20) as response:
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


def obter_geometria_rota_vias(
  pontos_ordenados: list[PontoGeografico],
  opcoes: OpcoesDirections | None = None,
) -> list[list[float]]:
  """
  Obtem coordenadas da rota pelas ruas via ORS Directions API (trecho a trecho).

  Retorna lista de [latitude, longitude] pronta para Folium.
  """
  resultado = obter_geometria_rota_detalhada(pontos_ordenados, opcoes=opcoes)
  return resultado["coordenadas"]


def obter_geometria_rota_detalhada(
  pontos_ordenados: list[PontoGeografico],
  opcoes: OpcoesDirections | None = None,
) -> ResultadoGeometriaRota:
  if len(pontos_ordenados) < 2:
    return {
      "coordenadas": [
        [ponto["latitude"], ponto["longitude"]]
        for ponto in pontos_ordenados
      ],
      "segue_vias": False,
      "avisos": [],
    }

  api_key, profile = _obter_credenciais(opcoes)
  coordenadas: list[list[float]] = []
  avisos: list[str] = []
  trechos_vias = 0

  for indice in range(len(pontos_ordenados) - 1):
    origem = pontos_ordenados[indice]
    destino = pontos_ordenados[indice + 1]
    try:
      trecho = _requisitar_geometria_trecho(
        origem,
        destino,
        api_key=api_key,
        profile=profile,
      )
      if coordenadas and trecho:
        trecho = trecho[1:]
      coordenadas.extend(trecho)
      trechos_vias += 1
    except ValueError as erro:
      avisos.append(f"Trecho {indice + 1}->{indice + 2}: {erro}")
      linha = [
        [origem["latitude"], origem["longitude"]],
        [destino["latitude"], destino["longitude"]],
      ]
      if coordenadas:
        linha = linha[1:]
      coordenadas.extend(linha)

  if not coordenadas:
    coordenadas = [
      [ponto["latitude"], ponto["longitude"]]
      for ponto in pontos_ordenados
    ]

  return {
    "coordenadas": coordenadas,
    "segue_vias": trechos_vias > 0 and trechos_vias == len(pontos_ordenados) - 1,
    "avisos": avisos,
  }


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
