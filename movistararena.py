import requests
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import HEADERS, agregar_evento
from helpers.texto import normalizar_texto


def convertir_fecha_movistararena(texto):
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

    m = re.search(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d{1,2})\s+([a-záéíóú]+)\s+(\d{4})",
        texto
    )
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


def obtener_lugar_movistararena(texto):
    texto_norm = normalizar_texto(texto).lower()

    if "la sala movistar" in texto_norm:
        return "La Sala del Movistar Arena"

    return "Movistar Arena"


def limpiar_titulo_movistararena(texto):
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"<br\s*/?>", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def sacar_movistararena():
    url = "https://www.movistararena.es/calendario"
    eventos = []
    vistos = set()

    respuesta = requests.get(url, headers=HEADERS, verify=False, timeout=20)
    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")

    bloques = soup.select("div.product-thumb")

    for bloque in bloques:
        enlace_el = bloque.select_one('header.product-header a[href*="informacion?evento="]')
        categoria_el = bloque.select_one("ul.product-price-list span.product-price")
        titulo_el = bloque.select_one("div.product-inner h5")
        fecha_el = bloque.select_one("div.product-inner h2.product-title")

        if not enlace_el or not categoria_el or not titulo_el or not fecha_el:
            continue

        href = enlace_el.get("href", "").strip()
        if not href:
            continue

        url_evento = urljoin(url, href)

        categoria = categoria_el.get_text(" ", strip=True)
        lugar = obtener_lugar_movistararena(categoria)

        titulo = limpiar_titulo_movistararena(titulo_el.get_text(" ", strip=True))
        fecha_texto = fecha_el.get_text(" ", strip=True)

        if not titulo or not fecha_texto:
            continue

        fecha_evento = convertir_fecha_movistararena(fecha_texto)
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