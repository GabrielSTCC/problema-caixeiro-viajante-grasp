"""Cliente HTTP para geocodificacao via Google Geocoding API."""

import json
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from infraestrutura.roteamento.cliente_ors_geocode import PartesEndereco, extrair_partes_endereco

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PONTUACAO_LOCATION_TYPE = {
  "ROOFTOP": 40,
  "RANGE_INTERPOLATED": 30,
  "GEOMETRIC_CENTER": 10,
  "APPROXIMATE": 5,
}


@dataclass(frozen=True)
class ResultadoGeocodeGoogle:
  latitude: float
  longitude: float
  label: str
  location_type: str = ""


def _obter_api_key() -> str | None:
  api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
  return api_key or None


def google_geocode_disponivel() -> bool:
  return _obter_api_key() is not None


def _normalizar_texto_comparacao(texto: str) -> str:
  sem_acento = unicodedata.normalize("NFKD", texto)
  sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
  return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _cidade_corresponde(resultado: dict, cidade: str) -> bool:
  cidade_norm = _normalizar_texto_comparacao(cidade)
  for componente in resultado.get("address_components", []):
    tipos = componente.get("types", [])
    if not any(tipo in tipos for tipo in ("locality", "administrative_area_level_2", "postal_town")):
      continue
    if cidade_norm in _normalizar_texto_comparacao(componente.get("long_name", "")):
      return True
    if cidade_norm in _normalizar_texto_comparacao(componente.get("short_name", "")):
      return True
  endereco_formatado = _normalizar_texto_comparacao(resultado.get("formatted_address", ""))
  return cidade_norm in endereco_formatado


def _estado_corresponde(resultado: dict, estado: str, nome_estado: str) -> bool:
  estado_norm = _normalizar_texto_comparacao(estado)
  nome_norm = _normalizar_texto_comparacao(nome_estado)
  for componente in resultado.get("address_components", []):
    if "administrative_area_level_1" not in componente.get("types", []):
      continue
    texto = _normalizar_texto_comparacao(componente.get("short_name", ""))
    if estado_norm == texto:
      return True
    texto = _normalizar_texto_comparacao(componente.get("long_name", ""))
    if nome_norm in texto:
      return True
  return False


def _pontuar_resultado(resultado: dict, partes: PartesEndereco) -> int:
  if not _cidade_corresponde(resultado, partes.cidade):
    return -1
  if not _estado_corresponde(resultado, partes.estado, partes.nome_estado):
    return -1

  geometry = resultado.get("geometry", {})
  location_type = str(geometry.get("location_type") or "")
  score = PONTUACAO_LOCATION_TYPE.get(location_type, 0)

  label = _normalizar_texto_comparacao(resultado.get("formatted_address", ""))
  palavras = [p for p in _normalizar_texto_comparacao(partes.logradouro).split() if len(p) > 2]
  if palavras and any(palavra in label for palavra in palavras):
    score += 4

  if partes.numero and partes.numero in label:
    score += 8

  if partes.bairro and _normalizar_texto_comparacao(partes.bairro) in label:
    score += 3

  return score


def _escolher_melhor_resultado(
  resultados: list[dict],
  partes: PartesEndereco,
) -> ResultadoGeocodeGoogle | None:
  melhor: dict | None = None
  melhor_score = -1

  for item in resultados:
    score = _pontuar_resultado(item, partes)
    if score > melhor_score:
      melhor_score = score
      melhor = item

  if melhor is None or melhor_score < 0:
    return None

  location = melhor["geometry"]["location"]
  return ResultadoGeocodeGoogle(
    latitude=float(location["lat"]),
    longitude=float(location["lng"]),
    label=str(melhor.get("formatted_address") or ""),
    location_type=str(melhor.get("geometry", {}).get("location_type") or ""),
  )


def geocodificar_endereco_google(
  endereco: str,
  *,
  partes: PartesEndereco | None = None,
) -> ResultadoGeocodeGoogle:
  """
  Geocodifica via Google Geocoding API.

  Raises:
    ValueError: se a chave nao estiver configurada ou o endereco nao for encontrado.
  """
  api_key = _obter_api_key()
  if not api_key:
    raise ValueError("GOOGLE_MAPS_API_KEY nao configurada para geocodificacao.")

  componentes = partes or extrair_partes_endereco(endereco)
  params = {
    "address": componentes.texto_contextualizado,
    "key": api_key,
    "region": "br",
    "language": "pt-BR",
  }
  query = urllib.parse.urlencode(params)
  request = urllib.request.Request(
    f"{GOOGLE_GEOCODE_URL}?{query}",
    headers={"Accept": "application/json"},
    method="GET",
  )

  try:
    with urllib.request.urlopen(request, timeout=20) as response:
      data = json.loads(response.read().decode("utf-8"))
  except urllib.error.HTTPError as error:
    raise ValueError(f"Erro Google Geocode ({error.code})") from error
  except TimeoutError as error:
    raise ValueError("Timeout Google Geocode: servico demorou para responder") from error
  except urllib.error.URLError as error:
    raise ValueError(f"Falha de conexao com Google Geocode: {error.reason}") from error
  except OSError as error:
    raise ValueError(f"Falha de rede Google Geocode: {error}") from error

  status = data.get("status")
  if status != "OK":
    mensagem = data.get("error_message") or status or "erro desconhecido"
    raise ValueError(f"Google Geocode: {mensagem}")

  resultados = data.get("results", [])
  melhor = _escolher_melhor_resultado(resultados, componentes)
  if melhor is None:
    raise ValueError(f"Endereco nao encontrado (Google): {endereco}")

  return melhor
