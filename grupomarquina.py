import requests
import re
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento


BASE_URL = "https://www.grupomarquina.es/"


# -------------------------
# HELPERS FECHA
# -------------------------

def parsear_rango_marquina(texto):
    """
    Formatos:
    - 29/05/2026 - 29/05/2026
    - 15/04/2026 - 24/05/2026
    - 01/09/2025 - 31/05/2026
    """
    if not texto:
        return None

    t = limpiar_texto(texto)

    m = re.fullmatch(
        r"(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4})",
        t
    )
    if not m:
        return None

    try:
        fi = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        ff = date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
    except Exception:
        return None

    if fi == ff:
        return {
            "tipo_fecha": "unica",
            "fecha": fi.isoformat(),
            "fecha_inicio": fi.isoformat(),
            "fecha_fin": ff.isoformat(),
            "fechas_funcion": [fi.isoformat()],
            "dias_semana": [],
            "texto_fecha_original": t,
        }

    return {
        "tipo_fecha": "rango",
        "fecha": fi.isoformat(),
        "fecha_inicio": fi.isoformat(),
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": t,
    }


# -------------------------
# PORTADA
# -------------------------

def extraer_bloques_portada(soup):
    """
    La home repite contenido arriba y abajo.
    Nos quedamos con bloques que tengan:
    - date_range dd/mm/yyyy - dd/mm/yyyy
    - Teatro Marquina o Teatro Príncipe Gran Vía
    - un h3 con título
    """
    bloques_validos = []

    for div in soup.find_all("div"):
        texto = limpiar_texto(div.get_text(" ", strip=True))
        if not texto:
            continue

        if not re.search(r"\b\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}\b", texto):
            continue

        texto_low = texto.lower()
        if (
            "teatro marquina" not in texto_low
            and "teatro principe gran via" not in texto_low
            and "teatro príncipe gran vía" not in texto_low
        ):
            continue

        if not div.find("h3"):
            continue

        bloques_validos.append(div)

    return bloques_validos


def extraer_titulo_desde_bloque(bloque):
    h3 = bloque.find("h3")
    if not h3:
        return None

    titulo = limpiar_texto(h3.get_text(" ", strip=True))
    return titulo or None


def extraer_lugar_desde_bloque(bloque):
    texto = limpiar_texto(bloque.get_text(" ", strip=True)).lower()

    if "teatro príncipe gran vía" in texto or "teatro principe gran via" in texto:
        return "Teatro Príncipe Gran Vía"

    if "teatro marquina" in texto:
        return "Teatro Marquina"

    return None


def extraer_url_ficha_desde_bloque(bloque):
    # preferimos "+ información"
    for a in bloque.find_all("a", href=True):
        texto = limpiar_texto(a.get_text(" ", strip=True)).lower()
        href = (a.get("href") or "").strip()

        if not href:
            continue

        if "+ informacion" in texto or "+ información" in texto:
            return urljoin(BASE_URL, href)

    # fallback: primer /espectaculos/
    for a in bloque.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        href_abs = urljoin(BASE_URL, href)
        if "/espectaculos/" in href_abs:
            return href_abs

    return None


# -------------------------
# FICHA
# -------------------------

def extraer_titulo_ficha(soup):
    # En ficha suele venir:
    # # Bendita Terapia
    for tag in ["h1", "h2"]:
        el = soup.find(tag)
        if el:
            texto = limpiar_texto(el.get_text(" ", strip=True))
            if texto:
                return texto

    return None


def extraer_lugar_ficha(lineas):
    for i, linea in enumerate(lineas):
        t = limpiar_texto(linea).lower()

        if t in {"teatro marquina", "teatro príncipe gran vía", "teatro principe gran via"}:
            if "principe" in t or "príncipe" in t:
                return "Teatro Príncipe Gran Vía"
            return "Teatro Marquina"

    return None


def extraer_fecha_ficha(lineas):
    for linea in lineas:
        texto = limpiar_texto(linea)

        m = re.search(r"\b\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}\b", texto)
        if m:
            return limpiar_texto(m.group(0))

    return None


def extraer_info_ficha(session, url_ficha):
    try:
        r = get_url(url_ficha, session=session, timeout=20)
    except Exception as e:
        print(f"[AVISO] No se pudo abrir ficha Grupo Marquina: {url_ficha} -> {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    lineas = [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]

    titulo = extraer_titulo_ficha(soup)
    lugar = extraer_lugar_ficha(lineas)
    fecha_txt = extraer_fecha_ficha(lineas)

    return {
        "titulo": titulo,
        "lugar": lugar,
        "fecha_txt": fecha_txt,
    }


# -------------------------
# SCRAPER
# -------------------------

def sacar_grupomarquina():
    eventos = []
    vistos = set()
    session = requests.Session()

    respuesta = get_url(BASE_URL, session=session, timeout=20)
    soup = BeautifulSoup(respuesta.text, "html.parser")

    bloques = extraer_bloques_portada(soup)

    for bloque in bloques:
        try:
            titulo_portada = extraer_titulo_desde_bloque(bloque)
            lugar_portada = extraer_lugar_desde_bloque(bloque)
            url_ficha = extraer_url_ficha_desde_bloque(bloque)

            if not titulo_portada or not lugar_portada or not url_ficha:
                continue

            info_ficha = extraer_info_ficha(session, url_ficha)
            if not info_ficha:
                continue

            titulo = info_ficha.get("titulo") or titulo_portada
            lugar = info_ficha.get("lugar") or lugar_portada
            fecha_txt = info_ficha.get("fecha_txt")

            if not titulo or not lugar or not fecha_txt:
                continue

            info_fecha = parsear_rango_marquina(fecha_txt)
            if not info_fecha:
                continue

            agregar_evento(
                eventos,
                vistos,
                titulo,
                info_fecha.get("fecha"),
                lugar,
                url_ficha,
                BASE_URL,
                info_fecha=info_fecha
            )

        except Exception as e:
            print(f"[AVISO] Error en Grupo Marquina: {e}")

    return eventos