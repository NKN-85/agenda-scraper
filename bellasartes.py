import requests
import re
import calendar
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento


BASE_URL = "https://www.teatrobellasartes.es/"
LUGAR = "Teatro Bellas Artes"

MESES = {
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

MAPA_DIAS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

ORDEN_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


# -------------------------
# NORMALIZACION
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


def _mes_a_num(mes_txt):
    return MESES.get(_normalizar(mes_txt))


def _construir_fecha(dia, mes_num, anio):
    try:
        return date(int(anio), int(mes_num), int(dia))
    except Exception:
        return None


def _ultimo_dia_mes(mes_num, anio):
    return calendar.monthrange(anio, mes_num)[1]


# -------------------------
# CONSTRUCTORES INFO_FECHA
# -------------------------

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

    return {
        "tipo_fecha": "rango",
        "fecha": fi.isoformat(),
        "fecha_inicio": fi.isoformat(),
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": _limpiar(texto_original),
    }


def _info_desde(fi, texto_original=""):
    if not fi:
        return None

    return {
        "tipo_fecha": "desde",
        "fecha": fi.isoformat(),
        "fecha_inicio": fi.isoformat(),
        "fecha_fin": None,
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": _limpiar(texto_original),
    }


def _info_hasta(ff, texto_original=""):
    if not ff:
        return None

    return {
        "tipo_fecha": "hasta",
        "fecha": ff.isoformat(),
        "fecha_inicio": None,
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": _limpiar(texto_original),
    }


def _info_patron(fi, ff, dias_semana, texto_original=""):
    dias_semana = sorted(set(d for d in dias_semana if isinstance(d, int) and 0 <= d <= 6))
    if not dias_semana:
        return None

    base = fi or ff
    if not base:
        return None

    return {
        "tipo_fecha": "patron",
        "fecha": base.isoformat(),
        "fecha_inicio": fi.isoformat() if fi else None,
        "fecha_fin": ff.isoformat() if ff else None,
        "fechas_funcion": [],
        "dias_semana": dias_semana,
        "texto_fecha_original": _limpiar(texto_original),
    }


# -------------------------
# PARSER FECHA GENERAL
# -------------------------

def _parsear_fecha_general(texto):
    """
    Casos:
    - Del 1 al 5 de julio de 2026
    - Desde el 21 de marzo de 2026
    - Hasta el 30 de mayo de 2026
    """
    t = _normalizar(texto)

    m = re.fullmatch(r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})", t)
    if m:
        d1 = int(m.group(1))
        d2 = int(m.group(2))
        mes_num = _mes_a_num(m.group(3))
        anio = int(m.group(4))
        if mes_num:
            fi = _construir_fecha(d1, mes_num, anio)
            ff = _construir_fecha(d2, mes_num, anio)
            if fi and ff:
                if fi == ff:
                    return _info_unica(fi, texto)
                return _info_rango(fi, ff, texto)

    m = re.fullmatch(
        r"del\s+(\d{1,2})\s+de\s+([a-z]+)\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})",
        t
    )
    if m:
        d1 = int(m.group(1))
        m1 = _mes_a_num(m.group(2))
        d2 = int(m.group(3))
        m2 = _mes_a_num(m.group(4))
        anio = int(m.group(5))
        if m1 and m2:
            fi = _construir_fecha(d1, m1, anio)
            ff = _construir_fecha(d2, m2, anio)
            if fi and ff:
                if fi == ff:
                    return _info_unica(fi, texto)
                return _info_rango(fi, ff, texto)

    m = re.fullmatch(r"desde\s+el\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})", t)
    if m:
        dia = int(m.group(1))
        mes_num = _mes_a_num(m.group(2))
        anio = int(m.group(3))
        if mes_num:
            fi = _construir_fecha(dia, mes_num, anio)
            return _info_desde(fi, texto)

    m = re.fullmatch(r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})", t)
    if m:
        dia = int(m.group(1))
        mes_num = _mes_a_num(m.group(2))
        anio = int(m.group(3))
        if mes_num:
            ff = _construir_fecha(dia, mes_num, anio)
            return _info_hasta(ff, texto)

    # fecha única
    m = re.fullmatch(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})", t)
    if m:
        dia = int(m.group(1))
        mes_num = _mes_a_num(m.group(2))
        anio = int(m.group(3))
        if mes_num:
            f = _construir_fecha(dia, mes_num, anio)
            return _info_unica(f, texto)

    return None


# -------------------------
# PARSER HORARIOS / DIAS
# -------------------------

def _expandir_rango_dias(d1, d2):
    d1 = _normalizar(d1)
    d2 = _normalizar(d2)

    if d1 not in ORDEN_DIAS or d2 not in ORDEN_DIAS:
        return []

    i1 = ORDEN_DIAS.index(d1)
    i2 = ORDEN_DIAS.index(d2)

    if i1 <= i2:
        nombres = ORDEN_DIAS[i1:i2 + 1]
    else:
        nombres = ORDEN_DIAS[i1:] + ORDEN_DIAS[:i2 + 1]

    return [MAPA_DIAS[n] for n in nombres]


def _extraer_dias_desde_horarios(texto):
    t = _normalizar(texto)
    dias = set()

    # miércoles a viernes
    for m in re.finditer(
        r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t
    ):
        dias.update(_expandir_rango_dias(m.group(1), m.group(2)))

    # sábado y domingo
    for m in re.finditer(
        r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+y\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t
    ):
        dias.add(MAPA_DIAS[m.group(1)])
        dias.add(MAPA_DIAS[m.group(2)])

    # días sueltos
    for nombre, idx in MAPA_DIAS.items():
        if re.search(rf"\b{re.escape(nombre)}\b", t):
            dias.add(idx)

    return sorted(dias)


def _combinar_fecha_general_y_horarios(info_fecha_general, horarios_txt):
    if not info_fecha_general or not horarios_txt:
        return info_fecha_general

    dias = _extraer_dias_desde_horarios(horarios_txt)
    if not dias:
        return info_fecha_general

    tipo = info_fecha_general.get("tipo_fecha")
    fi = info_fecha_general.get("fecha_inicio")
    ff = info_fecha_general.get("fecha_fin")

    fi_date = date.fromisoformat(fi) if fi else None
    ff_date = date.fromisoformat(ff) if ff else None

    # única no la convertimos a patrón
    if tipo == "unica":
        return info_fecha_general

    if tipo in {"rango", "desde", "hasta"}:
        return _info_patron(fi_date, ff_date, dias, horarios_txt)

    return info_fecha_general


# -------------------------
# PORTADA
# -------------------------

def _extraer_obras_portada(soup):
    obras = []
    vistos = set()

    for bloque in soup.select("div.obra"):
        a_ficha = bloque.select_one("a.imagen[href]")
        titulo_el = bloque.select_one("div.faldon span.titulo")
        fecha_el = bloque.select_one("div.faldon span.fecha")

        if not a_ficha or not titulo_el:
            continue

        url_ficha = urljoin(BASE_URL, a_ficha.get("href", "").strip())
        titulo = _limpiar(titulo_el.get_text(" ", strip=True))
        fecha_portada = _limpiar(fecha_el.get_text(" ", strip=True)) if fecha_el else ""

        if not titulo or not url_ficha:
            continue

        clave = (titulo.lower(), url_ficha.lower())
        if clave in vistos:
            continue
        vistos.add(clave)

        obras.append({
            "titulo": titulo,
            "url_ficha": url_ficha,
            "fecha_portada": fecha_portada,
        })

    return obras


# -------------------------
# FICHA
# -------------------------

def _extraer_titulo_ficha(soup):
    for tag in ["h1", "h2"]:
        el = soup.find(tag)
        if el:
            txt = _limpiar(el.get_text(" ", strip=True))
            if txt:
                return txt

    if soup.title:
        txt = _limpiar(soup.title.get_text(" ", strip=True))
        if txt:
            return txt.split("|")[0].strip()

    return None


def _extraer_fecha_ficha(soup):
    el = soup.select_one("p.fecha")
    if el:
        return _limpiar(el.get_text(" ", strip=True))
    return ""


def _extraer_horarios_ficha(soup):
    aside = soup.select_one("div.aside.info-util")
    if not aside:
        return ""

    h3s = aside.find_all("h3")
    for h3 in h3s:
        if _normalizar(h3.get_text(" ", strip=True)) != "horarios":
            continue

        textos = []
        sib = h3.find_next_sibling()
        while sib and sib.name != "h3":
            txt = _limpiar(sib.get_text(" ", strip=True))
            if txt:
                textos.append(txt)
            sib = sib.find_next_sibling()

        return " ".join(textos).strip()

    return ""


def _extraer_info_ficha(session, url_ficha, fecha_portada=""):
    try:
        r = get_url(url_ficha, session=session, timeout=20)
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    titulo = _extraer_titulo_ficha(soup) or ""
    fecha_txt = _extraer_fecha_ficha(soup) or fecha_portada
    horarios_txt = _extraer_horarios_ficha(soup)

    if not titulo or not fecha_txt:
        return None

    info_fecha = _parsear_fecha_general(fecha_txt)
    if not info_fecha:
        return None

    info_fecha = _combinar_fecha_general_y_horarios(info_fecha, horarios_txt)

    return {
        "titulo": titulo,
        "info_fecha": info_fecha,
    }


# -------------------------
# SCRAPER
# -------------------------

def sacar_bellasartes():
    eventos = []
    vistos = set()
    session = requests.Session()

    try:
        r = get_url(BASE_URL, session=session, timeout=20)
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    obras = _extraer_obras_portada(soup)

    for obra in obras:
        try:
            info = _extraer_info_ficha(
                session=session,
                url_ficha=obra["url_ficha"],
                fecha_portada=obra["fecha_portada"],
            )
            if not info:
                continue

            agregar_evento(
                eventos=eventos,
                vistos=vistos,
                titulo=info["titulo"],
                fecha_evento=info["info_fecha"]["fecha"],
                lugar=LUGAR,
                url_evento=obra["url_ficha"],
                fuente=BASE_URL,
                info_fecha=info["info_fecha"],
            )
        except Exception as e:
            print(f"[AVISO] Error en Bellas Artes {obra['url_ficha']}: {e}")

    return eventos