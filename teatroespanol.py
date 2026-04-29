import json
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url


BASE_URL = "https://www.teatroespanol.es"
PROGRAMACION_URL = f"{BASE_URL}/programacion"

# URL AJAX que has localizado en Red/XHR.
# Solo cambiamos page=...
AJAX_URL_TEMPLATE = (
    "https://www.teatroespanol.es/views/ajax"
    "?_wrapper_format=drupal_ajax"
    "&view_name=schedule"
    "&view_display_id=schedule"
    "&view_args="
    "&view_path=/programacion"
    "&view_base_path=programacion"
    "&view_dom_id=f88884a96e911228c847a5c3558098a05982de6be837792a310c8b69374766f2"
    "&pager_element=0"
    "&page={page}"
    "&_drupal_ajax=1"
    "&ajax_page_state[theme]=teatroespanol_v2"
    "&ajax_page_state[theme_token]="
    "&ajax_page_state[libraries]=eJx1U1GW2yAMvJBj3msPxBMgE20AUYSTeE9fOU6y3bX7Y0szQrZmhMPesVm8VxYMdqKkqZgAHSv5i8aDOy6JWLBBGlyCz8U44hE-4D445i69QbUOWiM2E7e8R2NiB-kkfUlU4p5X9CJ7OKMIRBSbKJ774Dlxc3w3r-ALwTvkmvD3G7FCK2ATQzDrQ5mGejJXLli6jD-_djplLPNWFtpcIY3aLEEVHFQgSLBgMw7PcCVWoXC2nvlCaNemiaB4NEfg2h-HCTx2eXXesvFKeJPTQ8mJ-pWCmOf7nVOhPkTmqMN0iCbq42e-efENzMPHnxnbYgPWhl4NVi_n4jtxkbcfvlHt8i7lW4kNAponkDCCX4YcLHiPQo4SdXUfdFVKWHE_S-dst3HsjULEbqDWtFg3987F-jP6y2rIRq6HOkJvjFKhcDIwB-I9_Fq4HFTJzMXIeZWxOPvMt9c_gCRd4UEW6Zj1H9W2bx3t9Zdxif1l3ByS_9EPU8YtLhru6zwknR_anpm4dLihcD74-koedPtxOXZ84YAjqHNXFX-Uip4m8lYQmj_vyzd8xBKpHPzEOp2SnfqhBA_6eOoHJepnmBMOD5XMplXmL8hSmdadRavbpfdnKzm90NOG_gXrBcjP"
)


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


def _construir_fecha(dia, mes_txt, anio):
    mes = MESES.get(_normalizar(mes_txt))
    if not mes:
        return None

    try:
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def _es_url_evento(url):
    if not url:
        return False

    u = url.lower()
    if not u.startswith("https://www.teatroespanol.es/"):
        return False

    excluidos = [
        "/programacion",
        "/historico",
        "/archivo",
        "/contacto",
        "/prensa",
        "/search",
        "/buscar",
    ]
    return not any(x in u for x in excluidos)


def _extraer_fecha_desde_div(div_fecha, anio_defecto=None):
    """
    Soporta:
    <div class="date language--es"><span class="number">21</span> Mayo</div>
    <div class="date language--es"><span class="number">21</span> Junio <span class="number">2026</span></div>
    """
    if not div_fecha:
        return None

    texto = _limpiar(div_fecha.get_text(" ", strip=True))
    if not texto:
        return None

    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]+)(?:\s+(\d{4}))?", texto)
    if not m:
        return None

    dia = int(m.group(1))
    mes_txt = m.group(2)
    anio = int(m.group(3)) if m.group(3) else anio_defecto

    if not anio:
        return None

    return _construir_fecha(dia, mes_txt, anio)


def _parsear_show_content(bloque):
    """
    Espera estructura tipo:
    <div class="show-content">
      <div class="date-range">
        <div class="date language--es">...</div>
        <div class="date language--es">...</div>
      </div>
      <div class="field field-name-node-title">
        <span class="title"><a href="/hamlet01">Hamlet.01</a></span>
      </div>
    </div>
    """
    if not bloque:
        return None

    enlace = bloque.select_one(".field.field-name-node-title a")
    if not enlace:
        return None

    titulo = _limpiar(enlace.get_text(" ", strip=True))
    href = (enlace.get("href") or "").strip()
    url_evento = urljoin(BASE_URL, href)

    if not titulo or not href or not _es_url_evento(url_evento):
        return None

    fechas = bloque.select(".date-range .date")
    if len(fechas) < 2:
        return None

    # La segunda fecha suele traer el año
    texto_fin = _limpiar(fechas[1].get_text(" ", strip=True))
    m_anio = re.search(r"\b(20\d{2})\b", texto_fin)
    anio = int(m_anio.group(1)) if m_anio else None

    fecha_inicio = _extraer_fecha_desde_div(fechas[0], anio_defecto=anio)
    fecha_fin = _extraer_fecha_desde_div(fechas[1], anio_defecto=anio)

    if not fecha_inicio or not fecha_fin:
        return None

    # Evita históricos
    if fecha_fin < date.today():
        return None

    texto_fecha_original = _limpiar(
        " ".join(_limpiar(f.get_text(" ", strip=True)) for f in fechas)
    )

    return {
        "titulo": titulo,
        "url_evento": url_evento,
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
        "texto_fecha_original": texto_fecha_original,
    }


def _parsear_html_eventos(html):
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    eventos = []

    for bloque in soup.select("div.show-content"):
        evento = _parsear_show_content(bloque)
        if evento:
            eventos.append(evento)

    return eventos


def _extraer_htmls_de_respuesta_ajax(obj):
    """
    Drupal AJAX suele devolver una lista JSON con comandos.
    Buscamos recursivamente strings HTML que contengan 'show-content'
    o 'date-range'.
    """
    htmls = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            s = x.strip()
            if ("show-content" in s) or ("date-range" in s) or ("field-name-node-title" in s):
                htmls.append(s)

    walk(obj)
    return htmls


def _descargar_pagina_ajax(page):
    url = AJAX_URL_TEMPLATE.format(page=page)

    try:
        r = get_url(url, timeout=25)
    except Exception:
        return []

    try:
        payload = r.json()
    except Exception:
        try:
            payload = json.loads(r.text)
        except Exception:
            return []

    htmls = _extraer_htmls_de_respuesta_ajax(payload)
    eventos = []

    for html in htmls:
        eventos.extend(_parsear_html_eventos(html))

    return eventos


def sacar_teatroespanol():
    lugar = "Teatro Español"
    fuente = PROGRAMACION_URL

    eventos = []
    vistos = set()

    # 1) HTML inicial
    try:
        r = get_url(PROGRAMACION_URL, timeout=20)
        eventos_iniciales = _parsear_html_eventos(r.text)
    except Exception:
        eventos_iniciales = []

    # 2) Páginas AJAX adicionales
    # page=0 suele repetir o no aportar; arrancamos en 1.
    eventos_ajax = []
    paginas_sin_novedad = 0
    urls_vistas = {e["url_evento"] for e in eventos_iniciales}

    for page in range(1, 6):
        lote = _descargar_pagina_ajax(page)
        if not lote:
            paginas_sin_novedad += 1
            if paginas_sin_novedad >= 2:
                break
            continue

        nuevas = []
        for e in lote:
            if e["url_evento"] not in urls_vistas:
                nuevas.append(e)
                urls_vistas.add(e["url_evento"])

        if nuevas:
            eventos_ajax.extend(nuevas)
            paginas_sin_novedad = 0
        else:
            paginas_sin_novedad += 1
            if paginas_sin_novedad >= 2:
                break

    todos = eventos_iniciales + eventos_ajax

    # 3) Alta final con tu pipeline normal
    for e in todos:
        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=e["titulo"],
            fecha_evento=e["fecha_inicio"],
            lugar=lugar,
            url_evento=e["url_evento"],
            fuente=fuente,
            info_fecha={
                "tipo_fecha": "patron",
                "tipo": "patron",
                "fecha": e["fecha_inicio"],
                "fecha_inicio": e["fecha_inicio"],
                "fecha_fin": e["fecha_fin"],
                "fechas_funcion": [],
                "dias_semana": [1, 2, 3, 4, 5, 6],  # martes a domingo
                "texto_fecha_original": e["texto_fecha_original"],
            },
        )

    return eventos