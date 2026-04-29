import json
import re
from datetime import date

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url


PROGRAMACION_URL = "https://www.salanazcaconciertos.com/conciertos"
PGID_PREFIX = "kx9e3n0n"


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


def _construir_fecha(dia, mes, anio):
    try:
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def _anio_probable_para_mes(mes_num):
    hoy = date.today()
    anio = hoy.year
    if mes_num < hoy.month - 1:
        anio += 1
    return anio


def _parsear_fecha_nazca(texto):
    t = _limpiar(texto)
    if not t:
        return None

    m = re.fullmatch(
        r"(\d{1,2})\s+(?:de\s+)?([A-Za-zÁÉÍÓÚáéíóúñÑ]+)",
        t,
        re.IGNORECASE,
    )
    if not m:
        return None

    dia = int(m.group(1))
    mes_num = _mes_a_num(m.group(2))
    if not mes_num:
        return None

    anio = _anio_probable_para_mes(mes_num)
    f = _construir_fecha(dia, mes_num, anio)
    if not f:
        return None

    return {
        "tipo": "unica",
        "fecha": f.isoformat(),
        "fecha_inicio": f.isoformat(),
        "fecha_fin": f.isoformat(),
        "fechas_funcion": [f.isoformat()],
        "dias_semana": [],
        "texto_fecha_original": t,
    }


def _parsear_titulo_y_fecha(texto):
    t = _limpiar(texto)
    if not t:
        return None, None

    m = re.search(
        r"^(.*?)\s*-\s*(\d{1,2}\s+(?:de\s+)?[A-Za-zÁÉÍÓÚáéíóúñÑ]+)$",
        t,
        re.IGNORECASE,
    )
    if not m:
        return None, None

    titulo = _limpiar(m.group(1))
    fecha_txt = _limpiar(m.group(2))
    titulo = re.sub(r"\s*-\s*$", "", titulo)

    info_fecha = _parsear_fecha_nazca(fecha_txt)
    if not titulo or not info_fecha:
        return None, None

    return titulo, info_fecha


def _buscar_gallery_items_recursivo(obj):
    encontrados = []

    if isinstance(obj, dict):
        for clave, valor in obj.items():
            if (
                isinstance(clave, str)
                and clave.endswith("_galleryData")
                and isinstance(valor, dict)
                and isinstance(valor.get("items"), list)
            ):
                encontrados.extend(valor["items"])

            encontrados.extend(_buscar_gallery_items_recursivo(valor))

    elif isinstance(obj, list):
        for x in obj:
            encontrados.extend(_buscar_gallery_items_recursivo(x))

    return encontrados


def _extraer_items_wix_warmup(html):
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="wix-warmup-data")
    if not script:
        return []

    raw = script.get_text(strip=False)
    if not raw:
        return []

    raw = raw.strip()

    try:
        data = json.loads(raw)
    except Exception:
        try:
            data = json.loads(raw.encode("utf-8", "ignore").decode("utf-8"))
        except Exception:
            return []

    items = _buscar_gallery_items_recursivo(data)

    dedup = []
    vistos = set()
    for item in items:
        item_id = _limpiar((item or {}).get("itemId", ""))
        if item_id and item_id in vistos:
            continue
        if item_id:
            vistos.add(item_id)
        dedup.append(item)

    return dedup


def _construir_url_pgid(item_id):
    item_id = _limpiar(item_id)
    if not item_id:
        return ""
    return f"{PROGRAMACION_URL}?pgid={PGID_PREFIX}-{item_id}"


def _extraer_eventos_desde_items(items):
    eventos = []
    vistos = set()

    for item in items:
        meta = item.get("metaData") or {}
        titulo_raw = _limpiar(meta.get("title", ""))
        if not titulo_raw:
            continue

        titulo, info_fecha = _parsear_titulo_y_fecha(titulo_raw)
        if not titulo or not info_fecha:
            continue

        item_id = _limpiar(item.get("itemId", ""))
        url_evento = _construir_url_pgid(item_id)

        if not url_evento:
            link = meta.get("link") or {}
            data = link.get("data") or {}
            url_evento = _limpiar(data.get("url", ""))

        if not url_evento:
            url_evento = f"{PROGRAMACION_URL}#evento-{_normalizar(titulo)}-{info_fecha['fecha']}"

        clave = (titulo.lower(), info_fecha["fecha"], url_evento.lower())
        if clave in vistos:
            continue
        vistos.add(clave)

        eventos.append({
            "titulo": titulo,
            "info_fecha": info_fecha,
            "url_evento": url_evento,
        })

    return eventos


def sacar_nazca():
    lugar = "Sala Nazca"
    fuente = PROGRAMACION_URL

    try:
        r = get_url(PROGRAMACION_URL, timeout=20)
    except Exception:
        return []

    items = _extraer_items_wix_warmup(r.text)
    eventos_extraidos = _extraer_eventos_desde_items(items)

    eventos = []
    vistos = set()

    for item in eventos_extraidos:
        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=item["titulo"],
            fecha_evento=item["info_fecha"]["fecha"],
            lugar=lugar,
            url_evento=item["url_evento"],
            fuente=fuente,
            info_fecha=item["info_fecha"],
        )

    return eventos