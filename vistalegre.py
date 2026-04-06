import requests
from bs4 import BeautifulSoup
from datetime import date

from utils import HEADERS, convertir_fecha_vistalegre, get_url


def sacar_vistalegre():
    url = "https://www.palaciovistalegre.com/events/"
    eventos = []
    vistos = set()

    # 🔥 CAMBIO AQUÍ
    respuesta = get_url(url, timeout=15)

    soup = BeautifulSoup(respuesta.text, "html.parser")

    bloques = soup.find_all("div", class_="tribe-events-calendar-list__event-details")

    for bloque in bloques:
        titulo_el = bloque.find("a", class_="tribe-events-calendar-list__event-title-link")
        fecha_el = bloque.find("time", class_="tribe-events-calendar-list__event-datetime")
        venue_el = bloque.find("span", class_="tribe-events-calendar-list__event-venue-title")

        if not titulo_el or not fecha_el:
            continue

        titulo = titulo_el.get_text(" ", strip=True)
        url_evento = titulo_el["href"].strip()
        fecha_texto = fecha_el.get_text(" ", strip=True)
        lugar = venue_el.get_text(" ", strip=True) if venue_el else "Palacio Vistalegre"

        if not titulo or not fecha_texto:
            continue

        fecha_evento = convertir_fecha_vistalegre(fecha_texto)

        if fecha_evento and fecha_evento >= date.today():
            clave = (fecha_evento, titulo, "Palacio Vistalegre")

            if clave not in vistos:
                vistos.add(clave)

                eventos.append([
                    titulo,
                    fecha_evento.strftime("%d/%m/%Y"),
                    lugar,
                    url_evento,
                    url
                ])

    return eventos