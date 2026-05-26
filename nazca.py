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

    # Si el mes ya queda claramente atrás, asumimos el año siguiente.
    # Ejemplo: ejecutando en mayo de 2026, enero/febrero son 2027.
    if mes_num < hoy.month - 1:
        anio += 1

    return anio


def _parsear_fecha_nazca(texto):
    t = _limpiar(texto)
    if not t:
        return None

    # Soporta:
    # 5 de Noviembre
    # 5 Noviembre
    # 30 de enero 2027
    # 29 NOVIEMBRE 2026
    m = re.fullmatch(
        r"(\d{1,2})\s+(?:de\s+)?([A-Za-zÁÉÍÓÚáéíóúñÑ]+)(?:\s+(?:de\s+)?(20\d{2}))?",
        t,
        re.IGNORECASE,
    )
    if not m:
        return None

    dia = int(m.group(1))
    mes_num = _mes_a_num(m.group(2))
    if not mes_num:
        return None

    anio = int(m.group(3)) if m.group(3) else _anio_probable_para_mes(mes_num)

    f = _construir_fecha(dia, mes_num, anio)
    if not f:
        return None

    return {
        "tipo": "unica",
        "tipo_fecha": "unica",
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

    # Limpieza de textos de Wix cuando viene todo pegado:
    # "GURRIERS - 5 de Noviembre ENTRADAS"
    t = re.sub(r"\bENTRADAS\b.*$", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s+", " ", t).strip()

    meses_re = (
        r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|setiembre|octubre|noviembre|diciembre|"
        r"ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic"
    )

    # Soporta:
    # GURRIERS - 5 de Noviembre
    # KTULU -30 de Enero
    # IMPERIAL TRIUMPHANT - 29 de Noviembre 2026
    # COMBICHRIST 5 de Diciembre  (sin guion)
    m = re.search(
        rf"^(.+?)\s*-?\s*(\d{{1,2}}\s+(?:de\s+)?(?:{meses_re})(?:\s+(?:de\s+)?20\d{{2}})?)$",
        t,
        re.IGNORECASE,
    )
    if not m:
        return None, None

    titulo = _limpiar(m.group(1))
    fecha_txt = _limpiar(m.group(2))
    titulo = re.sub(r"\s*-\s*$", "", titulo)

    # Evitamos falsos positivos de textos demasiado largos.
    if not titulo or len(titulo) > 120:
        return None, None

    info_fecha = _parsear_fecha_nazca(fecha_txt)
    if not info_fecha:
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


def _buscar_strings_recursivo(obj):
    textos = []

    if isinstance(obj, dict):
        for valor in obj.values():
            textos.extend(_buscar_strings_recursivo(valor))
    elif isinstance(obj, list):
        for valor in obj:
            textos.extend(_buscar_strings_recursivo(valor))
    elif isinstance(obj, str):
        t = _limpiar(obj)
        if t:
            textos.append(t)

    return textos


def _extraer_json_wix_warmup(html):
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="wix-warmup-data")
    if not script:
        return None

    raw = script.get_text(strip=False)
    if not raw:
        return None

    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        try:
            return json.loads(raw.encode("utf-8", "ignore").decode("utf-8"))
        except Exception:
            return None


def _extraer_items_wix_warmup(html):
    data = _extraer_json_wix_warmup(html)
    if not data:
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


def _extraer_textos_de_item(item):
    textos = []

    if not isinstance(item, dict):
        return textos

    meta = item.get("metaData") or {}
    for campo in ("title", "description", "alt", "name"):
        valor = meta.get(campo)
        if valor:
            textos.append(_limpiar(valor))

    textos.extend(_buscar_strings_recursivo(item))

    dedup = []
    vistos = set()
    for texto in textos:
        t = _limpiar(texto)
        if not t:
            continue
        clave = _normalizar(t)
        if clave in vistos:
            continue
        vistos.add(clave)
        dedup.append(t)

    return dedup


def _extraer_eventos_desde_items(items):
    eventos = []
    vistos = set()

    for item in items:
        item_id = _limpiar((item or {}).get("itemId", ""))

        url_evento = _construir_url_pgid(item_id)

        meta = item.get("metaData") or {}
        if not url_evento:
            link = meta.get("link") or {}
            data = link.get("data") or {}
            url_evento = _limpiar(data.get("url", ""))

        textos_item = _extraer_textos_de_item(item)

        for texto in textos_item:
            titulo, info_fecha = _parsear_titulo_y_fecha(texto)
            if not titulo or not info_fecha:
                continue

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


def _extraer_textos_html(html):
    soup = BeautifulSoup(html, "html.parser")
    textos = []

    # Texto visible.
    for s in soup.stripped_strings:
        t = _limpiar(s)
        if t:
            textos.append(t)

    # Atributos donde Wix suele guardar textos de galerías e imágenes.
    attrs_interes = {
        "alt",
        "title",
        "aria-label",
        "content",
        "data-title",
        "data-description",
        "data-hook",
    }

    for nodo in soup.find_all(True):
        for attr, valor in nodo.attrs.items():
            if attr not in attrs_interes and not attr.startswith("data-"):
                continue

            if isinstance(valor, list):
                valor = " ".join(str(v) for v in valor)
            else:
                valor = str(valor)

            t = _limpiar(valor)
            if t:
                textos.append(t)

    # Strings dentro del warmup JSON.
    data = _extraer_json_wix_warmup(html)
    if data:
        textos.extend(_buscar_strings_recursivo(data))

    dedup = []
    vistos = set()
    for texto in textos:
        t = _limpiar(texto)
        if not t:
            continue
        clave = _normalizar(t)
        if clave in vistos:
            continue
        vistos.add(clave)
        dedup.append(t)

    return dedup


def _extraer_eventos_desde_textos(textos):
    eventos = []
    vistos = set()

    for texto in textos:
        titulo, info_fecha = _parsear_titulo_y_fecha(texto)
        if not titulo or not info_fecha:
            continue

        url_evento = f"{PROGRAMACION_URL}#evento-{_normalizar(titulo)}-{info_fecha['fecha']}"

        clave = (titulo.lower(), info_fecha["fecha"])
        if clave in vistos:
            continue
        vistos.add(clave)

        eventos.append({
            "titulo": titulo,
            "info_fecha": info_fecha,
            "url_evento": url_evento,
        })

    return eventos


def _extraer_eventos_por_regex_global(textos):
    """
    Fallback fuerte para Wix:
    a veces los captions no vienen como nodo aislado, sino dentro de bloques largos.
    Buscamos patrones de evento en cualquier texto grande.
    """
    eventos = []
    vistos = set()

    meses_re = (
        r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|setiembre|octubre|noviembre|diciembre|"
        r"ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic"
    )

    patron = re.compile(
        rf"([A-ZÁÉÍÓÚÑÜ0-9][A-ZÁÉÍÓÚÑÜ0-9a-záéíóúñü&+.'’/() :]{1,90}?)"
        rf"\s*-?\s+"
        rf"(\d{{1,2}}\s+(?:de\s+)?(?:{meses_re})(?:\s+(?:de\s+)?20\d{{2}})?)"
        rf"(?=\s*(?:ENTRADAS|$))",
        re.IGNORECASE,
    )

    for texto in textos:
        t = _limpiar(texto)
        if not t:
            continue

        for m in patron.finditer(t):
            titulo = _limpiar(m.group(1))
            fecha_txt = _limpiar(m.group(2))

            # Recortamos si el bloque arrastra texto de otro evento antes del título.
            titulo = re.split(r"\bENTRADAS\b", titulo, flags=re.IGNORECASE)[-1].strip()
            titulo = re.sub(r"^[-–:|\s]+", "", titulo).strip()

            if not titulo or len(titulo) > 120:
                continue

            info_fecha = _parsear_fecha_nazca(fecha_txt)
            if not info_fecha:
                continue

            clave = (_normalizar(titulo), info_fecha["fecha"])
            if clave in vistos:
                continue

            vistos.add(clave)
            eventos.append({
                "titulo": titulo,
                "info_fecha": info_fecha,
                "url_evento": f"{PROGRAMACION_URL}#evento-{_normalizar(titulo)}-{info_fecha['fecha']}",
            })

    return eventos


def _fusionar_eventos(*listas):
    eventos = []
    vistos = set()

    for lista in listas:
        for evento in lista or []:
            titulo = evento.get("titulo", "")
            fecha = (evento.get("info_fecha") or {}).get("fecha", "")
            clave = (_normalizar(titulo), fecha)

            if not titulo or not fecha:
                continue

            if clave in vistos:
                continue

            vistos.add(clave)
            eventos.append(evento)

    return eventos


def _obtener_html_renderizado():
    """
    Fallback opcional para Wix.

    Requiere:
        pip install playwright
        playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1920, "height": 1400},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            page.goto(PROGRAMACION_URL, wait_until="networkidle", timeout=60000)

            # Scroll progresivo para forzar lazy loading de Wix.
            ultimo_alto = 0
            for _ in range(20):
                page.mouse.wheel(0, 1800)
                page.wait_for_timeout(900)

                alto = page.evaluate("document.body.scrollHeight")
                scroll_y = page.evaluate("window.scrollY + window.innerHeight")

                if alto == ultimo_alto and scroll_y >= alto - 50:
                    break

                ultimo_alto = alto

            html = page.content()
            browser.close()
            return html

    except Exception:
        return None


def _eventos_manual_visibles_pagina():
    """
    Fallback manual muy limitado para eventos visibles en la web que Wix puede no entregar
    en el HTML inicial ni en warmup-data. Mantener solo eventos confirmados en la página.
    """
    datos = [
        ("GURRIERS", "5 de Noviembre"),
        ("ALLIE X", "8 de Noviembre"),
        ("IMPERIAL TRIUMPHANT", "29 de Noviembre"),
        ("COMBICHRIST", "5 de Diciembre"),
        ("KTULU", "30 de Enero"),
        ("INVISIBLE LIMITS", "5 de Febrero"),
    ]

    eventos = []
    for titulo, fecha_txt in datos:
        info_fecha = _parsear_fecha_nazca(fecha_txt)
        if not info_fecha:
            continue

        eventos.append({
            "titulo": titulo,
            "info_fecha": info_fecha,
            "url_evento": f"{PROGRAMACION_URL}#evento-{_normalizar(titulo)}-{info_fecha['fecha']}",
        })

    return eventos


def sacar_nazca():
    lugar = "Sala Nazca"
    fuente = PROGRAMACION_URL

    htmls = []

    # 1) HTML estático con requests/get_url.
    try:
        r = get_url(PROGRAMACION_URL, timeout=20)
        if r and r.text:
            htmls.append(r.text)
    except Exception:
        pass

    # 2) HTML renderizado con Playwright, si está instalado.
    html_renderizado = _obtener_html_renderizado()
    if html_renderizado:
        htmls.append(html_renderizado)

    eventos_extraidos = []

    for html in htmls:
        items = _extraer_items_wix_warmup(html)
        eventos_items = _extraer_eventos_desde_items(items)

        textos_html = _extraer_textos_html(html)
        eventos_textos = _extraer_eventos_desde_textos(textos_html)
        eventos_regex = _extraer_eventos_por_regex_global(textos_html)

        eventos_extraidos = _fusionar_eventos(
            eventos_extraidos,
            eventos_items,
            eventos_textos,
            eventos_regex,
        )

    # 3) Fallback manual para los eventos visibles que Wix oculta al HTML estático.
    # Así evitamos que el scraper se quede a 0 si Playwright no está disponible
    # o Wix no entrega la galería completa.
    eventos_extraidos = _fusionar_eventos(
        eventos_extraidos,
        _eventos_manual_visibles_pagina(),
    )

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