import re
import unicodedata
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import agregar_evento, get_url


MUSICA_URL = "https://events.neptunopremium.com/es/musica"
LUGAR = "Estadio Metropolitano"


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

MESES_RE = (
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre"
)


# -------------------------
# HELPERS TEXTO / FECHA
# -------------------------

def limpiar_texto(texto):
    return " ".join(str(texto or "").split()).strip()


def normalizar_texto(texto):
    t = limpiar_texto(texto).lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t


def construir_fecha(dia, mes_txt, anio):
    mes = MESES.get(normalizar_texto(mes_txt))
    if not mes:
        return None

    try:
        return date(int(anio), mes, int(dia))
    except Exception:
        return None


def info_unica_local(f, texto_original=""):
    if not f:
        return None

    iso = f.isoformat()

    return {
        "tipo": "unica",
        "tipo_fecha": "unica",
        "fecha": iso,
        "fecha_inicio": iso,
        "fecha_fin": iso,
        "fechas_funcion": [iso],
        "dias_semana": [],
        "texto_fecha_original": limpiar_texto(texto_original),
    }


def info_lista_local(fechas, texto_original=""):
    fechas = sorted(set(f for f in fechas if f))
    if not fechas:
        return None

    fechas_iso = [f.isoformat() for f in fechas]

    return {
        "tipo": "lista" if len(fechas_iso) > 1 else "unica",
        "tipo_fecha": "lista" if len(fechas_iso) > 1 else "unica",
        "fecha": fechas_iso[0],
        "fecha_inicio": fechas_iso[0],
        "fecha_fin": fechas_iso[-1],
        "fechas_funcion": fechas_iso,
        "dias_semana": [],
        "texto_fecha_original": limpiar_texto(texto_original),
    }


def _extraer_anio_contexto(texto):
    """
    En la portada de música hablamos de próximos conciertos 2026, pero aun así
    priorizamos el año que aparece dentro de la frase de fecha.
    """
    anios = re.findall(r"\b(20\d{2})\b", normalizar_texto(texto))
    if not anios:
        return 2026

    if "2026" in anios:
        return 2026

    return int(anios[-1])


def _extraer_dias_de_grupo(dias_txt):
    """
    Convierte:
    - "30 y 31"
    - "2, 3, 6, 7, 10, 11, 14 y 15"
    en [30, 31] / [2, 3, 6, 7, 10, 11, 14, 15]
    """
    dias = []

    for x in re.findall(r"\b([0-3]?\d)\b", dias_txt or ""):
        n = int(x)
        if 1 <= n <= 31:
            dias.append(n)

    return dias


def _limpiar_lineas_articulo(lineas):
    """
    Quitamos líneas que suelen contener fechas que NO son del evento:
    publicación, venta, preventa, registro, etc.
    """
    limpias = []

    for linea in lineas:
        l = limpiar_texto(linea)
        if not l:
            continue

        ln = normalizar_texto(l)

        # Ejemplo publicación: "8 de mayo, 2025 - 15:26"
        if re.match(rf"^\d{{1,2}}\s+de\s+({MESES_RE}),?\s+20\d{{2}}\s*-", ln):
            continue

        if any(x in ln for x in {
            "preventa",
            "venta general",
            "entradas generales",
            "pondran a la venta",
            "pondran a la venta",
            "se pondran a la venta",
            "se pondrán a la venta",
            "ticketmaster",
            "livenation",
            "registrarse",
            "registro",
            "newsletter",
        }):
            continue

        limpias.append(l)

    return limpias


def extraer_fechas_concierto_desde_texto(texto):
    """
    Extrae fechas reales del concierto desde frases como:

    "El Riyadh Air Metropolitano acogerá los conciertos de Bad Bunny
    el próximo 30 y 31 de mayo y el 2, 3, 6, 7, 10, 11, 14 y 15
    de junio de 2026."

    También soporta:
    - "el próximo 20 de junio de 2026"
    - "los días 28, 29 y 30 de agosto de 2026"
    - "26 y 27 de junio de 2026"
    """
    if not texto:
        return []

    texto_original = limpiar_texto(texto)
    t = normalizar_texto(texto_original)

    # Nos quedamos preferentemente con frases que parecen hablar del evento,
    # no con todo el artículo.
    frases = re.split(r"(?<=[.!?])\s+", t)

    candidatas = []
    for frase in frases:
        if not re.search(r"\b\d{1,2}\b", frase):
            continue
        if not re.search(rf"\b({MESES_RE})\b", frase):
            continue

        # Frases buenas de evento.
        if any(x in frase for x in {
            "metropolitano",
            "riyadh air",
            "acogera",
            "acogerá",
            "concierto",
            "conciertos",
            "actuara",
            "actuará",
            "actuacion",
            "actuación",
            "sera el",
            "será el",
            "tendra lugar",
            "tendrá lugar",
            "proximo",
            "próximo",
            "proximos",
            "próximos",
            "los dias",
            "los días",
            "el dia",
            "el día",
        }):
            candidatas.append(frase)

    if not candidatas:
        candidatas = [t]

    fechas = set()

    for candidata in candidatas:
        anio_contexto = _extraer_anio_contexto(candidata)

        # Caso especial multimes:
        # 30 y 31 de mayo y el 2, 3, 6, 7, 10, 11, 14 y 15 de junio de 2026
        # Este regex encuentra cada bloque "días + mes + año opcional".
        for m in re.finditer(
            rf"((?:\d{{1,2}}\s*(?:,|y|e)?\s*)+)\s+de\s+({MESES_RE})(?:\s+(?:de\s+)?(20\d{{2}}))?",
            candidata,
            flags=re.I,
        ):
            dias_txt = m.group(1)
            mes_txt = m.group(2)
            anio = int(m.group(3)) if m.group(3) else anio_contexto

            for dia in _extraer_dias_de_grupo(dias_txt):
                f = construir_fecha(dia, mes_txt, anio)
                if f:
                    fechas.add(f)

    return sorted(fechas)


# -------------------------
# PORTADA
# -------------------------

def _limpiar_titulo_portada(texto):
    titulo = limpiar_texto(texto)

    # Neptuno suele pintar "BAD BUNNY Concierto".
    titulo = re.sub(r"\bconciertos?\b", "", titulo, flags=re.I)
    titulo = re.sub(r"\s+", " ", titulo).strip(" -–|")

    return titulo


def _es_url_noticia_evento(url_evento):
    if not url_evento:
        return False

    u = url_evento.lower()

    return (
        "atleticodemadrid.com/noticias/" in u
        or "atleticodemadrid.com/news/" in u
    )


def extraer_candidatos_portada(soup):
    candidatos = {}

    for a in soup.find_all("a", href=True):
        texto = limpiar_texto(a.get_text(" ", strip=True))
        href = (a.get("href") or "").strip()

        if not texto or not href:
            continue

        url_evento = urljoin(MUSICA_URL, href)

        if not _es_url_noticia_evento(url_evento):
            continue

        texto_norm = normalizar_texto(texto)

        # En música nos interesan los bloques actuales de "Concierto".
        # Evitamos "Conciertos" histórico cuando venga como listado antiguo.
        if "concierto" not in texto_norm:
            continue

        titulo = _limpiar_titulo_portada(texto)
        if not titulo or len(titulo) < 2:
            continue

        # Evita elementos de navegación.
        if normalizar_texto(titulo) in {
            "musica",
            "música",
            "eventos",
            "comprar",
            "mas informacion",
            "más informacion",
            "más información",
        }:
            continue

        if url_evento not in candidatos:
            candidatos[url_evento] = titulo

    return [
        {
            "titulo": titulo,
            "url_evento": url_evento,
        }
        for url_evento, titulo in candidatos.items()
    ]


# -------------------------
# FICHA / NOTICIA
# -------------------------

def extraer_titulo_ficha(soup):
    h1 = soup.find("h1")
    if h1:
        return limpiar_texto(h1.get_text(" ", strip=True))

    if soup.title:
        return limpiar_texto(soup.title.get_text(" ", strip=True).split("|")[0])

    return ""


def extraer_lineas_ficha(soup):
    return [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]


def extraer_textos_fecha_relevantes(soup, titulo_portada=None):
    """
    La fecha suele venir en el subtítulo o en el primer párrafo de la noticia,
    así que buscamos alrededor del H1 y en líneas con palabras clave.
    """
    lineas = _limpiar_lineas_articulo(extraer_lineas_ficha(soup))

    if not lineas:
        return []

    titulo_ficha = extraer_titulo_ficha(soup)
    idx_titulo = None

    for i, linea in enumerate(lineas):
        if titulo_ficha and normalizar_texto(linea) == normalizar_texto(titulo_ficha):
            idx_titulo = i
            break

    if idx_titulo is None and titulo_portada:
        titulo_norm = normalizar_texto(titulo_portada)
        for i, linea in enumerate(lineas):
            if titulo_norm and titulo_norm in normalizar_texto(linea):
                idx_titulo = i
                break

    textos = []

    if idx_titulo is not None:
        # Subtítulo previo + primeros párrafos.
        inicio = max(0, idx_titulo - 3)
        fin = min(len(lineas), idx_titulo + 12)
        textos.append(" ".join(lineas[inicio:fin]))

    for linea in lineas:
        ln = normalizar_texto(linea)

        if not re.search(r"\b\d{1,2}\b", ln):
            continue
        if not re.search(rf"\b({MESES_RE})\b", ln):
            continue

        if any(x in ln for x in {
            "metropolitano",
            "riyadh air",
            "acogera",
            "acogerá",
            "concierto",
            "conciertos",
            "actuara",
            "actuará",
            "proximo",
            "próximo",
            "proximos",
            "próximos",
            "los dias",
            "los días",
        }):
            textos.append(linea)

    # Fallback: texto completo limpio, pero solo si lo anterior no funcionó.
    if not textos:
        textos.append(" ".join(lineas[:80]))

    # Dedup
    out = []
    vistos = set()
    for t in textos:
        clave = normalizar_texto(t)
        if clave and clave not in vistos:
            vistos.add(clave)
            out.append(t)

    return out


def extraer_evento_desde_ficha(session, candidato):
    url_evento = candidato["url_evento"]
    titulo = candidato["titulo"]

    try:
        respuesta = get_url(url_evento, session=session, timeout=20)
    except Exception:
        return None

    soup = BeautifulSoup(respuesta.text, "html.parser")

    fechas = set()
    textos_usados = []

    for texto in extraer_textos_fecha_relevantes(soup, titulo_portada=titulo):
        fs = extraer_fechas_concierto_desde_texto(texto)
        if fs:
            fechas.update(fs)
            textos_usados.append(texto)

    info_fecha = info_lista_local(
        sorted(fechas),
        texto_original=" | ".join(textos_usados),
    )

    if not info_fecha:
        return None

    return {
        "titulo": titulo,
        "url_evento": url_evento,
        "info_fecha": info_fecha,
    }


# -------------------------
# SCRAPER
# -------------------------

def sacar_estadiometropolitano():
    """
    Scraper para:
    https://events.neptunopremium.com/es/musica

    La portada solo da el evento; la fecha real se resuelve abriendo
    cada noticia enlazada en atleticodemadrid.com.
    """
    eventos = []
    vistos = set()
    session = requests.Session()

    try:
        respuesta = get_url(MUSICA_URL, session=session, timeout=20)
    except Exception:
        return []

    soup = BeautifulSoup(respuesta.text, "html.parser")
    candidatos = extraer_candidatos_portada(soup)

    for candidato in candidatos:
        evento = extraer_evento_desde_ficha(session, candidato)
        if not evento:
            continue

        info_fecha = evento["info_fecha"]

        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=evento["titulo"],
            fecha_evento=info_fecha.get("fecha"),
            lugar=LUGAR,
            url_evento=evento["url_evento"],
            fuente=MUSICA_URL,
            info_fecha=info_fecha,
        )

    return eventos