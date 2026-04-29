import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url


BASE_URL = "https://www.ifema.es"
CALENDARIO_URL = f"{BASE_URL}/calendario/todos"


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


def _es_url_evento(url):
    if not url:
        return False

    u = url.lower()
    if not u.startswith(BASE_URL):
        return False

    excluidos = [
        "/calendario/todos",
        "/calendario",
        "/contacto",
        "/noticias",
        "/prensa",
        "/buscar",
        "/search",
        "/sobre-ifema",
    ]
    return not any(x == u.replace(BASE_URL, "") or x in u for x in excluidos)


def _parsear_fecha_ifema(texto):
    """
    Soporta:
    - 24/04/26
    - 25/04/26 a 26/04/26
    - 25/04/2026 al 26/04/2026
    - 9-11 JUN 2026
    - 9 JUN 2026
    """
    t = _limpiar(texto)
    if not t:
        return None

    # 25/04/2026 al 26/04/2026
    m = re.fullmatch(
        r"(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(?:a|al)\s+(\d{1,2})/(\d{1,2})/(\d{2,4})",
        t,
        re.IGNORECASE
    )
    if m:
        y1 = int(m.group(3))
        y2 = int(m.group(6))
        if y1 < 100:
            y1 += 2000
        if y2 < 100:
            y2 += 2000

        inicio = _fecha(m.group(1), m.group(2), y1)
        fin = _fecha(m.group(4), m.group(5), y2)
        if inicio and fin:
            return {
                "tipo": "rango",
                "fecha": inicio.isoformat(),
                "fecha_inicio": inicio.isoformat(),
                "fecha_fin": fin.isoformat(),
                "fechas_funcion": [],
                "dias_semana": [],
                "texto_fecha_original": t,
            }

    # 24/04/26
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", t)
    if m:
        y = int(m.group(3))
        if y < 100:
            y += 2000
        f = _fecha(m.group(1), m.group(2), y)
        if f:
            return {
                "tipo": "unica",
                "fecha": f.isoformat(),
                "fecha_inicio": f.isoformat(),
                "fecha_fin": f.isoformat(),
                "fechas_funcion": [f.isoformat()],
                "dias_semana": [],
                "texto_fecha_original": t,
            }

    # 9-11 JUN 2026
    m = re.fullmatch(
        r"(\d{1,2})\s*-\s*(\d{1,2})\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+(\d{4})",
        t,
        re.IGNORECASE
    )
    if m:
        mes = _mes_a_num(m.group(3))
        if mes:
            inicio = _fecha(m.group(1), mes, m.group(4))
            fin = _fecha(m.group(2), mes, m.group(4))
            if inicio and fin:
                return {
                    "tipo": "rango",
                    "fecha": inicio.isoformat(),
                    "fecha_inicio": inicio.isoformat(),
                    "fecha_fin": fin.isoformat(),
                    "fechas_funcion": [],
                    "dias_semana": [],
                    "texto_fecha_original": t,
                }

    # 9 JUN 2026
    m = re.fullmatch(
        r"(\d{1,2})\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+(\d{4})",
        t,
        re.IGNORECASE
    )
    if m:
        mes = _mes_a_num(m.group(2))
        if mes:
            f = _fecha(m.group(1), mes, m.group(3))
            if f:
                return {
                    "tipo": "unica",
                    "fecha": f.isoformat(),
                    "fecha_inicio": f.isoformat(),
                    "fecha_fin": f.isoformat(),
                    "fechas_funcion": [f.isoformat()],
                    "dias_semana": [],
                    "texto_fecha_original": t,
                }

    return None


def _extraer_fecha_ficha(url_evento):
    try:
        r = get_url(url_evento, timeout=20)
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    el = soup.select_one("div.hero-banner-date span")
    if el:
        info = _parsear_fecha_ifema(el.get_text(" ", strip=True))
        if info:
            return info

    candidatos = []
    for sel in [".hero-banner-date", ".event-date", ".date", ".fecha"]:
        for el in soup.select(sel):
            txt = _limpiar(el.get_text(" ", strip=True))
            if txt:
                candidatos.append(txt)

    for txt in soup.stripped_strings:
        txt = _limpiar(txt)
        if not txt:
            continue
        if "/" in txt or re.search(r"\b(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b", _normalizar(txt)):
            candidatos.append(txt)

    vistos = set()
    for txt in candidatos:
        if txt in vistos:
            continue
        vistos.add(txt)
        info = _parsear_fecha_ifema(txt)
        if info:
            return info

    return None


def _extraer_siguiente_pagina(soup):
    for a in soup.find_all("a", href=True):
        texto = _normalizar(a.get_text(" ", strip=True))
        title = _normalizar(a.get("title", ""))
        aria = _normalizar(a.get("aria-label", ""))

        if texto == "siguiente" or "siguiente" in title or "siguiente" in aria:
            href = (a.get("href") or "").strip()
            if href:
                return urljoin(BASE_URL, href)

    return None


def _buscar_cards_ifema(soup):
    """
    Card = bloque que contiene:
    - un .title
    - una .date
    - al menos un enlace interno a IFEMA
    """
    cards = []

    for bloque in soup.find_all(["article", "div", "li"]):
        if not bloque.select_one(".title"):
            continue
        if not bloque.select_one(".date"):
            continue

        tiene_link = False
        for a in bloque.find_all("a", href=True):
            url = urljoin(BASE_URL, (a.get("href") or "").strip())
            if _es_url_evento(url):
                tiene_link = True
                break

        if tiene_link:
            cards.append(bloque)

    return cards


def _extraer_titulo_card(bloque):
    el = bloque.select_one(".title span") or bloque.select_one(".title")
    if not el:
        return ""

    titulo = _limpiar(el.get_text(" ", strip=True))
    return titulo


def _extraer_fecha_card(bloque):
    # Primero intenta la fecha visible de la card
    for el in bloque.select(".date span, .date"):
        txt = _limpiar(el.get_text(" ", strip=True))
        info = _parsear_fecha_ifema(txt)
        if info:
            return info

    # fallback por textos del bloque
    textos = [_limpiar(x) for x in bloque.stripped_strings if _limpiar(x)]
    for txt in textos[:20]:
        info = _parsear_fecha_ifema(txt)
        if info:
            return info

    return None


def _extraer_url_card(bloque, titulo):
    """
    Busca la URL del evento dentro del bloque.
    Prioridad:
    1. anchor cuyo texto coincida con el título
    2. primer enlace interno válido del bloque
    """
    titulo_n = _normalizar(titulo)

    for a in bloque.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        url = urljoin(BASE_URL, href)
        texto = _limpiar(a.get_text(" ", strip=True))

        if not _es_url_evento(url):
            continue

        if _normalizar(texto) == titulo_n:
            return url

    for a in bloque.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        url = urljoin(BASE_URL, href)
        if _es_url_evento(url):
            return url

    return ""


def _extraer_eventos_pagina(url_pagina):
    try:
        r = get_url(url_pagina, timeout=20)
    except Exception:
        return [], None

    soup = BeautifulSoup(r.text, "html.parser")
    cards = _buscar_cards_ifema(soup)

    candidatos = []
    urls_vistas = set()

    for bloque in cards:
        titulo = _extraer_titulo_card(bloque)
        fecha_home = _extraer_fecha_card(bloque)

        if not titulo or not fecha_home:
            continue

        url_evento = _extraer_url_card(bloque, titulo)
        if not url_evento:
            continue

        if url_evento in urls_vistas:
            continue

        urls_vistas.add(url_evento)

        candidatos.append({
            "titulo": titulo,
            "url_evento": url_evento,
            "info_fecha_home": fecha_home,
        })

    next_url = _extraer_siguiente_pagina(soup)
    return candidatos, next_url


def sacar_ifema():
    lugar = "IFEMA MADRID"
    fuente = CALENDARIO_URL

    eventos = []
    vistos = set()
    paginas_vistas = set()
    urls_evento_vistas = set()

    url_actual = CALENDARIO_URL
    paginas_sin_novedad = 0

    for _ in range(20):
        if not url_actual or url_actual in paginas_vistas:
            break

        paginas_vistas.add(url_actual)

        lote, next_url = _extraer_eventos_pagina(url_actual)
        nuevas_en_pagina = 0

        for item in lote:
            if item["url_evento"] in urls_evento_vistas:
                continue

            urls_evento_vistas.add(item["url_evento"])
            nuevas_en_pagina += 1

            info_ficha = _extraer_fecha_ficha(item["url_evento"])
            info_final = info_ficha or item["info_fecha_home"]

            agregar_evento(
                eventos=eventos,
                vistos=vistos,
                titulo=item["titulo"],
                fecha_evento=info_final.get("fecha"),
                lugar=lugar,
                url_evento=item["url_evento"],
                fuente=fuente,
                info_fecha=info_final,
            )

        if nuevas_en_pagina == 0:
            paginas_sin_novedad += 1
        else:
            paginas_sin_novedad = 0

        if paginas_sin_novedad >= 2:
            break

        url_actual = next_url

    return eventos