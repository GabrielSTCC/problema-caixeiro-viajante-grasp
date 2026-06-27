"""Geometria de rota pelas ruas para visualizacao no mapa."""

from dados.enderecos_russas import EnderecoRussas
from grasp.distancia_haversine import GeoPoint
from grasp.tipos import Tour


def _endereco_para_geopoint(endereco: EnderecoRussas) -> GeoPoint:
  return {
    "latitude": endereco["latitude"],
    "longitude": endereco["longitude"],
  }


def _pontos_tour_ordenados(
  enderecos: list[EnderecoRussas],
  tour: Tour,
  *,
  retornar_ao_deposito: bool = True,
) -> list[GeoPoint]:
  pontos = [_endereco_para_geopoint(enderecos[indice]) for indice in tour]

  if retornar_ao_deposito and tour and tour[0] != tour[-1]:
    pontos.append(_endereco_para_geopoint(enderecos[tour[0]]))

  return pontos


def obter_coordenadas_rota(
  enderecos: list[EnderecoRussas],
  tour: Tour,
  *,
  usar_vias: bool = True,
) -> tuple[list[list[float]], bool]:
  """
  Retorna coordenadas [lat, lng] da rota e se seguem a malha viaria.

  Se usar_vias=True, tenta ORS Directions; em falha, usa linhas retas.
  """
  pontos = _pontos_tour_ordenados(enderecos, tour)

  if usar_vias:
    try:
      from infraestrutura.roteamento.cliente_ors_directions import (
        obter_geometria_rota_vias,
      )

      return obter_geometria_rota_vias(pontos), True
    except (ValueError, ImportError):
      pass

  return [[p["latitude"], p["longitude"]] for p in pontos], False
