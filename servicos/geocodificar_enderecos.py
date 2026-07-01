"""Geocodificacao em lote de enderecos."""

from dataclasses import dataclass, replace

from dados.enderecos_russas import EnderecoRussas, buscar_coordenadas_conhecidas
from infraestrutura.roteamento.cliente_google_geocode import (
  geocodificar_endereco_google,
  google_geocode_disponivel,
)
from infraestrutura.roteamento.cliente_nominatim import (
  geocodificar_bairro,
  geocodificar_endereco,
)
from infraestrutura.roteamento.cliente_ors_geocode import (
  PartesEndereco,
  extrair_partes_endereco,
  geocodificar_endereco_ors,
)
from servicos.contexto_geocodificacao import ContextoGeocodificacao, obter_contexto_geocodificacao


def _normalizar_comparacao(texto: str) -> str:
  import re
  import unicodedata

  sem_acento = unicodedata.normalize("NFKD", texto)
  sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
  return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _numero_confirmado(label: str, numero: str) -> bool:
  if not numero:
    return True
  return numero in _normalizar_comparacao(label)


def _resultado_preciso(label: str, partes: PartesEndereco) -> bool:
  """Indica se o label retornado refere-se a logradouro, nao apenas a cidade."""
  label_norm = _normalizar_comparacao(label)
  palavras = [
    palavra
    for palavra in _normalizar_comparacao(partes.logradouro).split()
    if len(palavra) > 2
  ]
  return bool(palavras) and any(palavra in label_norm for palavra in palavras)


def _classificar_precisao(
  label: str,
  partes: PartesEndereco,
  *,
  layer_ou_tipo: str = "",
) -> str:
  logradouro_ok = _resultado_preciso(label, partes)
  numero_ok = _numero_confirmado(label, partes.numero)
  endereco_especifico = layer_ou_tipo in {"address", "house", "building"}

  if logradouro_ok and partes.numero:
    if numero_ok or endereco_especifico:
      return "exato"
    return "aproximado"
  if logradouro_ok:
    return "exato"
  if partes.bairro and _normalizar_comparacao(partes.bairro) in _normalizar_comparacao(label):
    return "aproximado"
  return "aproximado"


@dataclass
class ResultadoGeocodificacao:
  indice: int
  nome: str
  endereco: str
  latitude: float
  longitude: float
  sucesso: bool
  fonte: str | None = None
  mensagem: str | None = None
  endereco_resolvido: str | None = None
  precisao: str | None = None


@dataclass(frozen=True)
class _CandidatoGeocode:
  latitude: float
  longitude: float
  fonte: str
  label: str
  precisao: str


def _tentar_apis(partes: PartesEndereco, endereco: str) -> _CandidatoGeocode | None:
  try:
    resultado = geocodificar_endereco_ors(endereco, partes=partes)
    return _CandidatoGeocode(
      latitude=resultado.latitude,
      longitude=resultado.longitude,
      fonte="ORS",
      label=resultado.label,
      precisao=_classificar_precisao(
        resultado.label,
        partes,
        layer_ou_tipo=resultado.layer,
      ),
    )
  except (ValueError, TimeoutError, OSError):
    pass

  try:
    resultado = geocodificar_endereco(
      endereco,
      cidade=partes.cidade,
      estado=partes.estado,
      partes=partes,
    )
    return _CandidatoGeocode(
      latitude=resultado.latitude,
      longitude=resultado.longitude,
      fonte="Nominatim",
      label=resultado.label,
      precisao=_classificar_precisao(
        resultado.label,
        partes,
        layer_ou_tipo=resultado.tipo,
      ),
    )
  except (ValueError, TimeoutError, OSError):
    return None


def _tentar_google(partes: PartesEndereco, endereco: str) -> _CandidatoGeocode | None:
  if not google_geocode_disponivel():
    return None

  try:
    resultado = geocodificar_endereco_google(endereco, partes=partes)
  except (ValueError, TimeoutError, OSError):
    return None

  if resultado.location_type in {"ROOFTOP", "RANGE_INTERPOLATED"}:
    precisao = "exato"
  else:
    precisao = _classificar_precisao(resultado.label, partes)

  return _CandidatoGeocode(
    latitude=resultado.latitude,
    longitude=resultado.longitude,
    fonte="Google",
    label=resultado.label,
    precisao=precisao,
  )


def _tentar_bairro(partes: PartesEndereco) -> _CandidatoGeocode | None:
  resultado = geocodificar_bairro(partes)
  if resultado is None:
    return None
  return _CandidatoGeocode(
    latitude=resultado.latitude,
    longitude=resultado.longitude,
    fonte="Nominatim",
    label=resultado.label,
    precisao="aproximado",
  )


def _tentar_cadastro(endereco: str) -> _CandidatoGeocode | None:
  coords = buscar_coordenadas_conhecidas(endereco)
  if coords is None:
    return None
  return _CandidatoGeocode(
    latitude=coords[0],
    longitude=coords[1],
    fonte="cadastro padrao",
    label=endereco,
    precisao="cadastro",
  )


def _geocodificar_um(
  endereco: str,
  *,
  contexto: ContextoGeocodificacao | None = None,
) -> tuple[float, float, str, str, str]:
  """Tenta ORS, Nominatim, fallbacks e cadastro. Retorna lat, lng, fonte, label, precisao."""
  ctx = contexto or obter_contexto_geocodificacao()
  partes = extrair_partes_endereco(endereco, cidade=ctx.cidade, estado=ctx.estado)

  candidato_cadastro = _tentar_cadastro(endereco)
  if candidato_cadastro is not None:
    return (
      candidato_cadastro.latitude,
      candidato_cadastro.longitude,
      candidato_cadastro.fonte,
      candidato_cadastro.label,
      candidato_cadastro.precisao,
    )

  etapas: list[tuple[str, PartesEndereco]] = [
    ("completo", partes),
    ("sem_numero", replace(partes, numero="")),
    ("so_logradouro", replace(partes, numero="", bairro="")),
  ]

  for nome_etapa, variantes in etapas:
    candidato = _tentar_apis(variantes, endereco)
    if candidato is None:
      continue

    if (
      nome_etapa == "completo"
      and partes.numero
      and not _numero_confirmado(candidato.label, partes.numero)
    ):
      candidato_google = _tentar_google(partes, endereco)
      if candidato_google is not None:
        candidato = candidato_google

    return (
      candidato.latitude,
      candidato.longitude,
      candidato.fonte,
      candidato.label,
      candidato.precisao,
    )

  candidato_bairro = _tentar_bairro(partes)
  if candidato_bairro is not None:
    return (
      candidato_bairro.latitude,
      candidato_bairro.longitude,
      candidato_bairro.fonte,
      candidato_bairro.label,
      candidato_bairro.precisao,
    )

  raise ValueError(
    "Endereco nao localizado com precisao suficiente. Coordenadas mantidas."
  )


COORDENADAS_PADRAO = (-4.94, -37.97)
ENDERECOS_GENERICOS = {"", "novo endereco"}


def precisa_geocodificar(item: EnderecoRussas) -> bool:
  lat_padrao, lng_padrao = COORDENADAS_PADRAO
  lat = round(item["latitude"], 2)
  lng = round(item["longitude"], 2)
  endereco_generico = item["endereco"].strip().lower() in ENDERECOS_GENERICOS
  return endereco_generico or (lat == lat_padrao and lng == lng_padrao)


def _formatar_badge(fonte: str, precisao: str) -> str:
  if precisao == "cadastro":
    return f"via {fonte}"
  if fonte == "Google" and precisao == "exato":
    return "via Google (endereco)"
  if precisao == "exato":
    return f"via {fonte} (rua)"
  if precisao == "aproximado":
    return f"via {fonte} (bairro/logradouro)"
  return f"via {fonte}"


def geocodificar_se_necessario(
  item: EnderecoRussas,
  *,
  contexto: ContextoGeocodificacao | None = None,
) -> tuple[EnderecoRussas, ResultadoGeocodificacao | None]:
  """Geocodifica um endereco se ainda tiver coordenadas padrao ou endereco generico."""
  if not precisa_geocodificar(item) and item["endereco"].strip().lower() not in ENDERECOS_GENERICOS:
    return item, None

  if item["endereco"].strip().lower() in ENDERECOS_GENERICOS:
    return item, ResultadoGeocodificacao(
      indice=-1,
      nome=item["nome"],
      endereco=item["endereco"],
      latitude=item["latitude"],
      longitude=item["longitude"],
      sucesso=False,
      mensagem="Informe o endereco completo antes de geocodificar.",
    )

  try:
    lat, lng, fonte, label, precisao = _geocodificar_um(item["endereco"], contexto=contexto)
    atualizado = dict(item)
    atualizado["latitude"] = lat
    atualizado["longitude"] = lng
    return atualizado, ResultadoGeocodificacao(
      indice=-1,
      nome=item["nome"],
      endereco=item["endereco"],
      latitude=lat,
      longitude=lng,
      sucesso=True,
      fonte=fonte,
      endereco_resolvido=label,
      precisao=precisao,
    )
  except ValueError as erro:
    return item, ResultadoGeocodificacao(
      indice=-1,
      nome=item["nome"],
      endereco=item["endereco"],
      latitude=item["latitude"],
      longitude=item["longitude"],
      sucesso=False,
      mensagem=str(erro),
    )


def geocodificar_pendentes(
  enderecos: list[EnderecoRussas],
  *,
  enderecos_alterados: list[str] | None = None,
  contexto: ContextoGeocodificacao | None = None,
) -> tuple[list[EnderecoRussas], list[ResultadoGeocodificacao]]:
  """Geocodifica linhas pendentes ou com endereco alterado."""
  atualizados: list[EnderecoRussas] = [dict(item) for item in enderecos]
  relatorio: list[ResultadoGeocodificacao] = []
  alterados = set(enderecos_alterados or [])

  for indice, item in enumerate(atualizados):
    endereco_texto = item["endereco"].strip()
    deve_geocodificar = (
      precisa_geocodificar(item)
      or endereco_texto in alterados
    )
    if not deve_geocodificar or endereco_texto.lower() in ENDERECOS_GENERICOS:
      continue

    try:
      lat, lng, fonte, label, precisao = _geocodificar_um(endereco_texto, contexto=contexto)
      atualizados[indice]["latitude"] = lat
      atualizados[indice]["longitude"] = lng
      relatorio.append(ResultadoGeocodificacao(
        indice=indice,
        nome=item["nome"],
        endereco=endereco_texto,
        latitude=lat,
        longitude=lng,
        sucesso=True,
        fonte=fonte,
        endereco_resolvido=label,
        precisao=precisao,
      ))
    except ValueError as erro:
      relatorio.append(ResultadoGeocodificacao(
        indice=indice,
        nome=item["nome"],
        endereco=endereco_texto,
        latitude=item["latitude"],
        longitude=item["longitude"],
        sucesso=False,
        mensagem=str(erro),
      ))

  return atualizados, relatorio


def geocodificar_lista(
  enderecos: list[EnderecoRussas],
  *,
  indices: list[int] | None = None,
  contexto: ContextoGeocodificacao | None = None,
) -> tuple[list[EnderecoRussas], list[ResultadoGeocodificacao]]:
  """
  Geocodifica enderecos e retorna lista atualizada + relatorio por linha.

  Se indices for None, processa todas as linhas.
  """
  atualizados: list[EnderecoRussas] = [dict(item) for item in enderecos]
  relatorio: list[ResultadoGeocodificacao] = []
  alvo = indices if indices is not None else list(range(len(enderecos)))

  for indice in alvo:
    if indice < 0 or indice >= len(atualizados):
      continue

    item = atualizados[indice]
    try:
      lat, lng, fonte, label, precisao = _geocodificar_um(item["endereco"], contexto=contexto)
      atualizados[indice]["latitude"] = lat
      atualizados[indice]["longitude"] = lng
      relatorio.append(ResultadoGeocodificacao(
        indice=indice,
        nome=item["nome"],
        endereco=item["endereco"],
        latitude=lat,
        longitude=lng,
        sucesso=True,
        fonte=fonte,
        endereco_resolvido=label,
        precisao=precisao,
      ))
    except ValueError as erro:
      relatorio.append(ResultadoGeocodificacao(
        indice=indice,
        nome=item["nome"],
        endereco=item["endereco"],
        latitude=item["latitude"],
        longitude=item["longitude"],
        sucesso=False,
        mensagem=str(erro),
      ))

  return atualizados, relatorio


def detectar_coordenadas_duplicadas(
  enderecos: list[EnderecoRussas],
) -> list[tuple[tuple[float, float], list[str]]]:
  """Agrupa enderecos distintos que compartilham a mesma coordenada arredondada."""
  grupos: dict[tuple[float, float], list[str]] = {}
  for item in enderecos:
    chave = (round(item["latitude"], 5), round(item["longitude"], 5))
    grupos.setdefault(chave, []).append(item["nome"])

  return [(coords, nomes) for coords, nomes in grupos.items() if len(nomes) > 1]
