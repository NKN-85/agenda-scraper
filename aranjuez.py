import requests
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import HEADERS, agregar_evento, get_url


def limpiar_texto(texto):
    return " ".join(texto.split()).strip()


def convertir_fecha_aranjuez(texto):
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

    texto = limpiar_texto(texto).lower()
    anio_actual = date.today().year

    # Caso completo
    m = re.search(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        dia = int(m.group(1))
        mes = meses.get(m.group(2))
        anio = int(m.group(3))
        if mes:
            return date(anio, mes, dia)

    # Caso truncado
    m = re.search(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+20(?:\d{0,2}|\.{3})",
        texto
    )
    if m:
        dia = int(m.group(1))
        mes = meses.get(m.group(2))
        if mes:
            return date(anio_actual, mes, dia)

    # Respaldo
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", texto)
    if m:
        dia = int(m.group(1))
        mes = meses.get(m.group(2))
        anio = int(m.group(3))
        if mes:
            return date(anio, mes, dia)

    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+20(?:\d{0,2}|\.{3})", texto)
    if m:
        dia = int(m.group(1))
        mes = meses.get(m.group(2))
        if mes:
            return date(anio_actual, mes, dia)

    return None


def sacar_aranjuez():
    url = "https://teatroaranjuez.es/cartelera/"
    lugar = "Teatro Real Carlos III de Aranjuez"

    eventos = []
    vistos = set()

    # 🔥 CAMBIO AQUÍ
    respuesta = get_url(url, timeout=20)

    soup = BeautifulSoup(respuesta.text, "html.parser")

    bloques = soup.select("li.eg-cartelera-wrapper")

    for bloque in bloques:
        titulo_el = bloque.select_one(".eg-cartelera-element-36")
        fecha_el = bloque.select_one(".eg-cartelera-element-24")
        enlace_el = bloque.select_one("a.eg-cartelera-element-32[href]")

        if not titulo_el or not fecha_el or not enlace_el:
            continue

        titulo = limpiar_texto(titulo_el.get_text(" ", strip=True))
        fecha_texto = limpiar_texto(fecha_el.get_text(" ", strip=True))
        url_evento = urljoin(url, enlace_el["href"].strip())

        if not titulo or not fecha_texto or not url_evento:
            continue

        fecha_evento = convertir_fecha_aranjuez(fecha_texto)
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
            url
        )

    return eventos