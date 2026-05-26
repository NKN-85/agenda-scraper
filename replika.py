import requests
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento, construir_fecha


BASE_URL = "https://replikateatro.com/programacion/"
LUGAR = "Réplika Teatro"


# -------------------------
# HELPERS FECHA
# -------------------------

def info_unica_local(f, texto_original=""):
    if not f:
        return None

    return {
        "tipo_fecha": "unica",
        "tipo": "unica",
        "fecha": f.isoformat(),
        "fecha_inicio": f.isoformat(),
        "fecha_fin": f.isoformat(),
        "fechas_funcion": [f.isoformat()],
        "dias_semana": [],
        "texto_fecha_original": texto_original or "",
    }


def info_lista_local(fechas, texto_original=""):
    fechas = sorted(set(f for f in fechas if f))
    if not fechas:
        return None

    return {
        "tipo_fecha": "lista",
        "tipo": "lista",
        "fecha": fechas[0].isoformat(),
        "fecha_inicio": fechas[0].isoformat(),
        "fecha_fin": fechas[-1].isoformat(),
        "fechas_funcion": [f.isoformat() for f in fechas],
        "dias_semana": [],
        "texto_fecha_original": texto_original or "",
    }


def info_rango_local(fi, ff, texto_original=""):
    if not fi or not ff:
        return None

    return {
        "tipo_fecha": "rango",
        "tipo": "rango",
        "fecha": fi.isoformat(),
        "fecha_inicio": fi.isoformat(),
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": texto_original or "",
    }


def parsear_fecha_numerica_replika(texto):
    """
    Casos de ficha:
    - 07/12/2026 - 10:00h.
    - 08/12/2026
    """
    if not texto:
        return None

    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", texto)
    if not m:
        return None

    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except Exception:
        return None


def parsear_fecha_replika(texto):
    """
    Casos de portada:
    - 24 de abril 2026
    - 2 - 3 de mayo 2026
    - 23 de febrero - 7 de mayo 2026
    """
    if not texto:
        return None

    t = limpiar_texto(texto).lower()

    # 23 de febrero - 7 de mayo 2026
    m = re.fullmatch(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s*-\s*(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(20\d{2})",
        t
    )
    if m:
        anio = int(m.group(5))
        fi = construir_fecha(int(m.group(1)), m.group(2), anio)
        ff = construir_fecha(int(m.group(3)), m.group(4), anio)
        if fi and ff:
            return info_rango_local(fi, ff, texto)

    # 2 - 3 de mayo 2026
    m = re.fullmatch(
        r"(\d{1,2})\s*-\s*(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(20\d{2})",
        t
    )
    if m:
        anio = int(m.group(4))
        fechas = [
            construir_fecha(int(m.group(1)), m.group(3), anio),
            construir_fecha(int(m.group(2)), m.group(3), anio),
        ]
        fechas = [f for f in fechas if f]
        if len(fechas) == 2:
            return info_lista_local(fechas, texto)

    # 24 de abril 2026
    m = re.fullmatch(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(20\d{2})",
        t
    )
    if m:
        f = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        if f:
            return info_unica_local(f, texto)

    return None


def extraer_info_fecha_desde_linea(linea):
    """
    Línea tipo:
    Theodora Laird aka feeo / 24 de abril 2026
    Ewa Dziarnowska / 2 - 3 de mayo 2026
    ÉSKATON x Miguel Deblas / 23 de febrero - 7 de mayo 2026
    """
    if not linea:
        return None

    partes = [limpiar_texto(x) for x in linea.split("/") if limpiar_texto(x)]
    if not partes:
        return None

    # normalmente la fecha va al final tras la última barra
    candidata = partes[-1]
    return parsear_fecha_replika(candidata)


def extraer_lineas_soup(soup):
    return [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]


def extraer_info_fecha_desde_ficha(session, url_evento):
    """
    En Réplika algunas fichas tienen fechas reales en "Próximas fechas".
    Esas fechas deben tener prioridad sobre el rango de portada.

    Ejemplo:
    Próximas fechas:
    07/12/2026 - 10:00h.
    08/12/2026 - 10:00h.
    ...
    """
    if not url_evento:
        return None

    try:
        respuesta = get_url(url_evento, session=session, timeout=20)
    except Exception:
        return None

    soup = BeautifulSoup(respuesta.text, "html.parser")
    lineas = extraer_lineas_soup(soup)

    fechas = []
    texto_original = ""

    # Preferimos las fechas que aparecen debajo de "Próximas fechas".
    for i, linea in enumerate(lineas):
        if limpiar_texto(linea).lower().startswith("próximas fechas") or limpiar_texto(linea).lower().startswith("proximas fechas"):
            bloque = []
            for j in range(i + 1, min(i + 25, len(lineas))):
                l = limpiar_texto(lineas[j])
                f = parsear_fecha_numerica_replika(l)

                if f:
                    fechas.append(f)
                    bloque.append(l)
                    continue

                # Si ya hemos empezado a capturar fechas y aparece una línea sin fecha,
                # asumimos que termina el bloque.
                if fechas:
                    break

            texto_original = " | ".join(bloque)
            break

    # Fallback: si no hay cabecera, buscamos fechas numéricas en toda la ficha.
    if not fechas:
        bloque = []
        for linea in lineas:
            f = parsear_fecha_numerica_replika(linea)
            if f:
                fechas.append(f)
                bloque.append(linea)
        texto_original = " | ".join(bloque)

    fechas = sorted(set(fechas))

    if len(fechas) >= 2:
        return info_lista_local(fechas, texto_original)

    if len(fechas) == 1:
        return info_unica_local(fechas[0], texto_original)

    return None


# -------------------------
# SCRAPER
# -------------------------

def sacar_replika():
    eventos = []
    vistos = set()
    session = requests.Session()

    respuesta = get_url(BASE_URL, session=session, timeout=20)
    soup = BeautifulSoup(respuesta.text, "html.parser")

    lineas = [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]

    # Mapa de títulos -> URL de "Más información"
    enlaces_info = []
    for a in soup.find_all("a", href=True):
        texto = limpiar_texto(a.get_text(" ", strip=True))
        href = (a.get("href") or "").strip()

        if texto.lower() != "más información":
            continue
        if not href:
            continue

        enlaces_info.append(urljoin(BASE_URL, href))

    idx_url = 0

    for i, linea in enumerate(lineas):
        if linea.lower() != "más información":
            continue

        if i < 2:
            continue

        titulo = limpiar_texto(lineas[i - 2])
        linea_fecha = limpiar_texto(lineas[i - 1])

        # filtros de ruido
        if not titulo or len(titulo) < 3:
            continue
        if titulo.lower() in {
            "news!",
            "buscar:",
            "escuela",
            "sala de teatro",
            "newsletter",
            "actualidad",
        }:
            continue

        info_fecha_portada = extraer_info_fecha_desde_linea(linea_fecha)
        if not info_fecha_portada:
            continue

        if idx_url >= len(enlaces_info):
            continue

        url_evento = enlaces_info[idx_url]
        idx_url += 1

        # La ficha manda sobre la portada.
        # Así evitamos convertir rangos de portada en funciones diarias cuando la ficha
        # trae una lista real de "Próximas fechas".
        info_fecha_ficha = extraer_info_fecha_desde_ficha(session, url_evento)
        info_fecha = info_fecha_ficha or info_fecha_portada

        agregar_evento(
            eventos,
            vistos,
            titulo,
            info_fecha.get("fecha"),
            LUGAR,
            url_evento,
            BASE_URL,
            info_fecha=info_fecha
        )

    return eventos