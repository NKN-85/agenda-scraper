import re
import unicodedata
import requests
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url, limpiar_texto, construir_fecha
from helpers.avisos import avisar


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

MESES_ABR = {
    "ENE": "enero",
    "FEB": "febrero",
    "MAR": "marzo",
    "ABR": "abril",
    "MAY": "mayo",
    "JUN": "junio",
    "JUL": "julio",
    "AGO": "agosto",
    "SEP": "septiembre",
    "OCT": "octubre",
    "NOV": "noviembre",
    "DIC": "diciembre",
}


def _normalizar(texto):
    if not texto:
        return ""

    texto = limpiar_texto(str(texto)).lower()
    texto = _reparar_mojibake(texto)
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace("-", " ")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def _reparar_mojibake(texto):
    if not texto:
        return ""

    texto = str(texto)

    if "Ã" not in texto and "Â" not in texto:
        return texto

    try:
        return texto.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        return texto


def _normalizar_mes(mes):
    mes = limpiar_texto(mes).upper().strip(".")
    return MESES_ABR.get(mes[:3], mes.lower())


def _fecha_desde_dia_mes(dia, mes, anio):
    return construir_fecha(int(dia), _normalizar_mes(mes), int(anio))


def _parsear_info_fecha(texto):
    texto_original = limpiar_texto(_reparar_mojibake(texto))
    t = texto_original.upper()

    # 30 ABR - 31 MAY
    m = re.search(
        r"\b(\d{1,2})\s+([A-ZÁÉÍÓÚ]{3,})\s*[-–]\s*(\d{1,2})\s+([A-ZÁÉÍÓÚ]{3,})\b",
        t,
    )
    if m:
        anio = date.today().year
        inicio = _fecha_desde_dia_mes(m.group(1), m.group(2), anio)
        fin = _fecha_desde_dia_mes(m.group(3), m.group(4), anio)

        # Rango que cruza año: 21 NOV - 11 ENE.
        if inicio and fin and fin < inicio:
            fin = _fecha_desde_dia_mes(m.group(3), m.group(4), anio + 1)

        # Temporada siguiente si todo el rango ya pasó.
        if inicio and fin and fin < date.today():
            inicio = _fecha_desde_dia_mes(m.group(1), m.group(2), anio + 1)
            fin = _fecha_desde_dia_mes(m.group(3), m.group(4), anio + 1)

            if inicio and fin and fin < inicio:
                fin = _fecha_desde_dia_mes(m.group(3), m.group(4), anio + 2)

        if inicio and fin:
            return {
                "tipo_fecha": "rango",
                "fecha": inicio.isoformat(),
                "fecha_inicio": inicio.isoformat(),
                "fecha_fin": fin.isoformat(),
                "fechas_funcion": [],
                "dias_semana": [],
                "texto_fecha_original": texto_original,
            }

    # Sábado 23 y domingo 24 de mayo
    m = re.search(
        r"\b(?:LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)?\s*"
        r"(\d{1,2})\s+Y\s+"
        r"(?:LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)?\s*"
        r"(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚ]{3,})\b",
        t,
    )
    if m:
        anio = date.today().year
        f1 = _fecha_desde_dia_mes(m.group(1), m.group(3), anio)
        f2 = _fecha_desde_dia_mes(m.group(2), m.group(3), anio)

        if f1 and f2 and f2 < date.today():
            f1 = _fecha_desde_dia_mes(m.group(1), m.group(3), anio + 1)
            f2 = _fecha_desde_dia_mes(m.group(2), m.group(3), anio + 1)

        if f1 and f2:
            return {
                "tipo_fecha": "lista",
                "fecha": f1.isoformat(),
                "fecha_inicio": f1.isoformat(),
                "fecha_fin": f2.isoformat(),
                "fechas_funcion": [f1.isoformat(), f2.isoformat()],
                "dias_semana": [],
                "texto_fecha_original": texto_original,
            }

    # Domingo 12 de abril / 01 DIC
    m = re.search(
        r"\b(?:LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)?\s*"
        r"(\d{1,2})\s+(?:DE\s+)?([A-ZÁÉÍÓÚ]{3,})\b",
        t,
    )
    if m:
        anio = date.today().year
        f = _fecha_desde_dia_mes(m.group(1), m.group(2), anio)

        if f and f < date.today():
            f = _fecha_desde_dia_mes(m.group(1), m.group(2), anio + 1)

        if f:
            return {
                "tipo_fecha": "unica",
                "fecha": f.isoformat(),
                "fecha_inicio": f.isoformat(),
                "fecha_fin": f.isoformat(),
                "fechas_funcion": [f.isoformat()],
                "dias_semana": [],
                "texto_fecha_original": texto_original,
            }

    return None


def _html_desde_respuesta(respuesta):
    try:
        return respuesta.content.decode("utf-8", errors="replace")
    except Exception:
        return respuesta.text or ""


def _html_valido(html):
    html_norm = _normalizar(html)
    return (
        "item event resume" in html_norm
        and "/evento/" in html
        and "incapsula incident" not in html_norm
        and "request unsuccessful" not in html_norm
    )


def _get_html_requests(url, session):
    try:
        respuesta = get_url(
            url,
            headers=HEADERS,
            session=session,
            timeout=20,
        )
        html = _html_desde_respuesta(respuesta)

        if _html_valido(html):
            return html

    except Exception:
        return ""

    return ""


def _get_html_playwright(url):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        avisar(
            "Para estas salas instala Playwright: "
            "pip install playwright && python -m playwright install chromium"
        )
        return ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="es-ES",
                viewport={"width": 1440, "height": 1200},
            )

            page = context.new_page()

            try:
                page.goto(url, wait_until="load", timeout=60000)
            except Exception:
                # Algunas páginas siguen navegando/cambiando contenido.
                # En ese caso intentamos seguir con lo que haya cargado.
                pass

            try:
                page.wait_for_selector("div.item-event-resume, article.event-resume", timeout=15000)
            except Exception:
                pass

            page.wait_for_timeout(3000)

            try:
                page.evaluate("window.stop()")
            except Exception:
                pass

            html = page.content()
            browser.close()
            return html

    except Exception as e:
        avisar(f"No se pudo renderizar con Playwright: {url} -> {e}")
        return ""


def _get_html(url, session):
    html = _get_html_requests(url, session)
    if html:
        return html

    return _get_html_playwright(url)


def _html_activo(html):
    return re.split(
        r"LO\s+QUE\s+YA\s+HEMOS\s+VISTO\s+ESTA\s+TEMPORADA",
        html,
        maxsplit=1,
        flags=re.I,
    )[0]


def _cta_activo(item):
    cta = item.select_one(".cta a")
    if not cta:
        return False

    texto = _normalizar(cta.get_text(" ", strip=True))
    href = limpiar_texto(cta.get("href", ""))

    if "agotada" in texto or "agotado" in texto:
        return False

    return (
        ("entradas" in texto and href)
        or ("solicitudes abiertas" in texto and href)
        or ("proximamente" in texto)
    )


def _items_activos(html):
    soup = BeautifulSoup(_html_activo(html), "html.parser")

    for item in soup.select("div.item-event-resume"):
        clases = item.get("class", [])
        if "item-event-old" in clases:
            continue

        yield item


def _titulo_item(item):
    h2 = (
        item.select_one(".detail h2 span")
        or item.select_one("h2 span")
        or item.select_one("h2")
    )
    if not h2:
        return ""

    return limpiar_texto(h2.get_text(" ", strip=True))


def _url_evento_item(item, base_url):
    enlace = (
        item.select_one(".detail h2 a[href*='/evento/']")
        or item.select_one(".wrapper-detail a[href*='/evento/']")
        or item.select_one("a[href*='/evento/']")
    )
    if enlace and enlace.get("href"):
        return urljoin(base_url, enlace["href"])

    return ""


def _texto_fecha_lugar_item(item, teatro_busqueda):
    teatro_norm = _normalizar(teatro_busqueda)

    for p in item.select(".detail p"):
        texto = limpiar_texto(p.get_text(" ", strip=True))
        if "|" in texto and teatro_norm in _normalizar(texto):
            return texto

    return limpiar_texto(item.get_text(" ", strip=True))


def _extraer_evento_item(item, base_url, teatro_busqueda, extraer_lugar):
    texto_item = limpiar_texto(item.get_text(" ", strip=True))

    if _normalizar(teatro_busqueda) not in _normalizar(texto_item):
        return None

    if not _cta_activo(item):
        return None

    titulo = _titulo_item(item)
    url_evento = _url_evento_item(item, base_url)
    texto_fecha_lugar = _texto_fecha_lugar_item(item, teatro_busqueda)
    info_fecha = _parsear_info_fecha(texto_fecha_lugar) or _parsear_info_fecha(texto_item)

    if not titulo or not url_evento or not info_fecha:
        return None

    lugar = extraer_lugar(texto_fecha_lugar)

    return titulo, info_fecha, lugar, url_evento


BASE_URLS = [
    "https://dramatico.inaem.gob.es/programacion/teatro-valle-inclan/",
    "https://dramatico.inaem.gob.es/programacion/teatro-valle-inclan/sala-valle-inclan/",
    "https://dramatico.inaem.gob.es/programacion/teatro-valle-inclan/sala-francisco-nieva/",
    "https://dramatico.inaem.gob.es/programacion/teatro-valle-inclan/sala-mirlo-blanco/",
]

FUENTE = "https://dramatico.inaem.gob.es/programacion/teatro-valle-inclan/"
TEATRO_BUSQUEDA = "Teatro Valle-Inclán"
LUGAR_BASE = "Teatro Valle-Inclán"


def _extraer_lugar(texto):
    texto = _reparar_mojibake(texto)

    if "Sala Francisco Nieva" in texto:
        return "Teatro Valle-Inclán - Sala Francisco Nieva"

    if "Sala El Mirlo Blanco" in texto or "El Mirlo Blanco" in texto:
        return "Teatro Valle-Inclán - Sala El Mirlo Blanco"

    if "Sala Grande" in texto:
        return "Teatro Valle-Inclán - Sala Grande"

    return LUGAR_BASE


def sacar_valle_inclan():
    eventos = []
    vistos = set()
    session = requests.Session()

    for url in BASE_URLS:
        html = _get_html(url, session)
        if not html:
            continue

        for item in _items_activos(html):
            extraido = _extraer_evento_item(
                item=item,
                base_url=url,
                teatro_busqueda=TEATRO_BUSQUEDA,
                extraer_lugar=_extraer_lugar,
            )

            if not extraido:
                continue

            titulo, info_fecha, lugar, url_evento = extraido

            agregar_evento(
                eventos=eventos,
                vistos=vistos,
                titulo=titulo,
                fecha_evento=info_fecha.get("fecha"),
                lugar=lugar,
                url_evento=url_evento,
                fuente=FUENTE,
                info_fecha=info_fecha,
            )

    return eventos