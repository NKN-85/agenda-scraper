import re
import unicodedata
import requests
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento, construir_fecha


BASE_URL = "https://salagalileo.es/programacion/"
LUGAR = "Sala Galileo Galilei"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

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

MESES_NUM = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


def _normalizar(texto):
    if not texto:
        return ""

    texto = limpiar_texto(str(texto)).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def _html_desde_respuesta(respuesta):
    try:
        return respuesta.content.decode("utf-8", errors="replace")
    except Exception:
        return respuesta.text or ""


def _html_valido(html):
    t = _normalizar(html)
    return "mec event article" in t and "mec event title" in t


def _get_html_requests(session, url):
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
        pass

    return ""


def _get_html_playwright(url):
    """
    Fallback por si salagalileo.es devuelve un HTML incompleto con requests.
    Solo se usa si requests no trae los artículos MEC.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
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
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
            return html
    except Exception:
        return ""


def _get_html(session, url):
    html = _get_html_requests(session, url)
    if html:
        return html

    return _get_html_playwright(url)


def _mes_corto_a_largo(mes_txt):
    if not mes_txt:
        return None

    m = _normalizar(mes_txt)[:3]
    return MESES_CORTOS.get(m)


def _mes_corto_a_num(mes_txt):
    if not mes_txt:
        return None

    m = _normalizar(mes_txt)[:3]
    return MESES_NUM.get(m)


def _anio_mes_desde_clases(article):
    """
    Galileo añade clases tipo:
    mec-toggle-202604-770
    mec-toggle-202605-770

    De ahí sacamos año y mes reales, sin depender del año actual.
    """
    clases = " ".join(article.get("class", []) or [])
    m = re.search(r"mec-toggle-(20\d{2})(\d{2})", clases)
    if not m:
        return None, None

    return int(m.group(1)), int(m.group(2))


def _fecha_desde_label(fecha_txt, article):
    """
    Ejemplos:
    - 29 Abr
    - 01 May
    """
    fecha_txt = limpiar_texto(fecha_txt)
    if not fecha_txt:
        return None, None

    m = re.search(r"(\d{1,2})\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]{3,})", fecha_txt)
    if not m:
        return None, None

    dia = int(m.group(1))
    mes_txt = m.group(2)

    anio_clase, mes_clase = _anio_mes_desde_clases(article)
    mes_label = _mes_corto_a_num(mes_txt)
    mes_largo = _mes_corto_a_largo(mes_txt)

    if not mes_largo:
        return None, None

    # Preferimos el año del MEC si viene en la clase.
    anio = anio_clase or date.today().year

    # Si no hay clase MEC y la fecha ya pasó claramente, asumimos siguiente año.
    if not anio_clase:
        mes_num = mes_label
        if mes_num and mes_num < date.today().month - 1:
            anio += 1

    # Si hay clase y el mes del label no coincide, mantenemos el mes del label:
    # la clase solo se usa para año.
    fecha = construir_fecha(dia, mes_largo, anio)
    if not fecha:
        return None, None

    info_fecha = {
        "tipo_fecha": "unica",
        "fecha": fecha.isoformat(),
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": fecha.isoformat(),
        "fechas_funcion": [fecha.isoformat()],
        "dias_semana": [],
        "texto_fecha_original": fecha_txt,
    }

    return fecha, info_fecha


def _titulo_y_url(article):
    a = article.select_one("h3.mec-event-title a[href]")
    if not a:
        return "", ""

    titulo = limpiar_texto(a.get_text(" ", strip=True))
    url_evento = urljoin(BASE_URL, a.get("href", "").strip())

    return titulo, url_evento


def _article_tiene_ticket_o_info(article):
    """
    No bloqueamos si falta Tickets, porque algunos eventos pueden tener solo Info.
    Sirve para evitar artículos basura: debe tener al menos enlace Info o Tickets.
    """
    for a in article.select("a[href]"):
        texto = _normalizar(a.get_text(" ", strip=True))
        href = a.get("href", "").strip()

        if not href:
            continue

        if "tickets" in texto or "info" in texto:
            return True

        if "/programacion/" in href:
            return True

    return False


def _extraer_evento(article):
    if not _article_tiene_ticket_o_info(article):
        return None

    titulo, url_evento = _titulo_y_url(article)
    if not titulo or not url_evento:
        return None

    fecha_el = article.select_one("span.mec-start-date-label")
    if not fecha_el:
        return None

    fecha_txt = limpiar_texto(fecha_el.get_text(" ", strip=True))
    fecha_evento, info_fecha = _fecha_desde_label(fecha_txt, article)

    if not fecha_evento or not info_fecha:
        return None

    return titulo, fecha_evento, info_fecha, url_evento


def sacar_galileo():
    eventos = []
    vistos = set()
    session = requests.Session()

    html = _get_html(session, BASE_URL)
    if not html:
        return eventos

    soup = BeautifulSoup(html, "html.parser")

    for article in soup.select("article.mec-event-article"):
        extraido = _extraer_evento(article)
        if not extraido:
            continue

        titulo, fecha_evento, info_fecha, url_evento = extraido

        agregar_evento(
            eventos,
            vistos,
            titulo,
            fecha_evento,
            LUGAR,
            url_evento,
            BASE_URL,
            info_fecha=info_fecha,
        )

    return eventos