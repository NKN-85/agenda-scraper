import re
import requests
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url, limpiar_texto, construir_fecha


BASE_URL = "https://www.teatrolalatina.es/"
LUGAR = "Teatro La Latina"

MAPA_DIAS = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

PATRON_HASTA = re.compile(
    r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

PATRON_RANGO_MISMO_MES = re.compile(
    r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

PATRON_RANGO_COMPLETO = re.compile(
    r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

PATRON_UNICA = re.compile(
    r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)


def _parsear_info_fecha(texto):
    t = limpiar_texto(texto)

    m = PATRON_HASTA.search(t)
    if m:
        ff = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        if ff:
            return {
                "tipo_fecha": "hasta",
                "tipo": "hasta",
                "fecha": ff.isoformat(),
                "fecha_inicio": None,
                "fecha_fin": ff.isoformat(),
                "fechas_funcion": [],
                "dias_semana": [],
                "texto_fecha_original": t,
            }

    m = PATRON_RANGO_COMPLETO.search(t)
    if m:
        fi = construir_fecha(int(m.group(1)), m.group(2), int(m.group(5)))
        ff = construir_fecha(int(m.group(3)), m.group(4), int(m.group(5)))
        if fi and ff:
            return {
                "tipo_fecha": "rango",
                "tipo": "rango",
                "fecha": fi.isoformat(),
                "fecha_inicio": fi.isoformat(),
                "fecha_fin": ff.isoformat(),
                "fechas_funcion": [],
                "dias_semana": [],
                "texto_fecha_original": t,
            }

    m = PATRON_RANGO_MISMO_MES.search(t)
    if m:
        fi = construir_fecha(int(m.group(1)), m.group(3), int(m.group(4)))
        ff = construir_fecha(int(m.group(2)), m.group(3), int(m.group(4)))
        if fi and ff:
            return {
                "tipo_fecha": "rango",
                "tipo": "rango",
                "fecha": fi.isoformat(),
                "fecha_inicio": fi.isoformat(),
                "fecha_fin": ff.isoformat(),
                "fechas_funcion": [],
                "dias_semana": [],
                "texto_fecha_original": t,
            }

    m = PATRON_UNICA.search(t)
    if m:
        f = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        if f:
            iso = f.isoformat()
            return {
                "tipo_fecha": "unica",
                "tipo": "unica",
                "fecha": iso,
                "fecha_inicio": iso,
                "fecha_fin": iso,
                "fechas_funcion": [iso],
                "dias_semana": [],
                "texto_fecha_original": t,
            }

    return None


def _extraer_dias_semana_desde_horarios(soup):
    if not soup:
        return []

    aside = soup.find("div", class_="aside info-util")
    if not aside:
        return []

    h3s = aside.find_all("h3")
    horarios_texto = ""

    for h3 in h3s:
        if limpiar_texto(h3.get_text(" ", strip=True)).lower() == "horarios":
            siguiente = h3.find_next_sibling("p")
            if siguiente:
                horarios_texto = limpiar_texto(siguiente.get_text(" ", strip=True))
            break

    if not horarios_texto:
        return []

    dias = set()

    rangos = [
        ("lunes", "martes"),
        ("lunes", "miércoles"),
        ("lunes", "miercoles"),
        ("lunes", "jueves"),
        ("lunes", "viernes"),
        ("lunes", "sábado"),
        ("lunes", "sabado"),
        ("lunes", "domingo"),
        ("martes", "miércoles"),
        ("martes", "miercoles"),
        ("martes", "jueves"),
        ("martes", "viernes"),
        ("martes", "sábado"),
        ("martes", "sabado"),
        ("martes", "domingo"),
        ("miércoles", "jueves"),
        ("miercoles", "jueves"),
        ("miércoles", "viernes"),
        ("miercoles", "viernes"),
        ("miércoles", "sábado"),
        ("miercoles", "sabado"),
        ("miércoles", "domingo"),
        ("miercoles", "domingo"),
        ("jueves", "viernes"),
        ("jueves", "sábado"),
        ("jueves", "sabado"),
        ("jueves", "domingo"),
        ("viernes", "sábado"),
        ("viernes", "sabado"),
        ("viernes", "domingo"),
        ("sábado", "domingo"),
        ("sabado", "domingo"),
    ]

    for ini_txt, fin_txt in rangos:
        if re.search(rf"\b{re.escape(ini_txt)}\s+a\s+{re.escape(fin_txt)}\b", horarios_texto, re.IGNORECASE):
            ini = MAPA_DIAS[ini_txt]
            fin = MAPA_DIAS[fin_txt]
            for d in range(ini, fin + 1):
                dias.add(d)

    for dia_txt, num_dia in MAPA_DIAS.items():
        if re.search(rf"\b{re.escape(dia_txt)}s?\b", horarios_texto, re.IGNORECASE):
            dias.add(num_dia)

    return sorted(dias)


def _bloque_tiene_cta_activo(bloque):
    botones = bloque.find("div", class_="botones")
    if not botones:
        return False

    for a in botones.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        texto = limpiar_texto(a.get_text(" ", strip=True)).lower()

        if not href:
            continue

        if href in {"#", "javascript:void(0)"}:
            continue

        if texto in {"comprar", "entradas", "buy"}:
            return True

    return False


def sacar_teatrolalatina():
    url = BASE_URL
    eventos = []
    vistos = set()
    session = requests.Session()

    respuesta = get_url(url, session=session, timeout=20)
    if not respuesta:
        return []

    soup = BeautifulSoup(respuesta.text, "html.parser")
    bloques = soup.find_all("div", class_="obra")

    for bloque in bloques:
        if not _bloque_tiene_cta_activo(bloque):
            continue

        faldon = bloque.find("div", class_="faldon")
        if not faldon:
            continue

        a_principal = faldon.find("a", href=True)
        if not a_principal:
            continue

        url_evento = urljoin(url, a_principal["href"].strip())

        titulo_el = faldon.find("span", class_="titulo")
        fecha_el = faldon.find("span", class_="fecha")

        if not titulo_el or not fecha_el:
            continue

        titulo = limpiar_texto(titulo_el.get_text(" ", strip=True))
        texto_fecha = limpiar_texto(fecha_el.get_text(" ", strip=True))

        if not titulo or not texto_fecha:
            continue

        info_fecha = _parsear_info_fecha(texto_fecha)
        if not info_fecha:
            continue

        try:
            respuesta_ficha = get_url(url_evento, session=session, timeout=20)
            if respuesta_ficha:
                soup_ficha = BeautifulSoup(respuesta_ficha.text, "html.parser")
                dias_semana = _extraer_dias_semana_desde_horarios(soup_ficha)

                if dias_semana:
                    info_fecha["dias_semana"] = dias_semana

                    if info_fecha.get("tipo_fecha") == "hasta":
                        info_fecha["tipo_fecha"] = "patron"
                        info_fecha["tipo"] = "patron"
                        info_fecha["fechas_funcion"] = []
        except Exception:
            pass

        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=titulo,
            fecha_evento=info_fecha.get("fecha"),
            lugar=LUGAR,
            url_evento=url_evento,
            fuente=url,
            info_fecha=info_fecha,
        )

    return eventos