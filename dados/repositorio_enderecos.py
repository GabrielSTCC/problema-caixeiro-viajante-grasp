"""Persistencia de enderecos em SQLite."""

import sqlite3
from pathlib import Path
from typing import TypedDict

from dados.enderecos_russas import ENDERECOS_RUSSAS, EnderecoRussas

DB_PATH = Path(__file__).resolve().parent / "enderecos.db"


class EnderecoPersistido(TypedDict):
  """Endereco com identificador do banco."""

  id: int
  nome: str
  endereco: str
  latitude: float
  longitude: float


def _conectar() -> sqlite3.Connection:
  conexao = sqlite3.connect(DB_PATH)
  conexao.row_factory = sqlite3.Row
  return conexao


def _criar_tabela(conexao: sqlite3.Connection) -> None:
  conexao.execute("""
    CREATE TABLE IF NOT EXISTS enderecos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ordem INTEGER NOT NULL,
      nome TEXT NOT NULL,
      endereco TEXT NOT NULL,
      latitude REAL NOT NULL,
      longitude REAL NOT NULL,
      ativo INTEGER NOT NULL DEFAULT 1
    )
  """)


def _seed_inicial(conexao: sqlite3.Connection) -> None:
  total = conexao.execute(
    "SELECT COUNT(*) FROM enderecos WHERE ativo = 1"
  ).fetchone()[0]
  if total > 0:
    return

  for ordem, item in enumerate(ENDERECOS_RUSSAS):
    conexao.execute(
      """
      INSERT INTO enderecos (ordem, nome, endereco, latitude, longitude, ativo)
      VALUES (?, ?, ?, ?, ?, 1)
      """,
      (ordem, item["nome"], item["endereco"], item["latitude"], item["longitude"]),
    )


def inicializar_banco() -> None:
  """Cria tabela e popula dados iniciais se necessario."""
  with _conectar() as conexao:
    _criar_tabela(conexao)
    _seed_inicial(conexao)
    conexao.commit()


def _linha_para_endereco(linha: sqlite3.Row) -> EnderecoPersistido:
  return {
    "id": int(linha["id"]),
    "nome": str(linha["nome"]),
    "endereco": str(linha["endereco"]),
    "latitude": float(linha["latitude"]),
    "longitude": float(linha["longitude"]),
  }


def listar_ativos() -> list[EnderecoPersistido]:
  inicializar_banco()
  with _conectar() as conexao:
    linhas = conexao.execute(
      """
      SELECT id, nome, endereco, latitude, longitude
      FROM enderecos
      WHERE ativo = 1
      ORDER BY ordem ASC, id ASC
      """
    ).fetchall()
  return [_linha_para_endereco(linha) for linha in linhas]


def inserir(
  nome: str,
  endereco: str,
  latitude: float,
  longitude: float,
) -> EnderecoPersistido:
  inicializar_banco()
  with _conectar() as conexao:
    proxima_ordem = conexao.execute(
      "SELECT COALESCE(MAX(ordem), -1) + 1 FROM enderecos WHERE ativo = 1"
    ).fetchone()[0]
    cursor = conexao.execute(
      """
      INSERT INTO enderecos (ordem, nome, endereco, latitude, longitude, ativo)
      VALUES (?, ?, ?, ?, ?, 1)
      """,
      (proxima_ordem, nome, endereco, latitude, longitude),
    )
    conexao.commit()
    endereco_id = int(cursor.lastrowid)

  return obter_por_id(endereco_id)


def obter_por_id(endereco_id: int) -> EnderecoPersistido:
  inicializar_banco()
  with _conectar() as conexao:
    linha = conexao.execute(
      """
      SELECT id, nome, endereco, latitude, longitude
      FROM enderecos
      WHERE id = ? AND ativo = 1
      """,
      (endereco_id,),
    ).fetchone()

  if linha is None:
    raise ValueError(f"Endereco {endereco_id} nao encontrado.")

  return _linha_para_endereco(linha)


def atualizar(
  endereco_id: int,
  *,
  nome: str,
  endereco: str,
  latitude: float,
  longitude: float,
  ordem: int,
) -> EnderecoPersistido:
  inicializar_banco()
  with _conectar() as conexao:
    alterados = conexao.execute(
      """
      UPDATE enderecos
      SET ordem = ?, nome = ?, endereco = ?, latitude = ?, longitude = ?
      WHERE id = ? AND ativo = 1
      """,
      (ordem, nome, endereco, latitude, longitude, endereco_id),
    ).rowcount
    conexao.commit()

  if alterados == 0:
    raise ValueError(f"Endereco {endereco_id} nao encontrado para atualizacao.")

  return obter_por_id(endereco_id)


def excluir(endereco_id: int) -> None:
  inicializar_banco()
  with _conectar() as conexao:
    alterados = conexao.execute(
      "UPDATE enderecos SET ativo = 0 WHERE id = ? AND ativo = 1",
      (endereco_id,),
    ).rowcount
    conexao.commit()

  if alterados == 0:
    raise ValueError(f"Endereco {endereco_id} nao encontrado para exclusao.")


def _desativar_exceto(conexao: sqlite3.Connection, ids_manter: list[int]) -> None:
  if ids_manter:
    marcadores = ",".join("?" for _ in ids_manter)
    conexao.execute(
      f"UPDATE enderecos SET ativo = 0 WHERE ativo = 1 AND id NOT IN ({marcadores})",
      tuple(ids_manter),
    )
  else:
    conexao.execute("UPDATE enderecos SET ativo = 0 WHERE ativo = 1")


def sincronizar_lista(
  enderecos: list[EnderecoPersistido | EnderecoRussas],
) -> list[EnderecoPersistido]:
  """Persiste lista editada: atualiza, insere novos e exclui removidos."""
  inicializar_banco()
  ids_manter: list[int] = []

  with _conectar() as conexao:
    for ordem, item in enumerate(enderecos):
      nome = str(item["nome"]).strip()
      endereco = str(item["endereco"]).strip()
      latitude = float(item["latitude"])
      longitude = float(item["longitude"])
      endereco_id = item.get("id") if isinstance(item, dict) else None

      if endereco_id:
        conexao.execute(
          """
          UPDATE enderecos
          SET ordem = ?, nome = ?, endereco = ?, latitude = ?, longitude = ?, ativo = 1
          WHERE id = ?
          """,
          (ordem, nome, endereco, latitude, longitude, endereco_id),
        )
        ids_manter.append(int(endereco_id))
      else:
        proxima_ordem = ordem
        cursor = conexao.execute(
          """
          INSERT INTO enderecos (ordem, nome, endereco, latitude, longitude, ativo)
          VALUES (?, ?, ?, ?, ?, 1)
          """,
          (proxima_ordem, nome, endereco, latitude, longitude),
        )
        ids_manter.append(int(cursor.lastrowid))

    _desativar_exceto(conexao, ids_manter)
    conexao.commit()

  return listar_ativos()


def restaurar_padrao() -> list[EnderecoPersistido]:
  """Remove todos os enderecos e repovoa com o padrao Russas."""
  inicializar_banco()
  with _conectar() as conexao:
    conexao.execute("DELETE FROM enderecos")
    _seed_inicial(conexao)
    conexao.commit()
  return listar_ativos()


def para_endereco_grasp(endereco: EnderecoPersistido) -> EnderecoRussas:
  return {
    "nome": endereco["nome"],
    "endereco": endereco["endereco"],
    "latitude": endereco["latitude"],
    "longitude": endereco["longitude"],
  }


def listar_para_grasp() -> list[EnderecoRussas]:
  return [para_endereco_grasp(item) for item in listar_ativos()]
