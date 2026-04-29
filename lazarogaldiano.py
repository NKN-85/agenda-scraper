import requests
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento


BASE_DOMAIN = "https://www.museolazarogaldiano.es"
FUENTE = "https://www.museolazarogaldiano.es/actividades"
LUGAR = "Museo Lázaro Galdiano"

SECCIONES = [
    ("Actividades", "https://www.museolazarogaldiano.es/actividades"),
    ("Talleres", "https://www.museolazarogaldiano.es/talleres"),
    ("Exposiciones", "https://www.museolazarogaldiano.es/actividades/exposiciones"),
    ("Conciertos", "https://www.museolazarogaldiano.es/conciertos"),
    ("Artes escénicas", "https://www.museolazarogaldiano.es/artes-escenicas"),
]

MESES = {
    "enero": 1, "ene": 1,
    "febrero": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6,
    "julio": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "septiembre": 9, "setiembre": 9, "sep": 9,
    "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12,
}

DIAS_SEMANA = {
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


def _fecha(dia, mes, anio):
    try:
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def _anio_probable_para_mes(mes):
    hoy = date.today()
    anio = hoy.year
    if mes < hoy.month - 1:
        anio += 1
    return anio


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

    return [DIAS_SEMANA[n] for n in nombres]


# -------------------------
# INFO_FECHA
# -------------------------

def _info_unica(f, texto_original=""):
    if not f or f < date.today():
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
    fechas = sorted(set(f for f in fechas if f and f >= date.today()))
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
    if not fi or not ff or ff < date.today():
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


def _info_patron(fi, ff, dias_semana, texto_original=""):
    dias_semana = sorted(set(dias_semana or []))
    if not fi or not ff or not dias_semana or ff < date.today():
        return None

    return {
        "tipo_fecha": "patron",
        "fecha": fi.isoformat(),
        "fecha_inicio": fi.isoformat(),
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [],
        "dias_semana": dias_semana,
        "texto_fecha_original": _limpiar(texto_original),
    }


# -------------------------
# PARSERS FECHA
# -------------------------

def _parsear_rango_puntos(texto):
    """
    09.04-28.06.2026
    9.04 - 28.06.2026
    """
    t = _limpiar(texto)

    m = re.search(
        r"\b(\d{1,2})\.(\d{1,2})\s*[-–]\s*(\d{1,2})\.(\d{1,2})\.(20\d{2})\b",
        t
    )
    if not m:
        return None, None

    d1 = int(m.group(1))
    m1 = int(m.group(2))
    d2 = int(m.group(3))
    m2 = int(m.group(4))
    anio = int(m.group(5))

    fi = _fecha(d1, m1, anio)
    ff = _fecha(d2, m2, anio)

    return fi, ff


def _parsear_fecha_natural(texto):
    """
    sábado 23 de mayo a las 11:00
    23 de mayo de 2026
    """
    t = _normalizar(texto)

    m = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(20\d{2}))?", t)
    if not m:
        return None

    dia = int(m.group(1))
    mes = _mes_a_num(m.group(2))
    if not mes:
        return None

    anio = int(m.group(3)) if m.group(3) else _anio_probable_para_mes(mes)
    return _fecha(dia, mes, anio)


def _parsear_lista_fechas_naturales(texto):
    """
    23 de mayo, 14 de junio y 28 de junio de 2026
    """
    t = _normalizar(texto)
    fechas = []

    anio_global = None
    m_anio = re.search(r"\b(20\d{2})\b", t)
    if m_anio:
        anio_global = int(m_anio.group(1))

    for m in re.finditer(r"\b(\d{1,2})\s+de\s+([a-z]+)", t):
        dia = int(m.group(1))
        mes = _mes_a_num(m.group(2))
        if not mes:
            continue

        anio = anio_global or _anio_probable_para_mes(mes)
        f = _fecha(dia, mes, anio)
        if f:
            fechas.append(f)

    return fechas


def _extraer_dias_semana(texto):
    """
    De martes a domingo
    Martes a domingo
    Sábados y domingos
    """
    t = _normalizar(texto)
    dias = set()

    for m in re.finditer(
        r"(?:de\s+)?(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t
    ):
        dias.update(_expandir_rango_dias(m.group(1), m.group(2)))

    for m in re.finditer(
        r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+y\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?",
        t
    ):
        dias.add(DIAS_SEMANA[m.group(1)])
        dias.add(DIAS_SEMANA[m.group(2)])

    for nombre, idx in DIAS_SEMANA.items():
        if re.search(rf"\b{re.escape(nombre)}s?\b", t):
            dias.add(idx)

    return sorted(dias)


def _resolver_info_fecha(fecha_txt, horario_txt, texto_fallback=""):
    texto_total = " ".join([fecha_txt or "", horario_txt or "", texto_fallback or ""]).strip()

    # 1) rango tipo 09.04-28.06.2026
    fi, ff = _parsear_rango_puntos(fecha_txt) if fecha_txt else (None, None)
    if fi and ff:
        dias = _extraer_dias_semana(horario_txt)
        if dias:
            return _info_patron(fi, ff, dias, texto_total)
        return _info_rango(fi, ff, texto_total)

    # 2) lista de fechas naturales
    fechas = _parsear_lista_fechas_naturales(texto_total)
    if len(fechas) > 1:
        return _info_lista(fechas, texto_total)

    # 3) fecha única
    f = _parsear_fecha_natural(texto_total)
    if f:
        return _info_unica(f, texto_total)

    return None


# -------------------------
# EXTRACCION PORTADA / SECCIONES
# -------------------------

def _extraer_urls_seccion(soup):
    urls = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        txt = _limpiar(a.get_text(" ", strip=True))

        if not href:
            continue

        url = urljoin(BASE_DOMAIN, href)

        # Nos quedamos con fichas de actividades, evitando menús generales
        if "/actividades/" not in url:
            continue

        if url.rstrip("/") in {
            "https://www.museolazarogaldiano.es/actividades",
            "https://www.museolazarogaldiano.es/actividades/exposiciones",
        }:
            continue

        if not txt and "actividades" not in url:
            continue

        if url in vistos:
            continue

        vistos.add(url)
        urls.append(url)

    return urls


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
        return _limpiar(soup.title.get_text(" ", strip=True)).split("|")[0].strip()

    return None


def _extraer_valor_por_etiqueta(lineas, etiqueta):
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

    return ""


def _extraer_fecha_ficha(soup, lineas):
    # Primero formatos compactos tipo 09.04-28.06.2026
    texto = _limpiar(soup.get_text(" ", strip=True))
    m = re.search(r"\b\d{1,2}\.\d{1,2}\s*[-–]\s*\d{1,2}\.\d{1,2}\.20\d{2}\b", texto)
    if m:
        return _limpiar(m.group(0))

    # Luego etiquetas habituales
    for etiqueta in ["Fecha", "Fechas", "Fecha y hora", "Fecha y Hora"]:
        val = _extraer_valor_por_etiqueta(lineas, etiqueta)
        if val:
            return val

    # Fallback: línea con mes natural
    for linea in lineas:
        low = _normalizar(linea)
        if re.search(r"\d{1,2}\s+de\s+[a-z]+", low):
            return linea

    return ""


def _extraer_horario_ficha(lineas):
    for etiqueta in ["Horario", "Horarios"]:
        val = _extraer_valor_por_etiqueta(lineas, etiqueta)
        if val:
            return val

    # fallback: línea tipo "De martes a domingo"
    for linea in lineas:
        low = _normalizar(linea)
        if "martes" in low and "domingo" in low:
            return linea

    return ""


def _extraer_info_ficha(session, url_ficha, texto_fallback=""):
    try:
        r = get_url(url_ficha, session=session, timeout=20)
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    lineas = [_limpiar(x) for x in soup.get_text("\n", strip=True).splitlines() if _limpiar(x)]

    titulo = _extraer_titulo_ficha(soup)
    fecha_txt = _extraer_fecha_ficha(soup, lineas)
    horario_txt = _extraer_horario_ficha(lineas)

    info_fecha = _resolver_info_fecha(fecha_txt, horario_txt, texto_fallback)

    if not titulo or not info_fecha:
        return None

    return {
        "titulo": titulo,
        "info_fecha": info_fecha,
    }


# -------------------------
# SCRAPER
# -------------------------

def sacar_lazarogaldiano():
    eventos = []
    vistos = set()
    session = requests.Session()

    urls_fichas = []
    vistos_urls = set()

    for nombre_seccion, url_seccion in SECCIONES:
        try:
            r = get_url(url_seccion, session=session, timeout=20)
        except Exception:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for url in _extraer_urls_seccion(soup):
            if url in vistos_urls:
                continue
            vistos_urls.add(url)
            urls_fichas.append((url, nombre_seccion))

    for url_ficha, nombre_seccion in urls_fichas:
        try:
            info = _extraer_info_ficha(session, url_ficha, texto_fallback=nombre_seccion)
            if not info:
                continue

            agregar_evento(
                eventos=eventos,
                vistos=vistos,
                titulo=info["titulo"],
                fecha_evento=info["info_fecha"]["fecha"],
                lugar=LUGAR,
                url_evento=url_ficha,
                fuente=FUENTE,
                info_fecha=info["info_fecha"],
            )
        except Exception as e:
            print(f"[AVISO] Error en Museo Lázaro Galdiano {url_ficha}: {e}")

    return eventos