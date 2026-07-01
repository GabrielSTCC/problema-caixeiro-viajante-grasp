"""Estados e cidades para geocodificacao."""

ESTADOS_BR: list[str] = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
  "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
  "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

NOMES_ESTADOS: dict[str, str] = {
  "AC": "Acre", "AL": "Alagoas", "AP": "Amapa", "AM": "Amazonas",
  "BA": "Bahia", "CE": "Ceara", "DF": "Distrito Federal", "ES": "Espirito Santo",
  "GO": "Goias", "MA": "Maranhao", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
  "MG": "Minas Gerais", "PA": "Para", "PB": "Paraiba", "PR": "Parana",
  "PE": "Pernambuco", "PI": "Piaui", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
  "RS": "Rio Grande do Sul", "RO": "Rondonia", "RR": "Roraima", "SC": "Santa Catarina",
  "SP": "Sao Paulo", "SE": "Sergipe", "TO": "Tocantins",
}

CIDADES_POR_ESTADO: dict[str, list[str]] = {
  "CE": [
    "Russas",
    "Fortaleza",
    "Limoeiro do Norte",
    "Morada Nova",
    "Quixada",
    "Aracati",
    "Sobral",
    "Juazeiro do Norte",
  ],
  "RN": ["Natal", "Mossoro", "Parnamirim"],
  "PE": ["Recife", "Petrolina", "Caruaru"],
  "PB": ["Joao Pessoa", "Campina Grande"],
  "SP": ["Sao Paulo", "Campinas", "Santos"],
  "RJ": ["Rio de Janeiro", "Niteroi"],
}

CIDADE_PADRAO = "Russas"
ESTADO_PADRAO = "CE"
OPCAO_OUTRA_CIDADE = "(Outra cidade)"
