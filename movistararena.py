import json
from datetime import date
from urllib.parse import urljoin

from utils import agregar_evento, get_url


def limpiar_texto(texto):
    return " ".join((texto or "").split()).strip()


def extraer_bloque_json(js_texto):
    """
    Busca el contenido de:
    window.__SESSIONS_BY_MONTH__ = {...}
    sin depender de regex frágiles.
    """
    marcador = "window.__SESSIONS_BY_MONTH__ ="
    pos = js_texto.find(marcador)

    if pos == -1:
        return None

    resto = js_texto[pos + len(marcador):].strip()

    # Quitamos posible ; final
    if resto.endswith(";"):
        resto = resto[:-1].strip()

    # Nos quedamos desde la primera { hasta la última }
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
        print(f"[movistararena] error parseando JSON: {e}")
        return {}


def construir_titulo(evento):
    titulo = limpiar_texto(evento.get("title", ""))
    return titulo


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
        anio, mes, dia = fecha_texto.split("-")
        return date(int(anio), int(mes), int(dia))
    except Exception:
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
        print("[movistararena] no se pudieron extraer datos de sessions-data.js.php")
        return eventos

    hoy = date.today()
    total_bruto = 0

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

            fecha_evento = convertir_fecha_iso(evento.get("date", ""))
            if not fecha_evento:
                continue

            if fecha_evento < hoy:
                continue

            lugar = obtener_lugar(evento)
            url_evento = obtener_url_evento(evento, base_url)
            if not url_evento:
                continue

            agregar_evento(
                eventos,
                vistos,
                titulo,
                fecha_evento,
                lugar,
                url_evento,
                url_datos
            )

    print(f"[movistararena] eventos brutos leídos: {total_bruto}")
    return eventos