import json
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url


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


def limpiar_texto(texto):
    return " ".join((texto or "").split()).strip()


def normalizar_texto(texto):
    texto = limpiar_texto(str(texto or "")).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def clave_evento(titulo, lugar, url_evento):
    return (
        normalizar_texto(titulo),
        normalizar_texto(lugar),
        limpiar_texto(url_evento).rstrip("/").lower(),
    )


def extraer_bloque_json(js_texto):
    marcador = "window.__SESSIONS_BY_MONTH__ ="
    pos = js_texto.find(marcador)

    if pos == -1:
        return None

    resto = js_texto[pos + len(marcador):].strip()

    if resto.endswith(";"):
        resto = resto[:-1].strip()

    inicio = resto.find("{")
    fin = resto.rfind("}")

    if inicio == -1 or fin == -1 or fin <= inicio:
        return None

    return resto[inicio:fin + 1]


def parsear_sessions_data(js_texto):
    bloque_json = extraer_bloque_json(js_texto)
    if not bloque_json:
        return {}

    try:
        return json.loads(bloque_json)
    except Exception as e:
        return {}


def construir_titulo(evento):
    return limpiar_texto(evento.get("title", ""))


def obtener_lugar(evento):
    venue = evento.get("venue") or {}
    nombre = limpiar_texto(venue.get("name", ""))
    ciudad = limpiar_texto(venue.get("city", ""))

    if nombre and ciudad:
        return f"{nombre} · {ciudad}"
    if nombre:
        return nombre

    return "Movistar Arena"


def obtener_url_evento(evento, base_url):
    cta = evento.get("cta") or {}
    info_url = limpiar_texto(cta.get("info_url", ""))
    slug = limpiar_texto(evento.get("slug", ""))

    if info_url:
        return urljoin(base_url, info_url)

    if slug:
        return urljoin(base_url, f"/programacion/evento/{slug}")

    return ""


def convertir_fecha_iso(fecha_texto):
    if not fecha_texto:
        return None

    try:
        anio, mes, dia = str(fecha_texto)[:10].split("-")
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def construir_fecha(dia, mes, anio):
    try:
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def construir_fecha_desde_texto(dia, mes_texto, anio):
    mes = MESES.get(normalizar_texto(mes_texto))
    if not mes:
        return None
    return construir_fecha(dia, mes, anio)


def extraer_fechas_texto_movistar(texto):
    texto_norm = normalizar_texto(texto)
    fechas = set()

    patron_textual = re.compile(
        r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)?"
        r",?\s*(\d{1,2})\s+de\s+"
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
        r"\s+de\s+(20\d{2})"
    )

    for match in patron_textual.finditer(texto_norm):
        fecha = construir_fecha_desde_texto(match.group(1), match.group(2), match.group(3))
        if fecha:
            fechas.add(fecha)

    patron_url = re.compile(r"(?<!\d)([0-3]?\d)-([01]?\d)-(20\d{2})(?!\d)")

    for match in patron_url.finditer(texto_norm):
        fecha = construir_fecha(match.group(1), match.group(2), match.group(3))
        if fecha:
            fechas.add(fecha)

    patron_iso = re.compile(r"\b(20\d{2})-([01]\d)-([0-3]\d)(?:[tT ][0-2]\d:[0-5]\d(?::[0-5]\d)?)?")

    for match in patron_iso.finditer(texto_norm):
        fecha = construir_fecha(match.group(3), match.group(2), match.group(1))
        if fecha:
            fechas.add(fecha)

    return sorted(fechas)


def recorrer_json(obj):
    if isinstance(obj, dict):
        yield obj
        for valor in obj.values():
            yield from recorrer_json(valor)
    elif isinstance(obj, list):
        for item in obj:
            yield from recorrer_json(item)


def extraer_fechas_json_ld(soup):
    fechas = set()

    for script in soup.select('script[type="application/ld+json"]'):
        texto = script.string or script.get_text(" ", strip=True)
        if not texto:
            continue

        try:
            data = json.loads(texto)
        except Exception:
            continue

        for nodo in recorrer_json(data):
            for clave in ("startDate", "endDate", "doorTime"):
                valor = nodo.get(clave)
                if not valor:
                    continue

                fecha = convertir_fecha_iso(str(valor))
                if fecha:
                    fechas.add(fecha)

    return sorted(fechas)


def extraer_textos_y_atributos(soup):
    piezas = []

    texto = soup.get_text("\n", strip=True)
    if texto:
        piezas.append(texto)

    for nodo in soup.find_all(True):
        for valor in nodo.attrs.values():
            if isinstance(valor, list):
                valor = " ".join(str(v) for v in valor)
            else:
                valor = str(valor)

            if valor:
                piezas.append(valor)

    return piezas


def extraer_fechas_ficha(url_evento):
    if not url_evento:
        return []

    try:
        respuesta = get_url(url_evento, timeout=20)
        soup = BeautifulSoup(respuesta.text, "html.parser")
    except Exception as e:
        return []

    fechas = set()
    fechas.update(extraer_fechas_json_ld(soup))

    for pieza in extraer_textos_y_atributos(soup):
        fechas.update(extraer_fechas_texto_movistar(pieza))

    return sorted(fechas)


def obtener_fechas_evento(evento, url_evento):
    fechas = set()

    fecha_base = convertir_fecha_iso(evento.get("date", ""))
    if fecha_base:
        fechas.add(fecha_base)

    fechas.update(extraer_fechas_ficha(url_evento))

    return sorted(fechas)


def actualizar_evento_con_lista_fechas(evento, fechas):
    fechas = sorted(set(fechas or []))
    if not evento or not fechas:
        return

    fechas_iso = [f.isoformat() for f in fechas]

    evento["fecha"] = fechas_iso[0]
    evento["fecha_inicio"] = fechas_iso[0]
    evento["fecha_fin"] = fechas_iso[-1]
    evento["fechas_funcion"] = fechas_iso
    evento["dias_semana"] = []
    evento["texto_fecha_original"] = "sessions-data + ficha movistararena"

    if len(fechas_iso) >= 2:
        evento["tipo_fecha"] = "lista"
        evento["rango_fechas"] = False
    else:
        evento["tipo_fecha"] = "unica"
        evento["rango_fechas"] = False


def buscar_evento_guardado(eventos, titulo, lugar, url_evento):
    clave = clave_evento(titulo, lugar, url_evento)

    for evento in reversed(eventos):
        if clave_evento(
            evento.get("titulo", ""),
            evento.get("lugar", ""),
            evento.get("url_evento", ""),
        ) == clave:
            return evento

    return None


def sacar_movistararena():
    base_url = "https://www.movistararena.es"
    url_datos = "https://www.movistararena.es/programacion/sessions-data.js.php?lang=es"

    eventos = []
    vistos = set()

    respuesta = get_url(url_datos, timeout=20)
    texto = respuesta.text

    datos = parsear_sessions_data(texto)

    if not datos:
        return eventos

    hoy = date.today()
    total_bruto = 0
    total_fechas_extra = 0
    agrupados = {}

    for _, lista_eventos in datos.items():
        if not isinstance(lista_eventos, list):
            continue

        for evento in lista_eventos:
            if not isinstance(evento, dict):
                continue

            total_bruto += 1

            titulo = construir_titulo(evento)
            if not titulo:
                continue

            lugar = obtener_lugar(evento)
            url_evento = obtener_url_evento(evento, base_url)
            if not url_evento:
                continue

            fechas_evento = obtener_fechas_evento(evento, url_evento)
            fechas_futuras = [f for f in fechas_evento if f >= hoy]

            if not fechas_futuras:
                continue

            clave = clave_evento(titulo, lugar, url_evento)

            if clave not in agrupados:
                agrupados[clave] = {
                    "titulo": titulo,
                    "lugar": lugar,
                    "url_evento": url_evento,
                    "fechas": set(),
                }

            agrupados[clave]["fechas"].update(fechas_futuras)

    for data in agrupados.values():
        titulo = data["titulo"]
        lugar = data["lugar"]
        url_evento = data["url_evento"]
        fechas = sorted(data["fechas"])

        if not fechas:
            continue

        if len(fechas) > 1:
            total_fechas_extra += len(fechas) - 1

        agregar_evento(
            eventos,
            vistos,
            titulo,
            fechas[0],
            lugar,
            url_evento,
            url_datos
        )

        evento_guardado = buscar_evento_guardado(eventos, titulo, lugar, url_evento)
        actualizar_evento_con_lista_fechas(evento_guardado, fechas)

    return eventos