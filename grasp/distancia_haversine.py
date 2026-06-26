"""Calculo de distancia geografica Haversine."""

import math
from typing import TypedDict


class GeoPoint(TypedDict):
    """Ponto geografico simulando retorno do PostGIS (SRID 4326)."""

    latitude: float
    longitude: float


EARTH_RADIUS_KM = 6371


def _para_radianos(graus: float) -> float:
  """Converte graus para radianos."""
  return graus * (math.pi / 180)


def calcular_haversine(a: GeoPoint, b: GeoPoint) -> float:
  """
  Calcula a distancia Haversine entre dois pontos geograficos.

  Complexidade: Tempo O(1), Espaco O(1)
  """
  lat1 = _para_radianos(a["latitude"])
  lat2 = _para_radianos(b["latitude"])
  delta_lat = _para_radianos(b["latitude"] - a["latitude"])
  delta_lng = _para_radianos(b["longitude"] - a["longitude"])

  sin_half_delta_lat = math.sin(delta_lat / 2)
  sin_half_delta_lng = math.sin(delta_lng / 2)

  haversine_formula = (
    sin_half_delta_lat ** 2
    + math.cos(lat1) * math.cos(lat2) * sin_half_delta_lng ** 2
  )

  return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(haversine_formula))
