"""Cliente HTTP para geocodificacao via Nominatim (OpenStreetMap)."""

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from dados.localidades_brasil import NOMES_ESTADOS
from infraestrutura.roteamento.cliente_ors_geocode import PartesEndereco, extrair_partes_endereco

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PAA-GRASP-TSP/1.0 (projeto academico; contato via GitHub)"
ULTIMA_REQUISICAO = 0.0
INTERVALO_MINIMO_SEG = 1.1

VIEWBOX_RUSSAS = "-38.02,-4.90,-37.94,-4.96"
PONTUACAO_MINIMA = 8
TIPOS_GENERICOS = frozenset({"administrative", "city", "town", "village", "municipality"})


@dataclass(frozen=True)
class ResultadoGeocodeNominatim:
  latitude: float
  longitude: float
  label: str
  tipo: str = ""


def _aguardar_rate_limit() -> None:
  global ULTIMA_REQUISICAO
  agora = time.monotonic()
  espera = INTERVALO_MINIMO_SEG - (agora - ULTIMA_REQUISICAO)
  if espera > 0:
    time.sleep(espera)
  ULTIMA_REQUISICAO = time.monotonic()


def _normalizar_texto_comparacao(texto: str) -> str:
  sem_acento = unicodedata.normalize("NFKD", texto)
  sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
  return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _variantes_consulta(partes: PartesEndereco) -> list[str]:
  sufixo = f"{partes.cidade}, {partes.estado}, Brasil"
  variantes = [partes.texto_contextualizado, f"{partes.street}, {sufixo}"]

  if partes.bairro:
    variantes.append(f"{partes.street}, {partes.bairro}, {sufixo}")
    variantes.append(f"{partes.logradouro}, {partes.bairro}, {sufixo}")

  if partes.numero:
    variantes.append(f"{partes.numero} {partes.logradouro}, {sufixo}")

  vistos: set[str] = set()
  unicos: list[str] = []
  for item in variantes:
    chave = item.lower()
    if chave not in vistos:
      vistos.add(chave)
      unicos.append(item)
  return unicos


def _buscar_nominatim(params: dict[str, str | int]) -> list[dict]:
  _aguardar_rate_limit()
  request = urllib.request.Request(
    f"{NOMINATIM_SEARCH_URL}?{urllib.parse.urlencode(params)}",
    headers={"User-Agent": USER_AGENT},
    method="GET",
  )

  try:
    with urllib.request.urlopen(request, timeout=15) as response:
      return json.loads(response.read().decode("utf-8"))
  except TimeoutError as error:
    raise ValueError("Timeout Nominatim: servico demorou para responder") from error
  except urllib.error.HTTPError as error:
    raise ValueError(f"Erro Nominatim ({error.code})") from error
  except urllib.error.URLError as error:
    raise ValueError(f"Falha de conexao com Nominatim: {error.reason}") from error
  except OSError as error:
    raise ValueError(f"Falha de rede Nominatim: {error}") from error


def _buscar_estruturado(partes: PartesEndereco) -> list[dict]:
  nome_estado = NOMES_ESTADOS.get(partes.estado, partes.estado)
  params: dict[str, str | int] = {
    "street": partes.street,
    "city": partes.cidade,
    "state": nome_estado,
    "country": "Brazil",
    "format": "json",
    "limit": 5,
    "countrycodes": "br",
    "addressdetails": 1,
  }
  if partes.bairro:
    params["suburb"] = partes.bairro
  if partes.cep:
    params["postalcode"] = partes.cep

  usar_viewbox = partes.cidade.lower() == "russas" and partes.estado == "CE"
  if usar_viewbox:
    params["viewbox"] = VIEWBOX_RUSSAS
    params["bounded"] = 0

  return _buscar_nominatim(params)


def _buscar_texto(consulta: str, *, usar_viewbox_russas: bool) -> list[dict]:
  params: dict[str, str | int] = {
    "q": consulta,
    "format": "json",
    "limit": 5,
    "countrycodes": "br",
    "addressdetails": 1,
  }
  if usar_viewbox_russas:
    params["viewbox"] = VIEWBOX_RUSSAS
    params["bounded"] = 0
  return _buscar_nominatim(params)


def _cidade_no_resultado(item: dict, cidade: str) -> bool:
  cidade_norm = _normalizar_texto_comparacao(cidade)
  endereco = item.get("address", {})
  campos = (
    endereco.get("city"),
    endereco.get("town"),
    endereco.get("municipality"),
    endereco.get("county"),
    item.get("display_name"),
  )
  for campo in campos:
    if campo and cidade_norm in _normalizar_texto_comparacao(str(campo)):
      return True
  return False


def _pontuar_resultado(item: dict, partes: PartesEndereco) -> int:
  if not _cidade_no_resultado(item, partes.cidade):
    return -1

  score = 0
  tipo = str(item.get("type") or item.get("class") or "")
  if tipo in {"house", "building", "residential"}:
    score += 20
  elif tipo in {"road", "highway"}:
    score += 15
  elif tipo in {"suburb", "neighbourhood"}:
    score += 5
  else:
    score += 1

  nome = _normalizar_texto_comparacao(item.get("display_name", ""))
  if partes.bairro and _normalizar_texto_comparacao(partes.bairro) in nome:
    score += 4

  palavras = [p for p in _normalizar_texto_comparacao(partes.logradouro).split() if len(p) > 2]
  if palavras and any(p in nome for p in palavras):
    score += 4

  if partes.numero and partes.numero in nome:
    score += 6
  elif partes.numero:
    score -= 10

  importancia = float(item.get("importance") or 0)
  score += int(importancia * 10)

  tipo = str(item.get("type") or item.get("class") or "")
  classe = str(item.get("class") or "")
  if classe == "place" and tipo in TIPOS_GENERICOS and score < PONTUACAO_MINIMA:
    return -1

  return score


def _escolher_melhor_resultado(
  resultados: list[dict],
  partes: PartesEndereco,
) -> ResultadoGeocodeNominatim | None:
  melhor: dict | None = None
  melhor_score = -1

  for item in resultados:
    score = _pontuar_resultado(item, partes)
    if score >= PONTUACAO_MINIMA and score > melhor_score:
      melhor_score = score
      melhor = item

  if melhor is None:
    return None

  return ResultadoGeocodeNominatim(
    latitude=float(melhor["lat"]),
    longitude=float(melhor["lon"]),
    label=str(melhor.get("display_name") or ""),
    tipo=str(melhor.get("type") or melhor.get("class") or ""),
  )


def _buscar_bairro(partes: PartesEndereco) -> list[dict]:
  if not partes.bairro:
    return []

  nome_estado = NOMES_ESTADOS.get(partes.estado, partes.estado)
  params: dict[str, str | int] = {
    "city": partes.cidade,
    "state": nome_estado,
    "country": "Brazil",
    "suburb": partes.bairro,
    "format": "json",
    "limit": 5,
    "countrycodes": "br",
    "addressdetails": 1,
  }

  usar_viewbox = partes.cidade.lower() == "russas" and partes.estado == "CE"
  if usar_viewbox:
    params["viewbox"] = VIEWBOX_RUSSAS
    params["bounded"] = 0

  try:
    return _buscar_nominatim(params)
  except (urllib.error.HTTPError, urllib.error.URLError):
    return []


def geocodificar_bairro(partes: PartesEndereco) -> ResultadoGeocodeNominatim | None:
  """Geocodifica bairro + cidade quando a rua nao e encontrada."""
  if not partes.bairro:
    return None

  sufixo = f"{partes.cidade}, {partes.estado}, Brasil"
  consulta = f"{partes.bairro}, {sufixo}"
  usar_viewbox = partes.cidade.lower() == "russas" and partes.estado == "CE"

  resultados: list[dict] = []
  resultados.extend(_buscar_bairro(partes))
  try:
    resultados.extend(_buscar_texto(consulta, usar_viewbox_russas=usar_viewbox))
  except (urllib.error.HTTPError, urllib.error.URLError):
    pass

  return _escolher_melhor_resultado(resultados, partes)


def geocodificar_endereco(
  endereco: str,
  *,
  cidade: str = "Russas",
  estado: str = "CE",
  partes: PartesEndereco | None = None,
) -> ResultadoGeocodeNominatim:
  """
  Converte endereco em coordenadas via Nominatim.

  Raises:
    ValueError: se o endereco for vazio ou nao encontrado.
  """
  if not endereco.strip():
    raise ValueError("Endereco vazio para geocodificacao.")

  componentes = partes or extrair_partes_endereco(endereco, cidade=cidade, estado=estado)
  usar_viewbox = componentes.cidade.lower() == "russas" and componentes.estado == "CE"
  todos_resultados: list[dict] = []

  try:
    todos_resultados.extend(_buscar_estruturado(componentes))
  except urllib.error.HTTPError as error:
    raise ValueError(f"Erro Nominatim ({error.code})") from error
  except urllib.error.URLError as error:
    raise ValueError(f"Falha de conexao com Nominatim: {error.reason}") from error

  for consulta in _variantes_consulta(componentes):
    try:
      todos_resultados.extend(
        _buscar_texto(consulta, usar_viewbox_russas=usar_viewbox)
      )
    except urllib.error.HTTPError as error:
      raise ValueError(f"Erro Nominatim ({error.code})") from error
    except urllib.error.URLError as error:
      raise ValueError(f"Falha de conexao com Nominatim: {error.reason}") from error

  melhor = _escolher_melhor_resultado(todos_resultados, componentes)
  if melhor is None:
    raise ValueError(f"Endereco nao encontrado: {endereco}")

  return melhor
