import requests
import re
from datetime import date
from urllib.parse import urljoin, urlparse, urldefrag
from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento


BASE_URL = "https://www.grupomarquina.es/"
LISTADO_URL = "https://www.grupomarquina.es/espectaculos/"
ENTRADAS_HOST = "entradas.grupomarquina.es"


# -------------------------
# HELPERS URL
# -------------------------

def normalizar_url_marquina(href):
    """
    Evita URLs rotas como:
    https://www.grupomarquina.es/espectaculos/https://entradas.grupomarquina.es/onbeat/events/55787

    y normaliza enlaces relativos/absolutos.
    """
    if not href:
        return None

    href = limpiar_texto(href).strip()
    href = href.replace(" ", "")

    if not href:
        return None

    # Si la web concatena por error un absoluto dentro de un path, nos quedamos
    # con el absoluto real de entradas.grupomarquina.es.
    for marcador in [
        "https://entradas.grupomarquina.es/",
        "http://entradas.grupomarquina.es/",
    ]:
        pos = href.find(marcador)
        if pos > 0:
            href = href[pos:]
            break

    if href.startswith("//"):
        href = "https:" + href

    url = urljoin(LISTADO_URL, href)
    url, _ = urldefrag(url)

    # Segundo saneo por si urljoin ya produjo una URL concatenada.
    for marcador in [
        "https://entradas.grupomarquina.es/",
        "http://entradas.grupomarquina.es/",
    ]:
        pos = url.find(marcador)
        if pos > 0:
            url = url[pos:]
            break

    return url.rstrip("/")


def es_url_ficha_interna(url):
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    return (
        parsed.netloc.lower() == "www.grupomarquina.es"
        and path.startswith("/espectaculos/")
        and path != "/espectaculos"
    )


def es_url_onbeat_evento(url):
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    return (
        parsed.netloc.lower() == ENTRADAS_HOST
        and re.search(r"/onbeat/events/\d+$", path) is not None
    )


def es_url_evento_valida(url):
    if not url:
        return False

    url_low = url.lower()

    if "gift-card" in url_low:
        return False

    if url_low.rstrip("/") == "https://entradas.grupomarquina.es/onbeat/events":
        return False

    return es_url_ficha_interna(url) or es_url_onbeat_evento(url)


# -------------------------
# HELPERS FECHA
# -------------------------

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


def parsear_rango_marquina(texto):
    """
    Formatos:
    - 29/05/2026 - 29/05/2026
    - 15/04/2026 - 24/05/2026
    - 01/09/2025 - 31/05/2026
    """
    if not texto:
        return None

    t = limpiar_texto(texto)

    m = re.fullmatch(
        r"(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4})",
        t
    )
    if not m:
        return None

    try:
        fi = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        ff = date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
    except Exception:
        return None

    if fi == ff:
        return {
            "tipo_fecha": "unica",
            "fecha": fi.isoformat(),
            "fecha_inicio": fi.isoformat(),
            "fecha_fin": ff.isoformat(),
            "fechas_funcion": [fi.isoformat()],
            "dias_semana": [],
            "texto_fecha_original": t,
        }

    return {
        "tipo_fecha": "rango",
        "fecha": fi.isoformat(),
        "fecha_inicio": fi.isoformat(),
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": t,
    }


def parsear_fecha_texto_marquina(texto):
    """
    Formatos de entradas.grupomarquina.es/onbeat:
    - 11 de junio de 2026, 21:00
    - 11 junio 2026
    """
    if not texto:
        return None

    t = limpiar_texto(texto).lower()

    m = re.search(
        r"\b(\d{1,2})\s*(?:de\s*)?"
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
        r"\s*(?:de\s*)?(\d{4})\b",
        t,
        re.I
    )
    if not m:
        return None

    try:
        f = date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)))
    except Exception:
        return None

    return {
        "tipo_fecha": "unica",
        "fecha": f.isoformat(),
        "fecha_inicio": f.isoformat(),
        "fecha_fin": f.isoformat(),
        "fechas_funcion": [f.isoformat()],
        "dias_semana": [],
        "texto_fecha_original": limpiar_texto(m.group(0)),
    }


def extraer_fecha_rango_texto(texto):
    texto = limpiar_texto(texto or "")
    m = re.search(r"\b\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}\b", texto)
    return limpiar_texto(m.group(0)) if m else None


def info_fecha_esta_pasada(info_fecha):
    if not info_fecha:
        return True

    fecha_fin = info_fecha.get("fecha_fin") or info_fecha.get("fecha")
    if not fecha_fin:
        return False

    try:
        return date.fromisoformat(fecha_fin) < date.today()
    except Exception:
        return False


# -------------------------
# PORTADA / LISTADO
# -------------------------

def extraer_lugar_desde_texto(texto):
    texto_low = limpiar_texto(texto).lower()

    if "teatro príncipe gran vía" in texto_low or "teatro principe gran via" in texto_low:
        return "Teatro Príncipe Gran Vía"

    if "teatro marquina" in texto_low:
        return "Teatro Marquina"

    return None


def es_titulo_ruido_marquina(titulo):
    if not titulo:
        return True

    t = limpiar_texto(titulo).lower()

    if not t:
        return True

    return t in {
        "espectáculos grupo marquina",
        "espectaculos grupo marquina",
        "cartelera de teatro en madrid",
        "más información",
        "mas información",
        "mas informacion",
        "+ información",
        "+ informacion",
        "comprar entradas",
        "entradas",
        "credit_card entradas",
        "información",
        "informacion",
        "sesiones",
    }


def limpiar_titulo_candidato_marquina(titulo):
    if not titulo:
        return None

    t = limpiar_texto(titulo)

    # Muchas imágenes/alt pueden venir como:
    # "Entradas MANU TENORIO, Madrid | Venta Oficial"
    t = re.sub(r"^entradas\s+", "", t, flags=re.I)
    t = re.sub(r",\s*madrid\s*\|\s*venta oficial.*$", "", t, flags=re.I)
    t = re.sub(r"\|\s*venta oficial.*$", "", t, flags=re.I)

    # Si el alt/title trae textos largos con fecha/lugar, cortamos antes.
    t = re.split(r"\bcalendar_today\b|\blocation_on\b|\bDesde\b", t, flags=re.I)[0]
    t = limpiar_texto(t)

    if es_titulo_ruido_marquina(t):
        return None

    return t or None


def extraer_titulo_desde_atributos(nodo):
    """
    En Grupo Marquina muchos eventos de entradas externas aparecen como imagen
    o tarjeta sin texto visible. El título suele estar en alt/title/aria-label.
    """
    if not nodo:
        return None

    atributos = ["alt", "title", "aria-label", "data-title", "data-name", "data-event-name"]

    for selector in ["img", "a", "[alt]", "[title]", "[aria-label]", "[data-title]", "[data-name]", "[data-event-name]"]:
        for el in nodo.select(selector):
            for attr in atributos:
                valor = el.get(attr)
                titulo = limpiar_titulo_candidato_marquina(valor)
                if titulo:
                    return titulo

    return None


def contar_rangos_fecha(texto):
    return len(re.findall(r"\b\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}\b", texto or ""))


def encontrar_bloque_evento(anchor):
    """
    Sube por los ancestros hasta encontrar el bloque más pequeño que contiene:
    - una fecha rango
    - un teatro
    Evita quedarse con contenedores enormes de toda la página.
    """
    nodo = anchor

    for _ in range(10):
        if not nodo or getattr(nodo, "name", None) in {"html", "body"}:
            break

        texto = limpiar_texto(nodo.get_text(" ", strip=True))
        if not texto:
            nodo = nodo.parent
            continue

        tiene_fecha = extraer_fecha_rango_texto(texto)
        tiene_lugar = extraer_lugar_desde_texto(texto)

        if tiene_fecha and tiene_lugar:
            # Si contiene muchas fechas, seguramente es un contenedor global,
            # no una tarjeta individual.
            if contar_rangos_fecha(texto) <= 2 and len(texto) <= 2500:
                return nodo

        nodo = nodo.parent

    return None


def extraer_titulo_desde_bloque(bloque):
    if not bloque:
        return None

    for selector in ["h3", "h2", "h1", ".title", ".titulo"]:
        el = bloque.select_one(selector)
        if not el:
            continue

        titulo = limpiar_titulo_candidato_marquina(el.get_text(" ", strip=True))
        if titulo:
            return titulo

    titulo_atributos = extraer_titulo_desde_atributos(bloque)
    if titulo_atributos:
        return titulo_atributos

    return None


def extraer_candidatos_portada(soup):
    candidatos = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        url = normalizar_url_marquina(a.get("href"))

        if not es_url_evento_valida(url):
            continue

        if url in vistos:
            continue

        bloque = encontrar_bloque_evento(a)
        texto_bloque = limpiar_texto(bloque.get_text(" ", strip=True)) if bloque else ""

        fecha_txt = extraer_fecha_rango_texto(texto_bloque)
        lugar = extraer_lugar_desde_texto(texto_bloque)
        titulo = extraer_titulo_desde_bloque(bloque)

        if not titulo:
            titulo = extraer_titulo_desde_atributos(a)

        texto_anchor = limpiar_texto(a.get_text(" ", strip=True))
        if not titulo:
            titulo = limpiar_titulo_candidato_marquina(texto_anchor)

        # Si seguimos sin título, probablemente es una tarjeta externa cuya imagen
        # no trae alt/title accesible. La descartamos para evitar registros falsos
        # tipo "Espectáculos Grupo Marquina".
        if not titulo:
            continue

        vistos.add(url)
        candidatos.append({
            "titulo_portada": titulo,
            "lugar_portada": lugar,
            "fecha_txt_portada": fecha_txt,
            "url": url,
        })

    return candidatos


# -------------------------
# FICHA
# -------------------------

def limpiar_titulo_ficha(titulo):
    if not titulo:
        return None

    t = limpiar_texto(titulo)

    # Onbeat:
    # Entradas MANU TENORIO, Madrid | Venta Oficial
    t = re.sub(r"^entradas\s+", "", t, flags=re.I)
    t = re.sub(r",\s*madrid\s*\|\s*venta oficial.*$", "", t, flags=re.I)
    t = re.sub(r"\|\s*venta oficial.*$", "", t, flags=re.I)

    return limpiar_texto(t) or None


def extraer_titulo_ficha(soup):
    for selector in ["h1", "h2"]:
        el = soup.find(selector)
        if el:
            texto = limpiar_titulo_ficha(el.get_text(" ", strip=True))
            if texto and texto.lower() not in {
                "información",
                "informacion",
                "sesiones",
                "espectáculos grupo marquina",
                "espectaculos grupo marquina",
            }:
                return texto

    return None


def extraer_lugar_ficha(lineas):
    texto_total = " ".join(lineas).lower()

    if "teatro príncipe gran vía" in texto_total or "teatro principe gran via" in texto_total:
        return "Teatro Príncipe Gran Vía"

    if "teatro marquina" in texto_total:
        return "Teatro Marquina"

    return None


def extraer_fecha_ficha(lineas):
    texto_total = " ".join(lineas)

    fecha_rango = extraer_fecha_rango_texto(texto_total)
    if fecha_rango:
        return fecha_rango

    info_fecha = parsear_fecha_texto_marquina(texto_total)
    if info_fecha:
        return info_fecha.get("texto_fecha_original")

    return None


def extraer_info_ficha(session, url_ficha):
    try:
        r = get_url(url_ficha, session=session, timeout=20)
    except Exception as e:
        print(f"[AVISO] No se pudo abrir ficha Grupo Marquina: {url_ficha} -> {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    lineas = [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]

    titulo = extraer_titulo_ficha(soup)
    lugar = extraer_lugar_ficha(lineas)
    fecha_txt = extraer_fecha_ficha(lineas)

    return {
        "titulo": titulo,
        "lugar": lugar,
        "fecha_txt": fecha_txt,
    }


def parsear_fecha_marquina(fecha_txt):
    return parsear_rango_marquina(fecha_txt) or parsear_fecha_texto_marquina(fecha_txt)


# -------------------------
# SCRAPER
# -------------------------

def sacar_grupomarquina():
    eventos = []
    vistos = set()
    session = requests.Session()

    respuesta = get_url(LISTADO_URL, session=session, timeout=20)
    soup = BeautifulSoup(respuesta.text, "html.parser")

    candidatos = extraer_candidatos_portada(soup)

    for candidato in candidatos:
        try:
            url_ficha = candidato.get("url")
            titulo_portada = candidato.get("titulo_portada")
            lugar_portada = candidato.get("lugar_portada")
            fecha_txt_portada = candidato.get("fecha_txt_portada")

            if not url_ficha:
                continue

            if not es_url_evento_valida(url_ficha):
                continue

            # Las fichas de entradas.grupomarquina.es/onbeat pueden devolver 403
            # a requests aunque estén enlazadas desde la portada. Para esos casos,
            # usamos los datos de la tarjeta del listado y no intentamos abrir la ficha.
            if es_url_onbeat_evento(url_ficha):
                info_ficha = {}
            else:
                info_ficha = extraer_info_ficha(session, url_ficha) or {}

            titulo = info_ficha.get("titulo") or titulo_portada
            lugar = info_ficha.get("lugar") or lugar_portada
            fecha_txt = info_ficha.get("fecha_txt") or fecha_txt_portada

            if not titulo or not lugar or not fecha_txt:
                continue

            # Evita falsos títulos del listado o botones.
            if es_titulo_ruido_marquina(titulo):
                continue

            info_fecha = parsear_fecha_marquina(fecha_txt)
            if not info_fecha:
                continue

            if info_fecha_esta_pasada(info_fecha):
                continue

            agregar_evento(
                eventos,
                vistos,
                titulo,
                info_fecha.get("fecha"),
                lugar,
                url_ficha,
                LISTADO_URL,
                info_fecha=info_fecha
            )

        except Exception as e:
            print(f"[AVISO] Error en Grupo Marquina: {e}")

    return eventos