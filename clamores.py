import re
import requests
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url, limpiar_texto, construir_fecha_actual


BASE_URL = "https://www.salaclamores.es/calendario"
LUGAR = "Sala Clamores"

PATRON_SPANISH_DATETIME = re.compile(
    r"(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\s+"
    r"(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
    r"\s+(\d{1,2}:\d{2})",
    re.IGNORECASE,
)


def _es_url_evento_valida(url_evento):
    if not url_evento:
        return False

    u = url_evento.strip().lower()

    if not u.startswith("http"):
        return False

    if "/eventos/" not in u:
        return False

    if u.rstrip("/") == BASE_URL.rstrip("/"):
        return False

    return True


def _parsear_info_fecha_desde_texto(texto):
    t = limpiar_texto(texto)
    m = PATRON_SPANISH_DATETIME.search(t)
    if not m:
        return None

    dia = int(m.group(2))
    mes_txt = m.group(3)
    fecha = construir_fecha_actual(dia, mes_txt)
    if not fecha:
        return None

    return {
        "tipo_fecha": "unica",
        "fecha": fecha.isoformat(),
        "texto_fecha_original": f"{m.group(1)} {m.group(2)} de {m.group(3)} {m.group(4)}",
    }


def _extraer_titulo_desde_texto(texto):
    t = limpiar_texto(texto)
    m = PATRON_SPANISH_DATETIME.search(t)
    if not m:
        return ""

    titulo = limpiar_texto(t[m.end():])

    titulo = re.sub(r'^[\-\–\|\·"\']+', "", titulo)
    titulo = re.sub(r'[\-\–\|\·"\']+$', "", titulo)
    titulo = limpiar_texto(titulo)

    return titulo


def _extraer_items_pagina(soup, url_base):
    items = []
    vistos_url = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(url_base, a["href"].strip())
        if not _es_url_evento_valida(href):
            continue

        texto = limpiar_texto(a.get_text(" ", strip=True))
        if not texto:
            continue

        if href in vistos_url:
            continue

        if not PATRON_SPANISH_DATETIME.search(texto):
            continue

        vistos_url.add(href)
        items.append({
            "url_evento": href,
            "texto": texto,
        })

    return items


def sacar_clamores():
    eventos = []
    vistos = set()
    session = requests.Session()

    paginas_vacias = 0
    max_paginas = 8

    for pagina in range(1, max_paginas + 1):
        url = BASE_URL if pagina == 1 else f"{BASE_URL}?e5273e04_page={pagina}"

        try:
            respuesta = get_url(url, session=session, timeout=20)
        except Exception as e:
            print(f"[AVISO] Clamores fallo en página {pagina}: {e}")
            break

        soup = BeautifulSoup(respuesta.text, "html.parser")
        items = _extraer_items_pagina(soup, url)

        nuevos = 0

        for item in items:
            info_fecha = _parsear_info_fecha_desde_texto(item["texto"])
            if not info_fecha:
                continue

            titulo = _extraer_titulo_desde_texto(item["texto"])
            if not titulo or len(titulo) < 2:
                continue

            ok = agregar_evento(
                eventos=eventos,
                vistos=vistos,
                titulo=titulo,
                fecha_evento=info_fecha.get("fecha"),
                lugar=LUGAR,
                url_evento=item["url_evento"],
                fuente=BASE_URL,
                info_fecha=info_fecha,
            )

            if ok:
                nuevos += 1

        if nuevos == 0:
            paginas_vacias += 1
        else:
            paginas_vacias = 0

        if paginas_vacias >= 2:
            break

    return eventos