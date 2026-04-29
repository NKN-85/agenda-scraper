import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from utils import agregar_evento, get_url, limpiar_texto


BASE_URL = "https://www.circulobellasartes.com/agenda/"
LUGAR = "Círculo de Bellas Artes"

PATRON_RANGO = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})"
)

PATRON_UNICA = re.compile(
    r"\b(\d{2}/\d{2}/\d{4})\b"
)


def _fecha_es_a_iso(fecha_txt):
    try:
        d, m, y = fecha_txt.split("/")
        return f"{y}-{m}-{d}"
    except Exception:
        return None


def _parsear_info_fecha(texto):
    t = limpiar_texto(texto)

    m = PATRON_RANGO.search(t)
    if m:
        fi = _fecha_es_a_iso(m.group(1))
        ff = _fecha_es_a_iso(m.group(2))
        if fi and ff:
            return {
                "tipo_fecha": "rango",
                "fecha_inicio": fi,
                "fecha_fin": ff,
                "texto_fecha_original": t,
            }

    m = PATRON_UNICA.search(t)
    if m:
        f = _fecha_es_a_iso(m.group(1))
        if f:
            return {
                "tipo_fecha": "unica",
                "fecha": f,
                "texto_fecha_original": t,
            }

    return None


def _es_url_evento_valida(href):
    if not href:
        return False

    u = href.strip().lower()

    if not u.startswith("http"):
        return False

    if u.rstrip("/") == BASE_URL.rstrip("/"):
        return False

    return "circulobellasartes.com" in u


def sacar_circulo_bellas_artes():
    eventos = []
    vistos = set()
    session = requests.Session()

    try:
        respuesta = get_url(BASE_URL, session=session, timeout=20)
    except Exception as e:
        print(f"[AVISO] Círculo Bellas Artes fallo: {e}")
        return []

    soup = BeautifulSoup(respuesta.text, "html.parser")

    items = []
    titulos = soup.find_all("h2")

    for h2 in titulos:
        a = h2.find("a", href=True)
        if not a:
            continue

        titulo = limpiar_texto(a.get_text(" ", strip=True))
        if not titulo:
            continue

        url_evento = urljoin(BASE_URL, a["href"].strip())
        if not _es_url_evento_valida(url_evento):
            continue

        fecha_el = h2.find_next("p")
        if not fecha_el:
            continue

        texto_fecha = limpiar_texto(fecha_el.get_text(" ", strip=True))
        info_fecha = _parsear_info_fecha(texto_fecha)
        if not info_fecha:
            continue

        items.append({
            "titulo": titulo,
            "url_evento": url_evento,
            "info_fecha": info_fecha,
        })

    for item in items:
        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=item["titulo"],
            fecha_evento=item["info_fecha"].get("fecha"),
            lugar=LUGAR,
            url_evento=item["url_evento"],
            fuente=BASE_URL,
            info_fecha=item["info_fecha"],
        )

    return eventos