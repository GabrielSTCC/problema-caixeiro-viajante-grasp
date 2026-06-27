"""Mapa interativo Folium com rota GRASP."""

import folium
from folium import PolyLine

from dados.enderecos_russas import EnderecoRussas
from grasp.tipos import Tour


def criar_mapa_rota(
  enderecos: list[EnderecoRussas],
  tour: Tour,
  *,
  coordenadas_rota: list[list[float]] | None = None,
  segue_vias: bool = False,
) -> folium.Map:
  """Cria mapa Folium com marcadores numerados e polyline da rota."""
  if not enderecos:
    return folium.Map(location=[-4.94, -37.97], zoom_start=13)

  deposito = enderecos[0]
  centro_lat = sum(e["latitude"] for e in enderecos) / len(enderecos)
  centro_lng = sum(e["longitude"] for e in enderecos) / len(enderecos)

  mapa = folium.Map(
    location=[centro_lat, centro_lng],
    zoom_start=13,
    tiles="OpenStreetMap",
  )

  folium.Marker(
    location=[deposito["latitude"], deposito["longitude"]],
    popup=f"<b>{deposito['nome']}</b><br>{deposito['endereco']}",
    tooltip="Deposito (inicio/fim)",
    icon=folium.Icon(color="green", icon="home"),
  ).add_to(mapa)

  ordem_visita = {indice: pos + 1 for pos, indice in enumerate(tour)}

  for indice, item in enumerate(enderecos):
    if indice == 0:
      continue

    ordem = ordem_visita.get(indice, "?")
    folium.Marker(
      location=[item["latitude"], item["longitude"]],
      popup=f"<b>{ordem}. {item['nome']}</b><br>{item['endereco']}",
      tooltip=f"Parada {ordem}: {item['nome']}",
      icon=folium.DivIcon(
        html=(
          f'<div style="background:#2563eb;color:white;border-radius:50%;'
          f'width:28px;height:28px;display:flex;align-items:center;'
          f'justify-content:center;font-weight:bold;font-size:13px;'
          f'border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.3);">'
          f"{ordem}</div>"
        ),
        icon_size=(28, 28),
        icon_anchor=(14, 14),
      ),
    ).add_to(mapa)

  if tour and coordenadas_rota:
    PolyLine(
      coordenadas_rota,
      color="#2563eb",
      weight=5,
      opacity=0.85,
      dash_array=None if segue_vias else "8",
    ).add_to(mapa)

  return mapa
