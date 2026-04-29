import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url


BASE_URL = "https://www.teatroreal.es"
PROGRAMACION_URL = f"{BASE_URL}/es/temporada-actual"


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
    return MESES.get(_normalizar(mes_txt).strip("."))


def _fecha(dia, mes, anio):
    try:
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def _anio_2_a_4(anio):
    anio = int(anio)
    if anio < 100:
        return 2000 + anio
    return anio


def _parsear_fecha_corta(texto):
    t = _normalizar(texto)
    t = re.sub(r"^de\s+", "", t)

    m = re.search(r"(\d{1,2})\s+([a-z]+),\s*(\d{2,4})", t)
    if not m:
        return None

    dia = int(m.group(1))
    mes = _mes_a_num(m.group(2))
    anio = _anio_2_a_4(m.group(3))

    if not mes:
        return None

    f = _fecha(dia, mes, anio)
    return f.isoformat() if f else None


def _parsear_fecha_larga(texto):
    t = _normalizar(texto)
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if not m:
        return None

    dia = int(m.group(1))
    mes = _mes_a_num(m.group(2))
    anio = int(m.group(3))

    if not mes:
        return None

    f = _fecha(dia, mes, anio)
    return f.isoformat() if f else None


def _extraer_catalogo():
    try:
        r = get_url(PROGRAMACION_URL, timeout=30)
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    resultados = []
    vistos = set()

    for card in soup.select("div.wrap-swiper-content"):
        a = card.select_one("a.wrap-text-link[href]")
        title_el = card.select_one(".wrap-description .title")
        date_el = card.select_one(".wrap-date .day")
        tipo_el = card.select_one(".wrap-date .play-type")

        if not a or not title_el:
            continue

        url_evento = urljoin(BASE_URL, _limpiar(a.get("href", "")))
        titulo = _limpiar(title_el.get_text(" ", strip=True))
        fecha_home_txt = _limpiar(date_el.get_text(" ", strip=True)) if date_el else ""
        tipo_evento = _limpiar(tipo_el.get_text(" ", strip=True)) if tipo_el else ""

        if not titulo or not url_evento:
            continue

        clave = (titulo.lower(), url_evento.lower())
        if clave in vistos:
            continue
        vistos.add(clave)

        resultados.append({
            "titulo": titulo,
            "url_evento": url_evento,
            "fecha_home_txt": fecha_home_txt,
            "tipo_evento_txt": tipo_evento,
        })

    return resultados


def _extraer_fechas_ficha(url_evento):
    try:
        r = get_url(url_evento, timeout=30)
    except Exception:
        return {
            "titulo": "",
            "fechas_funcion": [],
            "fecha_inicio": None,
            "fecha_fin": None,
            "texto_fecha_original": "",
            "espacios": [],
        }

    soup = BeautifulSoup(r.text, "html.parser")

    titulo = ""
    h1 = soup.select_one("h1")
    if h1:
        titulo = _limpiar(h1.get_text(" ", strip=True))

    fechas_funcion = []
    vistos = set()
    espacios = []
    textos_originales = []

    for bloque in soup.select(".functions-show__block"):
        fecha_el = bloque.select_one(".functions-show__block--item-date p")
        if not fecha_el:
            continue

        fecha_txt = _limpiar(fecha_el.get_text(" ", strip=True))
        fecha_iso = _parsear_fecha_larga(fecha_txt)
        if not fecha_iso:
            continue

        if fecha_iso not in vistos:
            vistos.add(fecha_iso)
            fechas_funcion.append(fecha_iso)
            textos_originales.append(fecha_txt)

        espacio_el = bloque.select_one(".functions-show__block--item-space p")
        if espacio_el:
            espacio = _limpiar(espacio_el.get_text(" ", strip=True))
            if espacio and espacio not in espacios:
                espacios.append(espacio)

    fechas_funcion.sort()

    if fechas_funcion:
        return {
            "titulo": titulo,
            "fechas_funcion": fechas_funcion,
            "fecha_inicio": fechas_funcion[0],
            "fecha_fin": fechas_funcion[-1],
            "texto_fecha_original": " | ".join(textos_originales[:5]),
            "espacios": espacios,
        }

    hero_h3s = [_limpiar(x.get_text(" ", strip=True)) for x in soup.select(".wrap-content-hero h3")]
    hero_fecha = None
    hero_texto = ""

    for txt in hero_h3s:
        iso = _parsear_fecha_corta(txt)
        if iso:
            hero_fecha = iso
            hero_texto = txt
            break

    return {
        "titulo": titulo,
        "fechas_funcion": [hero_fecha] if hero_fecha else [],
        "fecha_inicio": hero_fecha,
        "fecha_fin": hero_fecha,
        "texto_fecha_original": hero_texto,
        "espacios": espacios,
    }


def _tipo_evento_desde_texto(texto):
    t = _normalizar(texto)

    if "opera" in t or "ópera" in t:
        return "opera"
    if "danza" in t or "ballet" in t:
        return "danza"
    if "concierto" in t:
        return "concierto"
    if "tambien en el real" in t or "también en el real" in t:
        return "otros"

    return "otros"


def sacar_teatroreal():
    lugar_base = "Teatro Real"
    fuente = PROGRAMACION_URL

    eventos = []
    vistos = set()

    catalogo = _extraer_catalogo()

    for item in catalogo:
        ficha = _extraer_fechas_ficha(item["url_evento"])

        titulo_final = ficha["titulo"] or item["titulo"]
        fechas_funcion = [f for f in ficha["fechas_funcion"] if f]

        if fechas_funcion:
            info_fecha = {
                "tipo": "lista",
                "fecha": fechas_funcion[0],
                "fecha_inicio": fechas_funcion[0],
                "fecha_fin": fechas_funcion[-1],
                "fechas_funcion": fechas_funcion,
                "dias_semana": [],
                "texto_fecha_original": ficha["texto_fecha_original"] or item["fecha_home_txt"],
            }
        else:
            fecha_home = _parsear_fecha_corta(item["fecha_home_txt"])
            if not fecha_home:
                continue

            info_fecha = {
                "tipo": "unica",
                "fecha": fecha_home,
                "fecha_inicio": fecha_home,
                "fecha_fin": fecha_home,
                "fechas_funcion": [fecha_home],
                "dias_semana": [],
                "texto_fecha_original": item["fecha_home_txt"],
            }

        # 🔑 CLAVE: lugar fijo
        lugar = lugar_base
        espacio = ficha["espacios"][0] if ficha["espacios"] else ""

        agregado = agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=titulo_final,
            fecha_evento=info_fecha["fecha"],
            lugar=lugar,
            url_evento=item["url_evento"],
            fuente=fuente,
            info_fecha=info_fecha,
        )

        if agregado and eventos:
            eventos[-1]["tipo_evento"] = _tipo_evento_desde_texto(item["tipo_evento_txt"])

            if item["tipo_evento_txt"]:
                eventos[-1]["tags"] = [item["tipo_evento_txt"]]

            # guardamos espacio aparte (no rompe claves)
            if espacio:
                eventos[-1]["espacio"] = espacio

    return eventos