"""
Problema do Caixeiro Viajante (PCV) resolvido com GRASP e busca local 2-opt.

Caso de estudo: rotas de entrega em Russas-CE com distancias reais (OpenRouteService).

Execute:
  py principal.py

Requisitos:
  1. py -m pip install -r requirements.txt
  2. Copie .env.example para .env e preencha ORS_API_KEY
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from dados.enderecos_russas import ENDERECOS_RUSSAS, EnderecoRussas
from servicos.executar_otimizacao import executar_otimizacao, formatar_ordem_visita

load_dotenv(Path(__file__).resolve().parent / ".env")

ALPHA = float(os.getenv("GRASP_ALPHA", "0.3"))
MAX_ITERACOES = int(os.getenv("GRASP_MAX_ITERATIONS", "100"))


def imprimir_enderecos(enderecos: list[EnderecoRussas]) -> None:
  print("Enderecos cadastrados:")
  for indice, item in enumerate(enderecos):
    print(f"  [{indice}] {item['nome']}: {item['endereco']}")
    print(f"       lat={item['latitude']:.6f}, lng={item['longitude']:.6f}")
  print()


def imprimir_matriz_custos(rotulo: str, matriz: list[list[float]]) -> None:
  print(f"{rotulo}:")
  for linha in matriz:
    print("  [" + ", ".join(f"{v:.3f}" for v in linha) + "]")


def principal() -> None:
  imprimir_enderecos(ENDERECOS_RUSSAS)

  if os.getenv("ORS_API_KEY", "").strip():
    print("Calculando matriz ORS (rotas reais)...")
  else:
    print("ORS_API_KEY ausente — usando Haversine (aproximado)...")

  resultado_otimizacao = executar_otimizacao(
    ENDERECOS_RUSSAS,
    alpha=ALPHA,
    max_iteracoes=MAX_ITERACOES,
    usar_ors=bool(os.getenv("ORS_API_KEY", "").strip()),
    retornar_ao_deposito=True,
  )

  if resultado_otimizacao.aviso_matriz:
    print(f"Aviso: {resultado_otimizacao.aviso_matriz}")

  rotulo_matriz = (
    "Matriz ORS (rotas reais, km)"
    if resultado_otimizacao.tipo_matriz == "ors"
    else "Matriz Haversine (aproximada, km)"
  )
  imprimir_matriz_custos(rotulo_matriz, resultado_otimizacao.matriz_custos)
  print()

  if resultado_otimizacao.melhorias:
    print(f"\nGRASP - {MAX_ITERACOES} iteracoes (alpha={ALPHA})")
    print("-" * 60)
    for melhoria in resultado_otimizacao.melhorias:
      print(
        f"Iteracao {melhoria.iteracao}: novo melhor custo = "
        f"{melhoria.custo_km:.3f} km, tour = {melhoria.tour}"
      )

  resultado = resultado_otimizacao

  print("\n" + "=" * 60)
  print(f"Melhor tour (indices): {resultado.tour}")
  print(f"Custo total: {resultado.custo_km:.3f} km (inclui retorno ao deposito)")
  print(f"Iteracoes executadas: {resultado.iteracoes}")
  print("\nOrdem de visita:")
  for ordem, indice in enumerate(resultado.tour):
    item = ENDERECOS_RUSSAS[indice]
    print(f"  {ordem + 1}. [{indice}] {item['nome']} - {item['endereco']}")
  if resultado.tour:
    print(f"  {len(resultado.tour) + 1}. [0] {ENDERECOS_RUSSAS[0]['nome']} - retorno")
  print("\nResumo:", formatar_ordem_visita(resultado.tour, ENDERECOS_RUSSAS))
  print("=" * 60)


if __name__ == "__main__":
  try:
    principal()
  except ValueError as erro:
    print(erro)
    raise SystemExit(1) from erro
