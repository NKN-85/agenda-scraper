import re
import requests
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url, limpiar_texto, construir_fecha


BASE_URL = "https://salavillanos.es/agenda/"
LUGAR = "Sala Villanos"

MESES = {
    "jan": "enero",
    "feb": "febrero",
    "mar": "marzo",
    "apr": "abril",
    "may": "mayo",
    "jun": "junio",
    "jul": "julio",
    "aug": "agosto",
    "sep": "septiembre",
    "oct": "octubre",
    "nov": "noviembre",
    "dec": "diciembre",
}


def _inferir_anio(dia, mes_txt):
    hoy = date.today()
    fecha = construir_fecha(dia, mes_txt, hoy.year)
    if not fecha:
        return None

    if fecha.month < hoy.month - 1:
        return hoy.year + 1

    return hoy.year


def _parsear_fecha_linea(texto):
    t = limpiar_texto(texto)

    m = re.match(
        r"^(\d{1,2})\s+([A-Za-z]{3})\s+\d{1,2}:\d{2}H\b",
        t,
        re.I,
    )
    if not m:
        return None

    dia = int(m.group(1))
    mes_abrev = m.group(2).lower()
    mes_txt = MESES.get(mes_abrev)

    if not mes_txt:
        return None

    anio = _inferir_anio(dia, mes_txt)
    if not anio:
        return None

    fecha = construir_fecha(dia, mes_txt, anio)
    return fecha


def _limpiar_titulo_evento(texto):
    t = limpiar_texto(texto)

    t = re.sub(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{1,2}:\d{2}H\s+", "", t, flags=re.I)
    t = re.sub(
        r"^(Concierto|Club|Momentos Alhambra|Villanos del Jazz)\s+",
        "",
        t,
        flags=re.I,
    )

    generos = [
        "Pop", "Rock", "Jazz", "Latin", "Urban", "World Music & Folk",
        "Electronic", "Flamenco", "Funk & disco", "Soul & R&B",
        "Hip Hop & Rap", "Infantil", "Neoclásico", "Clasico", "Afro",
    ]

    cambiado = True
    while cambiado:
        cambiado = False
        for genero in generos:
            patron = rf"^{re.escape(genero)}\s+"
            nuevo = re.sub(patron, "", t, flags=re.I)
            if nuevo != t:
                t = nuevo
                cambiado = True

    t = re.sub(r"\s+", " ", t).strip(" -–·")
    return t


def _es_url_evento_valida(url):
    if not url:
        return False

    u = url.lower().strip()
    if not u.startswith("http"):
        return False

    if u.rstrip("/") == BASE_URL.rstrip("/"):
        return False

    return "salavillanos.es" in u


def _es_linea_evento(texto):
    t = limpiar_texto(texto)

    return bool(
        re.match(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{1,2}:\d{2}H\b", t, re.I)
    )


def sacar_salavillanos():
    eventos = []
    vistos = set()
    session = requests.Session()

    respuesta = get_url(BASE_URL, session=session, timeout=20)
    if not respuesta:
        return []

    soup = BeautifulSoup(respuesta.text, "html.parser")

    for a in soup.find_all("a", href=True):
        texto = limpiar_texto(a.get_text(" ", strip=True))
        href = urljoin(BASE_URL, a["href"].strip())

        if not _es_linea_evento(texto):
            continue

        if not _es_url_evento_valida(href):
            continue

        fecha = _parsear_fecha_linea(texto)
        if not fecha:
            continue

        titulo = _limpiar_titulo_evento(texto)
        if not titulo:
            continue

        info_fecha = {
            "tipo_fecha": "unica",
            "fecha": fecha.isoformat(),
            "texto_fecha_original": texto,
        }

        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=titulo,
            fecha_evento=fecha.isoformat(),
            lugar=LUGAR,
            url_evento=href,
            fuente=BASE_URL,
            info_fecha=info_fecha,
        )

    return eventos