import re
import requests
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento


BASE_URL = "https://www.teatrocircoprice.es/programacion"
BASE_DOMAIN = "https://www.teatrocircoprice.es"
LUGAR = "Teatro Circo Price"

MESES = {
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "septiembre": 9, "set": 9, "setiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}

CATEGORIAS = {
    "actividades",
    "cine",
    "circo",
    "humor",
    "magia",
    "musica",
    "música",
}


# -------------------------
# HELPERS
# -------------------------

def _limpiar(texto):
    return limpiar_texto(texto or "")


def _normalizar(texto):
    t = _limpiar(texto).lower()
    return (
        t.replace("á", "a")
         .replace("é", "e")
         .replace("í", "i")
         .replace("ó", "o")
         .replace("ú", "u")
    )


def _mes_a_num(txt):
    return MESES.get(_normalizar(txt))


def _anio_probable_para_mes(mes_num):
    hoy = date.today()
    anio = hoy.year
    if mes_num < hoy.month - 1:
        anio += 1
    return anio


def _construir_fecha(dia, mes_num, anio):
    try:
        return date(int(anio), int(mes_num), int(dia))
    except Exception:
        return None


def _es_num_dia(txt):
    return bool(re.fullmatch(r"\d{1,2}", _limpiar(txt)))


def _es_mes_abrev(txt):
    return _mes_a_num(txt) is not None


def _es_categoria(txt):
    return _normalizar(txt) in {_normalizar(x) for x in CATEGORIAS}


def _info_unica(f, texto_original=""):
    if not f:
        return None

    iso = f.isoformat()
    return {
        "tipo_fecha": "unica",
        "fecha": iso,
        "fecha_inicio": iso,
        "fecha_fin": iso,
        "fechas_funcion": [iso],
        "dias_semana": [],
        "texto_fecha_original": _limpiar(texto_original),
    }


def _info_rango(fi, ff, texto_original=""):
    if not fi or not ff:
        return None

    if fi == ff:
        return _info_unica(fi, texto_original)

    return {
        "tipo_fecha": "rango",
        "fecha": fi.isoformat(),
        "fecha_inicio": fi.isoformat(),
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": _limpiar(texto_original),
    }


# -------------------------
# MAPA TITULO -> URL
# -------------------------

def _extraer_urls_por_titulo(soup):
    """
    En la página, cada título tiene su enlace en h3 a:
    ### HOP!
    ### FINZI PASCA
    """
    urls = {}
    for a in soup.select("h3 a[href]"):
        titulo = _limpiar(a.get_text(" ", strip=True))
        href = (a.get("href") or "").strip()
        if not titulo or not href:
            continue
        urls[_normalizar(titulo)] = urljoin(BASE_DOMAIN, href)
    return urls


# -------------------------
# PARSEO LINEAL DEL LISTADO
# -------------------------

def _extraer_eventos_desde_lineas(lineas, urls_por_titulo):
    """
    Patrón real del Price:
    categoria
    dia inicio
    mes inicio
    [dia fin]
    [mes fin]
    TITULO
    subtitulo
    [CTA]

    Ejemplos visibles:
    Actividades / 28 / Sep / 14 / Jun / HOP!
    Actividades / 29 / Abr / MEMORIA GRAFICA Y CIRCO
    Circo / 08 / May / 09 / May / FINZI PASCA
    """
    eventos = []
    i = 0

    while i < len(lineas):
        linea = _limpiar(lineas[i])

        if not _es_categoria(linea):
            i += 1
            continue

        # intentamos leer inicio
        if i + 2 >= len(lineas):
            i += 1
            continue

        d1_txt = _limpiar(lineas[i + 1])
        m1_txt = _limpiar(lineas[i + 2])

        if not (_es_num_dia(d1_txt) and _es_mes_abrev(m1_txt)):
            i += 1
            continue

        d1 = int(d1_txt)
        m1 = _mes_a_num(m1_txt)
        a1 = _anio_probable_para_mes(m1)
        fi = _construir_fecha(d1, m1, a1)
        if not fi:
            i += 1
            continue

        j = i + 3
        ff = None

        # opcional: fecha fin
        if j + 1 < len(lineas):
            d2_txt = _limpiar(lineas[j])
            m2_txt = _limpiar(lineas[j + 1])

            if _es_num_dia(d2_txt) and _es_mes_abrev(m2_txt):
                d2 = int(d2_txt)
                m2 = _mes_a_num(m2_txt)
                a2 = a1
                if m2 < m1:
                    a2 += 1
                ff = _construir_fecha(d2, m2, a2)
                j += 2

        # siguiente línea debería ser el título
        if j >= len(lineas):
            i += 1
            continue

        titulo = _limpiar(lineas[j])
        if not titulo:
            i += 1
            continue

        # descartes de basura
        titulo_norm = _normalizar(titulo)
        if titulo_norm in {
            "fecha inicio",
            "fecha fin",
            "categoria",
            "pagina actual 1",
            "page 2",
            "siguiente pagina siguiente",
            "ultima pagina ultimo",
        }:
            i += 1
            continue

        # url del título
        url_evento = urls_por_titulo.get(titulo_norm, BASE_URL)

        texto_original = f"{linea} {d1_txt} {m1_txt}"
        if ff:
            texto_original += f" {ff.day:02d} {list(MESES.keys())[list(MESES.values()).index(ff.month)]}"

        info_fecha = _info_rango(fi, ff or fi, texto_original)

        eventos.append({
            "titulo": titulo,
            "url_evento": url_evento,
            "info_fecha": info_fecha,
        })

        i = j + 1

    return eventos


# -------------------------
# SCRAPER
# -------------------------

def sacar_price():
    eventos = []
    vistos = set()
    session = requests.Session()

    urls = [
        BASE_URL,
        f"{BASE_URL}?page=1",
    ]

    for url in urls:
        try:
            r = get_url(url, session=session, timeout=20)
        except Exception:
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        urls_por_titulo = _extraer_urls_por_titulo(soup)

        lineas = [
            _limpiar(x)
            for x in soup.get_text("\n", strip=True).splitlines()
            if _limpiar(x)
        ]

        eventos_extraidos = _extraer_eventos_desde_lineas(lineas, urls_por_titulo)

        for item in eventos_extraidos:
            agregar_evento(
                eventos=eventos,
                vistos=vistos,
                titulo=item["titulo"],
                fecha_evento=item["info_fecha"]["fecha"],
                lugar=LUGAR,
                url_evento=item["url_evento"],
                fuente=BASE_URL,
                info_fecha=item["info_fecha"],
            )

    return eventos