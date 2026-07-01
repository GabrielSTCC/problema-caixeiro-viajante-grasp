"""Helpers de fingerprint e invalidacao de resultado."""

import hashlib
import json

from dados.enderecos_russas import EnderecoRussas


def fingerprint_enderecos(enderecos: list[EnderecoRussas]) -> str:
  """Hash estavel da lista atual de enderecos."""
  payload = [
    {
      "nome": e["nome"],
      "endereco": e["endereco"],
      "latitude": round(e["latitude"], 6),
      "longitude": round(e["longitude"], 6),
    }
    for e in enderecos
  ]
  texto = json.dumps(payload, sort_keys=True, ensure_ascii=False)
  return hashlib.sha256(texto.encode("utf-8")).hexdigest()
