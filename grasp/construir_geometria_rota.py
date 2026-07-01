"""Geometria de rota pelas ruas para visualizacao no mapa."""

from dataclasses import dataclass, field

from dados.enderecos_russas import EnderecoRussas
from grasp.distancia_haversine import GeoPoint
from grasp.tipos import Tour


@dataclass
class ResultadoCoordenadasRota:
  coordenadas: list[list[float]]
  segue_vias: bool
  avisos: list[str] = field(default_factory=list)


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
) -> tuple[list[list[float]], bool, list[str]]:
  """
  Retorna coordenadas [lat, lng], flag de vias e avisos.

  Se usar_vias=True, tenta ORS Directions; em falha, usa linhas retas.
  """
  resultado = obter_coordenadas_rota_detalhado(enderecos, tour, usar_vias=usar_vias)
  return resultado.coordenadas, resultado.segue_vias, resultado.avisos


def obter_coordenadas_rota_detalhado(
  enderecos: list[EnderecoRussas],
  tour: Tour,
  *,
  usar_vias: bool = True,
) -> ResultadoCoordenadasRota:
  pontos = _pontos_tour_ordenados(enderecos, tour)
  linhas_retas = [[p["latitude"], p["longitude"]] for p in pontos]

  if usar_vias:
    try:
      from infraestrutura.roteamento.cliente_ors_directions import (
        obter_geometria_rota_detalhada,
      )

      detalhe = obter_geometria_rota_detalhada(pontos)
      return ResultadoCoordenadasRota(
        coordenadas=detalhe["coordenadas"],
        segue_vias=detalhe["segue_vias"],
        avisos=detalhe["avisos"],
      )
    except (ValueError, ImportError) as erro:
      return ResultadoCoordenadasRota(
        coordenadas=linhas_retas,
        segue_vias=False,
        avisos=[str(erro)],
      )

  return ResultadoCoordenadasRota(
    coordenadas=linhas_retas,
    segue_vias=False,
    avisos=[],
  )
