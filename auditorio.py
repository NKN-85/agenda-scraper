import requests
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import HEADERS, agregar_evento, get_url


def convertir_fecha_auditorio(texto):
    meses = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    texto = " ".join(texto.split()).strip().lower()

    # Prioridad 1: formato ISO presente en la página
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        anio = int(m.group(1))
        mes = int(m.group(2))
        dia = int(m.group(3))
        try:
            return date(anio, mes, dia)
        except ValueError:
            return None

    # Prioridad 2: formato español
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", texto)
    if m:
        dia = int(m.group(1))
        mes = meses.get(m.group(2))
        anio = int(m.group(3))
        if mes:
            try:
                return date(anio, mes, dia)
            except ValueError:
                return None

    return None


def sacar_auditorio():
    url_base = "https://auditorionacional.inaem.gob.es/es/programacion"
    eventos = []
    vistos = set()

    session = requests.Session()

    # La paginación va de 12 en 12
    for offset in range(0, 240, 12):
        if offset == 0:
            url = url_base
        else:
            url = f"{url_base}?b_start:int={offset}"

        # 🔥 CAMBIO AQUÍ
        resp = get_url(url, session=session, timeout=20)

        soup = BeautifulSoup(resp.text, "html.parser")

        enlaces = soup.select("h3.eventitem__title a.eventitem__link")

        if not enlaces:
            break

        encontrados_en_pagina = 0

        for a in enlaces:
            titulo = a.get_text(" ", strip=True)
            href = a.get("href", "").strip()

            if not titulo or not href:
                continue

            url_evento = urljoin(url_base, href)

            # Subimos al bloque más estable posible
            contenedor = a.find_parent("li")
            if not contenedor:
                contenedor = a.find_parent("article")
            if not contenedor:
                continue

            lugar_el = contenedor.select_one("p.location span")
            lugar = lugar_el.get_text(" ", strip=True) if lugar_el else "Auditorio Nacional"

            texto_bloque = contenedor.get_text(" ", strip=True)
            fecha_evento = convertir_fecha_auditorio(texto_bloque)

            if not fecha_evento:
                continue

            if fecha_evento < date.today():
                continue

            agregar_evento(
                eventos,
                vistos,
                titulo,
                fecha_evento,
                lugar,
                url_evento,
                url_base
            )
            encontrados_en_pagina += 1

        if encontrados_en_pagina == 0 and offset > 0:
            break

    return eventos