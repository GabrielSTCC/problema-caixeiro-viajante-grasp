"""Testes de geocodificacao."""

import math
import os
import unittest
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from dados.enderecos_russas import ENDERECOS_RUSSAS, buscar_coordenadas_conhecidas
from infraestrutura.roteamento.cliente_ors_geocode import (
  PartesEndereco,
  _escolher_melhor_feature,
  extrair_partes_endereco,
)
from servicos.contexto_geocodificacao import ContextoGeocodificacao
from servicos.geocodificar_enderecos import (
  _classificar_precisao,
  _geocodificar_um,
  _resultado_preciso,
  detectar_coordenadas_duplicadas,
)


def distancia_metros(
  lat1: float,
  lng1: float,
  lat2: float,
  lng2: float,
) -> float:
  dlat = math.radians(lat2 - lat1)
  dlng = math.radians(lng2 - lng1)
  a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
    math.radians(lat2)
  ) * math.sin(dlng / 2) ** 2
  return 6371000 * 2 * math.asin(math.sqrt(a))


class TestParserEndereco(unittest.TestCase):
  def test_extrai_logradouro_numero_bairro(self) -> None:
    partes = extrair_partes_endereco(
      "R. Maciel Pereira, 1054 - Vila Matoso",
      cidade="Russas",
      estado="CE",
    )
    self.assertEqual(partes.logradouro, "Rua Maciel Pereira")
    self.assertEqual(partes.numero, "1054")
    self.assertEqual(partes.bairro, "Vila Matoso")
    self.assertEqual(partes.street, "Rua Maciel Pereira, 1054")

  def test_texto_contextualizado_inclui_cidade(self) -> None:
    partes = extrair_partes_endereco(
      "Av. Dom Lino, 656 - Centro",
      cidade="Russas",
      estado="CE",
    )
    self.assertIn("Russas", partes.texto_contextualizado)
    self.assertIn("CE", partes.texto_contextualizado)
    self.assertIn("656", partes.texto_contextualizado)

  def test_normaliza_tv_para_travessa(self) -> None:
    partes = extrair_partes_endereco(
      "Tv. Carlos Pontes, 88 - Centro",
      cidade="Russas",
      estado="CE",
    )
    self.assertEqual(partes.logradouro, "Travessa Carlos Pontes")
    self.assertEqual(partes.numero, "88")

  def test_resultado_preciso_rejeita_apenas_cidade(self) -> None:
    partes = extrair_partes_endereco(
      "Av. Dom Lino, 656 - Centro",
      cidade="Russas",
      estado="CE",
    )
    self.assertFalse(_resultado_preciso("Russas, CE, Brazil", partes))
    self.assertTrue(
      _resultado_preciso("Avenida Dom Lino, Russas, CE, Brazil", partes)
    )


class TestClassificacaoPrecisao(unittest.TestCase):
  def test_rua_sem_numero_no_label_e_aproximado(self) -> None:
    partes = extrair_partes_endereco(
      "Tv. Agostinho Goncalves, 1701 - Vila Matoso",
      cidade="Russas",
      estado="CE",
    )
    label = "Travessa Professor Agostinho Goncalves Santiago, Russas, CE, Brazil"
    self.assertEqual(
      _classificar_precisao(label, partes, layer_ou_tipo="street"),
      "aproximado",
    )

  def test_rua_com_numero_no_label_e_exato(self) -> None:
    partes = extrair_partes_endereco(
      "Av. Dom Lino, 656 - Centro",
      cidade="Russas",
      estado="CE",
    )
    label = "Avenida Dom Lino, 656, Russas, CE, Brazil"
    self.assertEqual(_classificar_precisao(label, partes), "exato")


class TestRejeicaoLocality(unittest.TestCase):
  def test_rejeita_centro_da_cidade_ors(self) -> None:
    partes = extrair_partes_endereco(
      "Av. Dom Lino, 656 - Centro",
      cidade="Russas",
      estado="CE",
    )
    feature = {
      "geometry": {"coordinates": [-37.977681, -4.935484]},
      "properties": {
        "layer": "locality",
        "label": "Russas, CE, Brazil",
        "locality": "Russas",
        "region": "Ceara",
        "region_a": "CE",
        "confidence": 0.6,
      },
    }
    self.assertIsNone(_escolher_melhor_feature([feature], partes))


class TestCadastroConhecido(unittest.TestCase):
  def test_buscar_coordenadas_distintas(self) -> None:
    enderecos = [
      "Av. Dom Lino, 656 - Centro",
      "R. Gov. Raul Barbosa, 521 - Centro",
      "R. Jose Matoso Sobrinho, 146 - Tabuleiro da Vaquejada",
    ]
    coords = [buscar_coordenadas_conhecidas(end) for end in enderecos]
    self.assertTrue(all(c is not None for c in coords))
    assert coords[0] and coords[1] and coords[2]
    self.assertNotEqual(coords[0], coords[1])
    self.assertNotEqual(coords[1], coords[2])

  def test_detectar_duplicatas(self) -> None:
    enderecos = [
      {"nome": "A", "endereco": "x", "latitude": -4.935484, "longitude": -37.977681},
      {"nome": "B", "endereco": "y", "latitude": -4.935484, "longitude": -37.977681},
      {"nome": "C", "endereco": "z", "latitude": -4.94, "longitude": -37.97},
    ]
    duplicatas = detectar_coordenadas_duplicadas(enderecos)
    self.assertEqual(len(duplicatas), 1)
    self.assertEqual(set(duplicatas[0][1]), {"A", "B"})


@unittest.skipUnless(os.getenv("ORS_API_KEY"), "Requer ORS_API_KEY para testes de integracao")
class TestGeocodificacaoRussas(unittest.TestCase):
  contexto = ContextoGeocodificacao(cidade="Russas", estado="CE")

  def test_nao_geocodifica_em_rio_de_janeiro(self) -> None:
    lat, lng, _, _, _ = _geocodificar_um(
      "Av. Dom Lino, 656 - Centro",
      contexto=self.contexto,
    )
    self.assertGreater(lat, -6.0, "Latitude indica cidade fora do Ceara")
    self.assertGreater(lng, -39.0, "Longitude indica cidade fora de Russas")

  def test_enderecos_seed_nao_sao_todos_iguais(self) -> None:
    coords: list[tuple[float, float]] = []
    for item in ENDERECOS_RUSSAS[:4]:
      lat, lng, fonte, _, _ = _geocodificar_um(
        item["endereco"],
        contexto=self.contexto,
      )
      coords.append((lat, lng))
      self.assertIn(fonte, {"ORS", "Nominatim", "cadastro padrao", "Google"})
    self.assertGreater(len(set(coords)), 1, "Enderecos distintos com mesma coordenada")

  def test_enderecos_russas_dentro_da_regiao(self) -> None:
    for item in ENDERECOS_RUSSAS[:3]:
      lat, lng, _, _, _ = _geocodificar_um(
        item["endereco"],
        contexto=self.contexto,
      )
      self.assertGreater(lat, -5.2, f"{item['nome']} muito ao sul")
      self.assertLess(lat, -4.8, f"{item['nome']} muito ao norte")
      self.assertGreater(lng, -38.2, f"{item['nome']} muito a oeste")
      self.assertLess(lng, -37.8, f"{item['nome']} muito a leste")

  def test_deposito_proximo_ao_seed(self) -> None:
    seed = ENDERECOS_RUSSAS[0]
    lat, lng, _, _, _ = _geocodificar_um(seed["endereco"], contexto=self.contexto)
    erro = distancia_metros(seed["latitude"], seed["longitude"], lat, lng)
    self.assertLess(
      erro,
      2000,
      f"Deposito geocodificado a {erro:.0f}m do seed (limite OSM)",
    )


ENDERECO_DEPOSITO_AGOSTINHO = (
  "Tv. Agostinho Goncalves, 1701 - Vila Matoso, Russas - CE, 62900-000"
)
COORDS_DEPOSITO_REFERENCIA = (-4.949790595863034, -37.96705547067877)


@unittest.skipUnless(
  os.getenv("GOOGLE_MAPS_API_KEY"),
  "Requer GOOGLE_MAPS_API_KEY para testes de integracao Google",
)
class TestGeocodificacaoGoogle(unittest.TestCase):
  contexto = ContextoGeocodificacao(cidade="Russas", estado="CE")

  def test_deposito_agostinho_goncalves_via_google(self) -> None:
    lat, lng, fonte, _, precisao = _geocodificar_um(
      ENDERECO_DEPOSITO_AGOSTINHO,
      contexto=self.contexto,
    )
    self.assertEqual(fonte, "Google")
    self.assertEqual(precisao, "exato")
    erro = distancia_metros(
      lat,
      lng,
      COORDS_DEPOSITO_REFERENCIA[0],
      COORDS_DEPOSITO_REFERENCIA[1],
    )
    self.assertLess(
      erro,
      20,
      f"Deposito geocodificado a {erro:.0f}m da referencia Google Maps",
    )


if __name__ == "__main__":
  unittest.main()
