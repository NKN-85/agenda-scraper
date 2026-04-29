import requests
import re
from datetime import date
from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento, construir_fecha


BASE_URL = "https://www.labtheclub.com/agenda/"
LUGAR = "LAB the Club"

MESES_CORTOS = {
    "ene": "enero",
    "feb": "febrero",
    "mar": "marzo",
    "abr": "abril",
    "may": "mayo",
    "jun": "junio",
    "jul": "julio",
    "ago": "agosto",
    "sep": "septiembre",
    "oct": "octubre",
    "nov": "noviembre",
    "dic": "diciembre",
}


# -------------------------
# HELPERS FECHA
# -------------------------

def mes_corto_a_largo(mes_txt):
    if not mes_txt:
        return None

    return MESES_CORTOS.get(limpiar_texto(mes_txt).lower()[:3])


def convertir_fecha_lab(fecha_txt):
    """
    Ejemplos:
    - 24 Abr
    - 01 May
    - 29 May
    """
    if not fecha_txt:
        return None

    t = limpiar_texto(fecha_txt).lower()
    m = re.fullmatch(r"(\d{1,2})\s+([a-záéíóú]{3,})", t)
    if not m:
        return None

    dia = int(m.group(1))
    mes_largo = mes_corto_a_largo(m.group(2))
    if not mes_largo:
        return None

    meses_num = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    }

    mes_num = meses_num.get(mes_largo)
    if not mes_num:
        return None

    hoy = date.today()
    anio = hoy.year

    # misma lógica que usas en otros scrapers
    if mes_num < hoy.month - 1:
        anio += 1

    return construir_fecha(dia, mes_largo, anio)


def es_fecha_corta_lab(texto):
    return bool(re.fullmatch(r"\d{1,2}\s+[A-Za-zÁÉÍÓÚáéíóú]{3,}", limpiar_texto(texto)))


def es_titulo_evento(texto):
    t = limpiar_texto(texto)

    if not t or len(t) < 3:
        return False

    basura = {
        "eventos",
        "todos los clubs",
        "info y reservas",
        "contacto",
        "whatsapp",
        "telefono",
        "teléfono",
        "cómo llegar",
        "parking gratuito",
        "metro de madrid",
        "tren cercanías y ave",
        "tren cercanias y ave",
        "estación autobuses",
        "estacion autobuses",
        "parada taxis",
    }

    if t.lower() in basura:
        return False

    if es_fecha_corta_lab(t):
        return False

    if t.lower().startswith("desde las"):
        return False

    return True


# -------------------------
# HELPERS URL
# -------------------------

def extraer_urls_utiles(soup):
    """
    Saca URLs de Entradas / NFT Tickets / Reservados
    en el mismo orden en el que aparecen en la agenda.
    Preferimos entradas/tickets; si no, reservados.
    """
    urls = []

    for linea in soup.select("a[href]"):
        texto = limpiar_texto(linea.get_text(" ", strip=True)).lower()
        href = (linea.get("href") or "").strip()

        if not href:
            continue

        if texto in {
            "entradas entradas",
            "entradas",
            "nft tickets nft tickets",
            "nft tickets",
        }:
            urls.append(href)

    # si por lo que sea no hubiera entradas, usamos reservados
    if urls:
        return urls

    for linea in soup.select("a[href]"):
        texto = limpiar_texto(linea.get_text(" ", strip=True)).lower()
        href = (linea.get("href") or "").strip()

        if not href:
            continue

        if texto in {
            "reservados reservados",
            "reservados",
        }:
            urls.append(href)

    return urls


# -------------------------
# SCRAPER
# -------------------------

def sacar_labtheclub():
    eventos = []
    vistos = set()
    session = requests.Session()

    respuesta = get_url(BASE_URL, session=session, timeout=20)
    soup = BeautifulSoup(respuesta.text, "html.parser")

    lineas = [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]

    urls_utiles = extraer_urls_utiles(soup)

    candidatos = []

    i = 0
    while i < len(lineas):
        linea = lineas[i]

        if not es_fecha_corta_lab(linea):
            i += 1
            continue

        fecha_txt = linea
        titulo = None

        # el título va después de la fecha
        j = i + 1
        while j < len(lineas):
            lj = lineas[j]

            # si aparece otra fecha antes de encontrar título, abortamos
            if es_fecha_corta_lab(lj):
                break

            if es_titulo_evento(lj):
                titulo = lj
                break

            j += 1

        if not titulo:
            i += 1
            continue

        fecha_evento = convertir_fecha_lab(fecha_txt)
        if not fecha_evento:
            i += 1
            continue

        candidatos.append((titulo, fecha_evento))
        i = j + 1

    total = min(len(candidatos), len(urls_utiles))

    for idx in range(total):
        titulo, fecha_evento = candidatos[idx]
        url_evento = urls_utiles[idx]

        agregar_evento(
            eventos,
            vistos,
            titulo,
            fecha_evento,
            LUGAR,
            url_evento,
            BASE_URL
        )

    return eventos