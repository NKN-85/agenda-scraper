import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url


BASE_URL = "https://www.teatroabadia.com"
PROGRAMACION_URL = f"{BASE_URL}/temporada/2025-2026/"


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


def _limpiar(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()


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


def _fecha(dia, mes, anio):
    try:
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def _parsear_fecha_abadia(texto):
    """
    Soporta:
    - 9 abr – 10 may
    - 22 – 26 abr
    - 11 y 12 jun
    - 2 y 3 jul
    """
    t = _normalizar(texto)
    anio = 2026

    # 9 abr – 10 may
    m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)\s*[–-]\s*(\d{1,2})\s+([a-z]+)", t)
    if m:
        fi = _fecha(m.group(1), _mes_a_num(m.group(2)), anio)
        ff = _fecha(m.group(3), _mes_a_num(m.group(4)), anio)
        if fi and ff:
            return {
                "tipo": "rango",
                "fecha": fi.isoformat(),
                "fecha_inicio": fi.isoformat(),
                "fecha_fin": ff.isoformat(),
                "fechas_funcion": [],
                "dias_semana": [],
                "texto_fecha_original": texto,
            }

    # 22 – 26 abr
    m = re.fullmatch(r"(\d{1,2})\s*[–-]\s*(\d{1,2})\s+([a-z]+)", t)
    if m:
        mes = _mes_a_num(m.group(3))
        fi = _fecha(m.group(1), mes, anio)
        ff = _fecha(m.group(2), mes, anio)
        if fi and ff:
            return {
                "tipo": "rango",
                "fecha": fi.isoformat(),
                "fecha_inicio": fi.isoformat(),
                "fecha_fin": ff.isoformat(),
                "fechas_funcion": [],
                "dias_semana": [],
                "texto_fecha_original": texto,
            }

    # 11 y 12 jun
    m = re.fullmatch(r"(\d{1,2})\s+y\s+(\d{1,2})\s+([a-z]+)", t)
    if m:
        mes = _mes_a_num(m.group(3))
        f1 = _fecha(m.group(1), mes, anio)
        f2 = _fecha(m.group(2), mes, anio)
        fechas = [f.isoformat() for f in [f1, f2] if f]
        if fechas:
            return {
                "tipo": "lista",
                "fecha": fechas[0],
                "fecha_inicio": fechas[0],
                "fecha_fin": fechas[-1],
                "fechas_funcion": fechas,
                "dias_semana": [],
                "texto_fecha_original": texto,
            }

    return None


def _extraer_lugar_y_horario(article):
    lugar = "Teatro de la Abadía"
    horario_texto = ""

    dl = article.find("dl")
    if not dl:
        return lugar, horario_texto

    dts = dl.find_all("dt")
    for dt in dts:
        etiqueta = _normalizar(dt.get_text(" ", strip=True))
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue

        valor = _limpiar(dd.get_text(" ", strip=True))
        if not valor:
            continue

        if etiqueta == "lugar":
            lugar = f"Teatro de la Abadía - {valor}"
        elif etiqueta == "horario":
            horario_texto = valor

    return lugar, horario_texto


def _parsear_dias_semana_desde_horario(horario_texto):
    """
    Ejemplos:
    - De martes a sábado: 19:00 h Domingos: 18:30 h
    - Jueves y viernes: 19:30 h Sábados y domingos: 18:00 h
    - Viernes y sábado: 20:00 h
    """
    if not horario_texto:
        return []

    t = _normalizar(horario_texto)
    dias = set()

    # de martes a sábado
    for m in re.finditer(r"de\s+(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\s+a\s+(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)", t):
        d1 = DIAS_SEMANA.get(m.group(1))
        d2 = DIAS_SEMANA.get(m.group(2))
        if d1 is None or d2 is None:
            continue

        if d1 <= d2:
            for d in range(d1, d2 + 1):
                dias.add(d)
        else:
            # por si algún día hubiera rangos envolventes
            for d in list(range(d1, 7)) + list(range(0, d2 + 1)):
                dias.add(d)

    # jueves y viernes / sábados y domingos
    for m in re.finditer(r"(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\s+y\s+(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)", t):
        d1 = DIAS_SEMANA.get(m.group(1))
        d2 = DIAS_SEMANA.get(m.group(2))
        if d1 is not None:
            dias.add(d1)
        if d2 is not None:
            dias.add(d2)

    # domingos:
    for m in re.finditer(r"(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\s*:", t):
        d = DIAS_SEMANA.get(m.group(1))
        if d is not None:
            dias.add(d)

    return sorted(dias)


def _es_inside_article_activo(article):
    txt = _normalizar(article.get_text(" ", strip=True))
    if not txt:
        return False

    if "funcion finalizada" in txt or "función finalizada" in txt:
        return False

    if not article.select_one("h2.entry-title a[href]"):
        return False
    if not article.select_one("div.fecha-rep p"):
        return False

    return True


def sacar_abadia():
    fuente = PROGRAMACION_URL

    try:
        r = get_url(PROGRAMACION_URL, timeout=20)
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    eventos = []
    vistos = set()

    for article in soup.select("div.inside-article"):
        if not _es_inside_article_activo(article):
            continue

        a = article.select_one("h2.entry-title a[href]")
        fecha_el = article.select_one("div.fecha-rep p")

        if not a or not fecha_el:
            continue

        titulo = _limpiar(a.get_text(" ", strip=True))
        href = (a.get("href") or "").strip()
        url_evento = urljoin(BASE_URL, href)

        if not titulo or not url_evento:
            continue

        fecha_txt = _limpiar(fecha_el.get_text(" ", strip=True))
        info_fecha = _parsear_fecha_abadia(fecha_txt)
        if not info_fecha:
            continue

        lugar, horario_texto = _extraer_lugar_y_horario(article)
        dias_semana = _parsear_dias_semana_desde_horario(horario_texto)

        # Si es un rango y además tenemos horario por días, lo convertimos a patrón.
        if info_fecha.get("tipo") == "rango" and dias_semana:
            info_fecha = {
                "tipo": "patron",
                "fecha": info_fecha.get("fecha"),
                "fecha_inicio": info_fecha.get("fecha_inicio"),
                "fecha_fin": info_fecha.get("fecha_fin"),
                "fechas_funcion": [],
                "dias_semana": dias_semana,
                "texto_fecha_original": f"{fecha_txt} | {horario_texto}",
            }

        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=titulo,
            fecha_evento=info_fecha.get("fecha"),
            lugar=lugar,
            url_evento=url_evento,
            fuente=fuente,
            info_fecha=info_fecha,
        )

    return eventos