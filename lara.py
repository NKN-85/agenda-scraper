import requests
import re
import calendar
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento


BASE_URL = "https://teatrolara.com/programacion-teatro-lara"
BASE_DOMAIN = "https://teatrolara.com"

MAPA_SECCIONES = {
    "abono1": "Sala Cándido Lara",
    "abono2": "Sala Lola Membrives",
    "abono3": "Familiares",
    "abono4": "Eventos",
    "abono5": "Noches del Lara",
    "abono6": "Gira",
}

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

MAPA_DIAS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "sabados": 5,
    "sábados": 5,
    "domingo": 6,
    "domingos": 6,
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


def _anio_probable_para_mes(mes_num):
    hoy = date.today()
    anio = hoy.year
    if mes_num < hoy.month - 1:
        anio += 1
    return anio


def _ultimo_dia_mes(mes_num, anio):
    return calendar.monthrange(anio, mes_num)[1]


def _construir_fecha(dia, mes_num, anio):
    try:
        return date(int(anio), int(mes_num), int(dia))
    except Exception:
        return None


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


def _info_lista(fechas, texto_original=""):
    fechas = sorted(set(f for f in fechas if f))
    if not fechas:
        return None

    fechas_iso = [f.isoformat() for f in fechas]
    return {
        "tipo_fecha": "lista",
        "fecha": fechas_iso[0],
        "fecha_inicio": fechas_iso[0],
        "fecha_fin": fechas_iso[-1],
        "fechas_funcion": fechas_iso,
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

    fecha_repr = fi or ff
    if not fecha_repr:
        return None

    return {
        "tipo_fecha": "patron",
        "fecha": fecha_repr.isoformat(),
        "fecha_inicio": fi.isoformat() if fi else None,
        "fecha_fin": ff.isoformat() if ff else None,
        "fechas_funcion": [],
        "dias_semana": dias_semana,
        "texto_fecha_original": _limpiar(texto_original),
    }


# -------------------------
# PARSERS FECHA
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


def _parsear_fecha_unica_texto(texto):
    t = _limpiar(texto)
    if not t:
        return None

    m = re.search(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\b", t, re.IGNORECASE)
    if not m:
        m = re.search(r"\b(\d{1,2})\s+([a-záéíóú]+)\b", t, re.IGNORECASE)

    if not m:
        return None

    dia = int(m.group(1))
    mes_num = _mes_a_num(m.group(2))
    if not mes_num:
        return None

    anio = _anio_probable_para_mes(mes_num)
    return _construir_fecha(dia, mes_num, anio)


def _parsear_hasta_texto(texto):
    t = _normalizar(texto)
    m = re.search(r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-z]+)", t)
    if not m:
        return None

    dia = int(m.group(1))
    mes_num = _mes_a_num(m.group(2))
    if not mes_num:
        return None

    anio = _anio_probable_para_mes(mes_num)
    ff = _construir_fecha(dia, mes_num, anio)
    if not ff:
        return None

    return _info_hasta(ff, texto)


def _parsear_temporada_texto(texto):
    t = _normalizar(texto)
    m = re.search(r"temporada\s+(\d{2})\s*/\s*(\d{2})", t)
    if not m:
        return None, None

    anio_ini = 2000 + int(m.group(1))
    anio_fin = 2000 + int(m.group(2))

    fi = date(anio_ini, 9, 1)
    ff = date(anio_fin, 6, 30)
    return fi, ff


def _parsear_mes_anio_texto(texto):
    t = _normalizar(texto)
    m = re.search(r"\b([a-z]+)\s+(20\d{2})\b", t)
    if not m:
        return None

    mes_num = _mes_a_num(m.group(1))
    if not mes_num:
        return None

    anio = int(m.group(2))
    fi = date(anio, mes_num, 1)
    ff = date(anio, mes_num, _ultimo_dia_mes(mes_num, anio))
    return _info_rango(fi, ff, texto)


def _parsear_mes_solo_texto(texto):
    """
    Estreno mayo / Reestreno junio
    """
    t = _normalizar(texto)
    m = re.search(r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b", t)
    if not m:
        return None

    mes_num = _mes_a_num(m.group(1))
    if not mes_num:
        return None

    anio = _anio_probable_para_mes(mes_num)
    fi = date(anio, mes_num, 1)
    ff = date(anio, mes_num, _ultimo_dia_mes(mes_num, anio))
    return _info_rango(fi, ff, texto)


def _extraer_dias_semana(texto):
    t = _normalizar(texto)
    dias = set()

    for m in re.finditer(
        r"de\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t,
    ):
        dias.update(_expandir_rango_dias(m.group(1), m.group(2)))

    for m in re.finditer(
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+y\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b",
        t,
    ):
        dias.add(MAPA_DIAS[m.group(1)])
        dias.add(MAPA_DIAS[m.group(2)])

    for nombre, idx in MAPA_DIAS.items():
        if re.search(rf"\b{re.escape(nombre)}\b", t):
            dias.add(idx)

    return sorted(dias)


def _parsear_patron_texto(texto):
    if not texto:
        return None

    dias = _extraer_dias_semana(texto)
    if not dias:
        return None

    info_hasta = _parsear_hasta_texto(texto)
    if info_hasta:
        ff = date.fromisoformat(info_hasta["fecha_fin"])
        fi = date.today()
        return _info_patron(fi, ff, dias, texto)

    fi_temp, ff_temp = _parsear_temporada_texto(texto)
    if fi_temp and ff_temp:
        return _info_patron(fi_temp, ff_temp, dias, texto)

    return _info_patron(date.today(), None, dias, texto)


def _resolver_fecha_desde_texto_libre(texto):
    if not texto:
        return None

    info = _parsear_patron_texto(texto)
    if info:
        return info

    info = _parsear_hasta_texto(texto)
    if info:
        return info

    f = _parsear_fecha_unica_texto(texto)
    if f:
        return _info_unica(f, texto)

    info = _parsear_mes_anio_texto(texto)
    if info:
        return info

    info = _parsear_mes_solo_texto(texto)
    if info:
        return info

    return None


# -------------------------
# PORTADA
# -------------------------

def _extraer_eventos_portada_por_seccion(soup):
    eventos = []

    for section_id, nombre_seccion in MAPA_SECCIONES.items():
        cont = soup.find("div", id=section_id)
        if not cont:
            continue

        for a in cont.find_all("a", class_="ficha-obra", href=True):
            href = (a.get("href") or "").strip()
            url_ficha = urljoin(BASE_DOMAIN, href)

            h3 = a.find("h3")
            titulo = _limpiar(h3.get_text(" ", strip=True)) if h3 else ""

            content = a.find("div", class_="content")
            claim = ""
            if content:
                textos = [_limpiar(x) for x in content.stripped_strings if _limpiar(x)]
                if textos and titulo and _normalizar(textos[0]) == _normalizar(titulo):
                    textos = textos[1:]
                claim = " ".join(textos).strip()

            if not titulo or not url_ficha:
                continue

            eventos.append({
                "titulo": titulo,
                "url_ficha": url_ficha,
                "seccion_portada": nombre_seccion,
                "claim_portada": claim,
            })

    return eventos


# -------------------------
# FICHA
# -------------------------

def _extraer_lineas(soup):
    return [_limpiar(x) for x in soup.get_text("\n", strip=True).splitlines() if _limpiar(x)]


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


def _extraer_valor_campo(lineas, etiqueta):
    objetivo = _normalizar(etiqueta)

    for i, linea in enumerate(lineas):
        if _normalizar(linea) != objetivo:
            continue

        j = i + 1
        while j < len(lineas):
            valor = _limpiar(lineas[j])
            if valor:
                return valor
            j += 1

    return None


def _extraer_proximas_funciones_dom(soup):
    fechas = []

    for bloque in soup.select("div.fechas"):
        col1 = bloque.select_one("div.column1")
        if not col1:
            continue

        span_mes = col1.find("span")
        mes_txt = _limpiar(span_mes.get_text(" ", strip=True)) if span_mes else ""

        texto_col1 = _limpiar(col1.get_text(" ", strip=True))
        # texto_col1 suele ser "ABR 24"
        m = re.search(r"\b(\d{1,2})\b", texto_col1)
        if not m:
            continue

        dia = int(m.group(1))
        mes_num = _mes_a_num(mes_txt)
        if not mes_num:
            continue

        anio = _anio_probable_para_mes(mes_num)
        f = _construir_fecha(dia, mes_num, anio)
        if f and f >= date.today():
            fechas.append(f)

    return sorted(set(fechas))


def _resolver_lugar_ficha(espacio_ficha, seccion_portada):
    if espacio_ficha:
        return espacio_ficha
    return seccion_portada or "Teatro Lara"


def _extraer_info_ficha(session, url_ficha, seccion_portada=None, claim_portada=""):
    try:
        r = get_url(url_ficha, session=session, timeout=20)
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    lineas = _extraer_lineas(soup)

    titulo = _extraer_titulo_ficha(soup)
    espacio = _extraer_valor_campo(lineas, "ESPACIO")
    fecha_txt = _extraer_valor_campo(lineas, "FECHA") or ""

    lugar = _resolver_lugar_ficha(espacio, seccion_portada)
    info_fecha = None

    # 1) prioridad máxima: DOM de próximas funciones
    proximas = _extraer_proximas_funciones_dom(soup)
    if proximas:
        info_fecha = _info_lista(proximas, "proximas funciones")

    # 2) FECHA de ficha
    if not info_fecha and fecha_txt:
        info_fecha = _resolver_fecha_desde_texto_libre(fecha_txt)

    # 3) claim portada
    if not info_fecha and claim_portada:
        info_fecha = _resolver_fecha_desde_texto_libre(claim_portada)

    if not titulo or not lugar or not info_fecha:
        return None

    return {
        "titulo": titulo,
        "lugar": lugar,
        "info_fecha": info_fecha,
    }


# -------------------------
# SCRAPER
# -------------------------

def sacar_lara():
    eventos = []
    vistos = set()
    session = requests.Session()

    try:
        r = get_url(BASE_URL, session=session, timeout=20)
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    candidatos = _extraer_eventos_portada_por_seccion(soup)

    for cand in candidatos:
        try:
            info = _extraer_info_ficha(
                session=session,
                url_ficha=cand["url_ficha"],
                seccion_portada=cand["seccion_portada"],
                claim_portada=cand["claim_portada"],
            )
            if not info:
                continue

            agregar_evento(
                eventos=eventos,
                vistos=vistos,
                titulo=info["titulo"],
                fecha_evento=info["info_fecha"]["fecha"],
                lugar=info["lugar"],
                url_evento=cand["url_ficha"],
                fuente=BASE_URL,
                info_fecha=info["info_fecha"],
            )

        except Exception as e:
            print(f"[AVISO] Error en Teatro Lara {cand['url_ficha']}: {e}")

    return eventos