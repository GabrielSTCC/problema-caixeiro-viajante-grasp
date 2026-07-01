"""Caso de estudo: enderecos de entrega em Russas-CE."""

import re
import unicodedata
from typing import TypedDict


class EnderecoRussas(TypedDict):
  """Endereco com coordenadas geocodificadas."""

  nome: str
  endereco: str
  latitude: float
  longitude: float


# Coordenadas via OpenStreetMap (Nominatim) e dados postais (CEP).
# Indice 0 = deposito/base de operacoes.
ENDERECOS_RUSSAS: list[EnderecoRussas] = [
  {
    "nome": "Deposito",
    "endereco": "R. Maciel Pereira, 1054 - Vila Matoso",
    "latitude": -4.944268,
    "longitude": -37.973312,
  },
  {
    "nome": "Entrega 1",
    "endereco": "Av. Dom Lino, 656 - Centro",
    "latitude": -4.935800,
    "longitude": -37.970500,
  },
  {
    "nome": "Entrega 2",
    "endereco": "R. Gov. Raul Barbosa, 521 - Centro",
    "latitude": -4.936559,
    "longitude": -37.984130,
  },
  {
    "nome": "Entrega 3",
    "endereco": "Tv. Carlos Pontes, 88 - Centro",
    "latitude": -4.942648,
    "longitude": -37.968520,
  },
  {
    "nome": "Entrega 4",
    "endereco": "R. Nossa Sra. de Fatima, 214 - Nossa Sra. de Fatima",
    "latitude": -4.943201,
    "longitude": -37.969966,
  },
  {
    "nome": "Entrega 5",
    "endereco": "R. Jose Matoso Sobrinho, 146 - Tabuleiro da Vaquejada",
    "latitude": -4.926813,
    "longitude": -37.984562,
  },
  {
    "nome": "Entrega 6",
    "endereco": "Av. Cel. Antonio Cordeiro, 884 - Varzea Alegre",
    "latitude": -4.928048,
    "longitude": -37.970434,
  },
  {
    "nome": "Entrega 7",
    "endereco": "R. Vasco da Gama, 317 - Varzea Alegre",
    "latitude": -4.925825,
    "longitude": -37.969205,
  },
]


def normalizar_endereco(endereco: str) -> str:
  """Normaliza endereco para comparacao (sem acento, abreviacoes padronizadas)."""
  texto = endereco.strip().lower()
  texto = re.sub(r"\bR\.\s*", "rua ", texto, flags=re.IGNORECASE)
  texto = re.sub(r"\bAv\.\s*", "avenida ", texto, flags=re.IGNORECASE)
  texto = re.sub(r"\bTv\.\s*", "travessa ", texto, flags=re.IGNORECASE)
  sem_acento = unicodedata.normalize("NFKD", texto)
  sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
  return re.sub(r"\s+", " ", sem_acento).strip(" ,-")


INDICE_COORDENADAS_CONHECIDAS: dict[str, tuple[float, float]] = {
  normalizar_endereco(item["endereco"]): (item["latitude"], item["longitude"])
  for item in ENDERECOS_RUSSAS
}


def buscar_coordenadas_conhecidas(endereco: str) -> tuple[float, float] | None:
  """Retorna coordenadas do cadastro padrao se o endereco coincidir."""
  return INDICE_COORDENADAS_CONHECIDAS.get(normalizar_endereco(endereco))


def obter_pontos_geograficos(
  enderecos: list[EnderecoRussas] = ENDERECOS_RUSSAS,
) -> list[dict[str, float]]:
  """Converte enderecos para formato GeoPoint (latitude/longitude)."""
  return [
    {"latitude": item["latitude"], "longitude": item["longitude"]}
    for item in enderecos
  ]
