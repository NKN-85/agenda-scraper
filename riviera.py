import requests
import re
from datetime import date
from bs4 import BeautifulSoup

from utils import HEADERS, get_url


def limpiar_texto(texto):
    return " ".join(texto.split()).strip()


def convertir_fecha_riviera(texto):
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
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    texto = limpiar_texto(texto).lower()

    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", texto)
    if not m:
        return None

    dia = int(m.group(1))
    mes = meses.get(m.group(2))
    anio = int(m.group(3))

    if not mes:
        return None

    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def sacar_riviera():
    url = "https://salariviera.com/conciertossalariviera/"
    lugar = "Sala La Riviera"

    eventos = []
    vistos = set()

    # 🔥 CAMBIO AQUÍ
    r = get_url(url, timeout=20)

    soup = BeautifulSoup(r.text, "html.parser")

    lineas = [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]

    i = 0
    while i < len(lineas):
        fecha_evento = convertir_fecha_riviera(lineas[i])

        if not fecha_evento:
            i += 1
            continue

        # El título suele estar justo 1 o 2 líneas antes porque aparece duplicado
        titulo = None
        for j in range(max(0, i - 3), i):
            candidata = lineas[j]
            if candidata and candidata not in {"CONCIERTOS", "COMPRAR ENTRADAS"}:
                titulo = candidata

        if not titulo:
            i += 1
            continue

        enlace = soup.find("a", string=lambda s: s and limpiar_texto(s) == titulo)
        url_evento = enlace.get("href", "").strip() if enlace else ""

        if not url_evento:
            i += 1
            continue

        if fecha_evento >= date.today():
            clave = (titulo.lower(), fecha_evento, url_evento)
            if clave not in vistos:
                vistos.add(clave)
                eventos.append([
                    titulo,
                    fecha_evento.strftime("%d/%m/%Y"),
                    lugar,
                    url_evento,
                    url
                ])

        i += 1

    return eventos