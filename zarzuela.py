import requests
import re
from datetime import date, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento


BASE_DOMAIN = "https://teatrodelazarzuela.inaem.gob.es"
FUENTE = "https://teatrodelazarzuela.inaem.gob.es/es/"
LUGAR = "Teatro de la Zarzuela"

SECCIONES = [
    ("Lírica", "https://teatrodelazarzuela.inaem.gob.es/es/temporada/lirica-2025-2026"),
    ("Conciertos", "https://teatrodelazarzuela.inaem.gob.es/es/temporada/conciertos-2025-2026"),
    ("Danza", "https://teatrodelazarzuela.inaem.gob.es/es/temporada/danza-2025-2026"),
    ("Ambigú", "https://teatrodelazarzuela.inaem.gob.es/es/temporada/ambigu-2025-2026"),
]

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


def _mes_a_num(mes):
    return MESES.get(_normalizar(mes))


def _fecha(dia, mes, anio):
    try:
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def _info_lista(fechas, texto_original=""):
    fechas = sorted(set(f for f in fechas if f))
    fechas = [f for f in fechas if f >= date.today()]

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


def _info_rango(fi, ff, texto_original=""):
    if not fi or not ff:
        return None

    if ff < date.today():
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


def _expandir_rango(fi, ff, excluir=None):
    excluir = set(excluir or [])
    fechas = []
    cursor = fi

    while cursor <= ff:
        if cursor.weekday() not in excluir:
            fechas.append(cursor)
        cursor += timedelta(days=1)

    return fechas


def _parsear_lista_dias_mismo_mes(texto):
    """
    Casos:
    - 22, 23, 24, 25, 26 de abril de 2026
    - 11, 12, 14, 15, 16, 17, 18, 19, 21 y 22 de julio de 2026
    - Viernes y sábado, 8 y 9 de mayo de 2026
    """
    t = _normalizar(texto)

    m = re.search(
        r"((?:\d{1,2}\s*,\s*)*(?:\d{1,2})(?:\s*y\s*\d{1,2})?)\s+de\s+([a-z]+)\s+de\s+(20\d{2})",
        t
    )
    if not m:
        return []

    dias_txt = m.group(1)
    mes_num = _mes_a_num(m.group(2))
    anio = int(m.group(3))

    if not mes_num:
        return []

    dias = [int(x) for x in re.findall(r"\d{1,2}", dias_txt)]
    fechas = []

    for d in dias:
        f = _fecha(d, mes_num, anio)
        if f:
            fechas.append(f)

    return fechas


def _parsear_rango(texto):
    """
    Casos:
    - Del 10 al 28 de junio de 2026
    - Del 17 de febrero al 11 de marzo de 2026
    """
    t = _normalizar(texto)

    m = re.search(r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})", t)
    if m:
        d1 = int(m.group(1))
        d2 = int(m.group(2))
        mes = _mes_a_num(m.group(3))
        anio = int(m.group(4))
        if mes:
            fi = _fecha(d1, mes, anio)
            ff = _fecha(d2, mes, anio)
            return fi, ff

    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-z]+)\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})",
        t
    )
    if m:
        d1 = int(m.group(1))
        mes1 = _mes_a_num(m.group(2))
        d2 = int(m.group(3))
        mes2 = _mes_a_num(m.group(4))
        anio = int(m.group(5))
        if mes1 and mes2:
            fi = _fecha(d1, mes1, anio)
            ff = _fecha(d2, mes2, anio)
            return fi, ff

    return None, None


def _extraer_excepciones(texto):
    """
    Ej:
    excepto lunes y martes
    """
    t = _normalizar(texto)
    excluir = set()

    if "excepto" not in t:
        return excluir

    zona = t.split("excepto", 1)[1]

    for nombre, idx in DIAS_SEMANA.items():
        if re.search(rf"\b{nombre}\b", zona):
            excluir.add(idx)

    return excluir


def _resolver_info_fecha_texto(texto):
    """
    Prioridad:
    1. listas explícitas de días
    2. rangos
    3. fecha única
    """
    texto = _limpiar(texto)
    if not texto:
        return None

    fechas_lista = _parsear_lista_dias_mismo_mes(texto)
    if fechas_lista:
        return _info_lista(fechas_lista, texto)

    fi, ff = _parsear_rango(texto)
    if fi and ff:
        excluir = _extraer_excepciones(texto)
        if excluir:
            fechas = _expandir_rango(fi, ff, excluir=excluir)
            return _info_lista(fechas, texto)

        return _info_rango(fi, ff, texto)

    f_unica = _parsear_fecha_unica(texto)
    if f_unica:
        return _info_unica(f_unica, texto)

    return None


def _parsear_fecha_unica(texto):
    t = _normalizar(texto)
    m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})", t)
    if not m:
        return None

    dia = int(m.group(1))
    mes = _mes_a_num(m.group(2))
    anio = int(m.group(3))

    if not mes:
        return None

    return _fecha(dia, mes, anio)


def _extraer_lineas(soup):
    return [
        _limpiar(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if _limpiar(x)
    ]


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


def _extraer_texto_fecha_ficha(soup):
    """
    Busca primero zonas compactas de fecha.
    Si no encuentra, usa líneas con meses y años.
    """
    candidatos = []

    for selector in [
        ".field--name-field-date",
        ".field-name-field-date",
        ".date",
        ".fecha",
        ".field--name-field-friendly-date",
        ".field-name-field-friendly-date",
    ]:
        for el in soup.select(selector):
            txt = _limpiar(el.get_text(" ", strip=True))
            if txt and re.search(r"20\d{2}", txt):
                candidatos.append(txt)

    lineas = _extraer_lineas(soup)

    for linea in lineas:
        low = _normalizar(linea)
        if re.search(r"20\d{2}", low) and any(mes in low for mes in MESES):
            candidatos.append(linea)

    # preferimos textos con listas o rangos
    candidatos = sorted(
        set(candidatos),
        key=lambda x: (
            0 if re.search(r"\d{1,2}\s*,", x) else 1,
            0 if "del " in _normalizar(x) else 1,
            len(x),
        )
    )

    return candidatos[0] if candidatos else ""


def _extraer_info_ficha(session, url_ficha):
    try:
        r = get_url(url_ficha, session=session, timeout=20)
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    titulo = _extraer_titulo_ficha(soup)
    texto_fecha = _extraer_texto_fecha_ficha(soup)
    info_fecha = _resolver_info_fecha_texto(texto_fecha)

    if not titulo or not info_fecha:
        return None

    return {
        "titulo": titulo,
        "info_fecha": info_fecha,
    }


def _extraer_eventos_seccion(session, nombre_seccion, url):
    eventos = []

    try:
        r = get_url(url, session=session, timeout=20)
    except Exception:
        return eventos

    soup = BeautifulSoup(r.text, "html.parser")

    for h3 in soup.select("h3"):
        a = h3.find("a", href=True)
        if not a:
            continue

        titulo_portada = _limpiar(a.get_text(" ", strip=True))
        href = (a.get("href") or "").strip()

        if not titulo_portada or not href:
            continue

        url_ficha = urljoin(BASE_DOMAIN, href)

        info = _extraer_info_ficha(session, url_ficha)

        if not info:
            # fallback: fecha cercana en portada
            texto_cercano = _limpiar(h3.parent.get_text(" ", strip=True)) if h3.parent else ""
            info_fecha = _resolver_info_fecha_texto(texto_cercano)
            if not info_fecha:
                continue

            eventos.append({
                "titulo": titulo_portada,
                "url_evento": url_ficha,
                "info_fecha": info_fecha,
                "seccion": nombre_seccion,
            })
            continue

        eventos.append({
            "titulo": info["titulo"] or titulo_portada,
            "url_evento": url_ficha,
            "info_fecha": info["info_fecha"],
            "seccion": nombre_seccion,
        })

    return eventos


def sacar_zarzuela():
    eventos = []
    vistos = set()
    session = requests.Session()

    for nombre_seccion, url in SECCIONES:
        for item in _extraer_eventos_seccion(session, nombre_seccion, url):
            agregar_evento(
                eventos=eventos,
                vistos=vistos,
                titulo=item["titulo"],
                fecha_evento=item["info_fecha"]["fecha"],
                lugar=LUGAR,
                url_evento=item["url_evento"],
                fuente=FUENTE,
                info_fecha=item["info_fecha"],
            )

    return eventos