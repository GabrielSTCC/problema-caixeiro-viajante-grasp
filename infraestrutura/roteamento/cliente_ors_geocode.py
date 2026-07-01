"""Cliente HTTP para geocodificacao via OpenRouteService."""

import json
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from dados.localidades_brasil import NOMES_ESTADOS

ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_GEOCODE_STRUCTURED_URL = "https://api.openrouteservice.org/geocode/search/structured"
ORS_RESULTADOS_MAX = 5
CONFIANCA_MINIMA = 0.3
PONTUACAO_MINIMA = 8
LAYER_GENERICOS = frozenset({"locality", "localadmin", "county", "region"})


@dataclass(frozen=True)
class PartesEndereco:
  """Componentes de um endereco brasileiro para geocodificacao."""

  logradouro: str
  numero: str
  bairro: str
  cep: str
  cidade: str
  estado: str

  @property
  def street(self) -> str:
    if self.numero:
      return f"{self.logradouro}, {self.numero}"
    return self.logradouro

  @property
  def texto_contextualizado(self) -> str:
    partes = [self.street]
    if self.bairro:
      partes.append(self.bairro)
    partes.append(f"{self.cidade}, {self.estado}, Brasil")
    return ", ".join(partes)

  @property
  def nome_estado(self) -> str:
    return NOMES_ESTADOS.get(self.estado, self.estado)


@dataclass(frozen=True)
class ResultadoGeocodeOrs:
  latitude: float
  longitude: float
  label: str
  layer: str = ""


def _obter_api_key() -> str:
  api_key = os.getenv("ORS_API_KEY", "").strip()
  if not api_key:
    raise ValueError("ORS_API_KEY nao configurada para geocodificacao.")
  return api_key


def _normalizar_texto_comparacao(texto: str) -> str:
  sem_acento = unicodedata.normalize("NFKD", texto)
  sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
  return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _normalizar_logradouro(texto: str) -> str:
  texto = texto.strip()
  texto = re.sub(r"\bR\.\s*", "Rua ", texto, flags=re.IGNORECASE)
  texto = re.sub(r"\bAv\.\s*", "Avenida ", texto, flags=re.IGNORECASE)
  texto = re.sub(r"\bTv\.\s*", "Travessa ", texto, flags=re.IGNORECASE)
  return texto


def extrair_partes_endereco(
  endereco: str,
  *,
  cidade: str = "Russas",
  estado: str = "CE",
) -> PartesEndereco:
  """Extrai logradouro, numero, bairro e CEP de enderecos brasileiros."""
  texto = _normalizar_logradouro(endereco.strip())
  cidade_limpa = cidade.strip() or "Russas"
  uf = estado.strip().upper() or "CE"

  cep = ""
  match_cep = re.search(r"(\d{5}-?\d{3})", texto)
  if match_cep:
    cep = match_cep.group(1)
    texto = texto.replace(match_cep.group(1), "").strip(" ,-")

  texto = re.sub(rf",\s*{re.escape(cidade_limpa)}.*$", "", texto, flags=re.IGNORECASE)
  texto = re.sub(r",\s*[A-Za-z]{2}\s*$", "", texto).strip(" ,-")

  logradouro = texto
  numero = ""
  bairro = ""

  match_completo = re.match(r"^(.+?),\s*(\d+)\s*-\s*(.+)$", texto)
  if match_completo:
    logradouro = match_completo.group(1).strip()
    numero = match_completo.group(2).strip()
    bairro = match_completo.group(3).strip()
  else:
    match_numero = re.match(r"^(.+?),\s*(\d+)$", texto)
    if match_numero:
      logradouro = match_numero.group(1).strip()
      numero = match_numero.group(2).strip()
    elif " - " in texto:
      antes, bairro = texto.rsplit(" - ", 1)
      bairro = bairro.strip()
      logradouro = antes.strip()

  return PartesEndereco(
    logradouro=logradouro,
    numero=numero,
    bairro=bairro,
    cep=cep,
    cidade=cidade_limpa,
    estado=uf,
  )


def _cidade_corresponde(propriedades: dict, cidade: str) -> bool:
  cidade_norm = _normalizar_texto_comparacao(cidade)
  campos = (
    propriedades.get("locality"),
    propriedades.get("localadmin"),
    propriedades.get("county"),
    propriedades.get("name"),
    propriedades.get("label"),
  )
  for campo in campos:
    if campo and cidade_norm in _normalizar_texto_comparacao(str(campo)):
      return True
  return False


def _estado_corresponde(propriedades: dict, estado: str, nome_estado: str) -> bool:
  estado_norm = _normalizar_texto_comparacao(estado)
  nome_norm = _normalizar_texto_comparacao(nome_estado)
  campos = (
    propriedades.get("region"),
    propriedades.get("macroregion"),
    propriedades.get("name"),
    propriedades.get("label"),
  )
  for campo in campos:
    texto = _normalizar_texto_comparacao(str(campo))
    if estado_norm in texto or nome_norm in texto:
      return True
  return False


def _pontuar_layer(layer: str) -> int:
  prioridade = {
    "address": 20,
    "venue": 18,
    "street": 15,
    "neighbourhood": 8,
    "borough": 6,
    "localadmin": 2,
    "locality": 1,
    "county": 1,
    "region": 0,
  }
  return prioridade.get(layer, 0)


def _pontuar_feature(feature: dict, partes: PartesEndereco) -> int:
  propriedades = feature.get("properties", {})
  score = 0

  if not _cidade_corresponde(propriedades, partes.cidade):
    return -1

  if not _estado_corresponde(propriedades, partes.estado, partes.nome_estado):
    return -1

  score += _pontuar_layer(str(propriedades.get("layer") or ""))

  label = _normalizar_texto_comparacao(
    str(propriedades.get("label") or propriedades.get("name") or "")
  )
  if partes.bairro and _normalizar_texto_comparacao(partes.bairro) in label:
    score += 3

  logradouro_norm = _normalizar_texto_comparacao(partes.logradouro)
  palavras_logradouro = [p for p in logradouro_norm.split() if len(p) > 2]
  if palavras_logradouro and any(p in label for p in palavras_logradouro):
    score += 4

  if partes.numero and partes.numero in label:
    score += 6
  elif partes.numero:
    score -= 10

  confianca = propriedades.get("confidence")
  if confianca is not None and float(confianca) < CONFIANCA_MINIMA:
    return -1

  layer = str(propriedades.get("layer") or "")
  if layer in LAYER_GENERICOS and score < PONTUACAO_MINIMA:
    return -1

  return score


def _feature_para_resultado(feature: dict) -> ResultadoGeocodeOrs:
  coords = feature["geometry"]["coordinates"]
  propriedades = feature.get("properties", {})
  label = str(propriedades.get("label") or propriedades.get("name") or "")
  return ResultadoGeocodeOrs(
    latitude=float(coords[1]),
    longitude=float(coords[0]),
    label=label,
    layer=str(propriedades.get("layer") or ""),
  )


def _escolher_melhor_feature(
  features: list[dict],
  partes: PartesEndereco,
) -> ResultadoGeocodeOrs | None:
  melhor: ResultadoGeocodeOrs | None = None
  melhor_score = -1

  for feature in features:
    score = _pontuar_feature(feature, partes)
    if score >= PONTUACAO_MINIMA and score > melhor_score:
      melhor_score = score
      melhor = _feature_para_resultado(feature)

  return melhor


def _requisitar_ors(url: str, params: dict[str, str]) -> dict:
  query = urllib.parse.urlencode(params)
  request = urllib.request.Request(
    f"{url}?{query}",
    headers={"Accept": "application/json"},
    method="GET",
  )
  try:
    with urllib.request.urlopen(request, timeout=20) as response:
      return json.loads(response.read().decode("utf-8"))
  except urllib.error.HTTPError as error:
    raise ValueError(f"Erro ORS Geocode ({error.code})") from error
  except TimeoutError as error:
    raise ValueError("Timeout ORS Geocode: servico demorou para responder") from error
  except urllib.error.URLError as error:
    raise ValueError(f"Falha de conexao com ORS Geocode: {error.reason}") from error
  except OSError as error:
    raise ValueError(f"Falha de rede ORS Geocode: {error}") from error


def _buscar_ors_estruturado(partes: PartesEndereco) -> list[dict]:
  api_key = _obter_api_key()
  params: dict[str, str] = {
    "api_key": api_key,
    "street": partes.street,
    "locality": partes.cidade,
    "region": partes.nome_estado,
    "country": "BRA",
    "size": str(ORS_RESULTADOS_MAX),
  }
  if partes.bairro:
    params["neighbourhood"] = partes.bairro
  if partes.cep:
    params["postalcode"] = partes.cep

  data = _requisitar_ors(ORS_GEOCODE_STRUCTURED_URL, params)
  return data.get("features", [])


def _buscar_ors_texto(texto: str) -> list[dict]:
  api_key = _obter_api_key()
  params = {
    "api_key": api_key,
    "text": texto,
    "boundary.country": "BRA",
    "size": str(ORS_RESULTADOS_MAX),
  }
  data = _requisitar_ors(ORS_GEOCODE_URL, params)
  return data.get("features", [])


def geocodificar_endereco_ors(
  endereco: str,
  *,
  partes: PartesEndereco | None = None,
) -> ResultadoGeocodeOrs:
  """
  Geocodifica via ORS com validacao de cidade/estado.

  Combina consulta estruturada e texto contextualizado, priorizando
  resultados em nivel de rua/endereco sobre o centro da cidade.
  """
  componentes = partes or extrair_partes_endereco(endereco)
  todas_features: list[dict] = []
  erros: list[str] = []

  try:
    todas_features.extend(_buscar_ors_estruturado(componentes))
  except ValueError as erro:
    erros.append(f"ORS estruturado: {erro}")

  try:
    todas_features.extend(_buscar_ors_texto(componentes.texto_contextualizado))
  except ValueError as erro:
    erros.append(f"ORS texto: {erro}")

  resultado = _escolher_melhor_feature(todas_features, componentes)
  if resultado is not None:
    return resultado

  raise ValueError(" | ".join(erros) or f"Endereco nao encontrado (ORS): {endereco}")
