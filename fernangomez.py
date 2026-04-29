import re
import requests
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import agregar_evento, get_url
from helpers.fichas import abrir_ficha, extraer_lineas, extraer_titulo


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

ORDEN_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

MAPA_DIAS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
    "domingos": 6,
    "sabados": 5,
    "sábados": 5,
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
    try:
        mes = MESES.get(_normalizar(mes_txt))
        if not mes:
            return None
        return date(int(anio), int(mes), int(dia))
    except Exception:
        return None


def _inferir_anio(textos, mes_txt=None):
    for texto in textos:
        t = _normalizar(texto)
        anios = re.findall(r"\b(20\d{2})\b", t)
        if anios:
            return int(anios[-1])

    hoy = date.today()
    if not mes_txt:
        return hoy.year

    mes = MESES.get(_normalizar(mes_txt))
    if not mes:
        return hoy.year

    anio = hoy.year
    if mes < hoy.month - 1:
        anio += 1
    return anio


def _es_url_excluida(url_evento):
    u = (url_evento or "").lower()

    if "/avances/" in u:
        return True

    slugs_excluidos = [
        "/programacion/participacion-cultural",
        "/actividades/encuentros-con-el-publico-funciones-matinales",
    ]

    return any(s in u for s in slugs_excluidos)


def _es_titulo_excluido(titulo):
    t = _normalizar(titulo)
    patrones = [
        "programacion temporada",
        "espectaculos de teatro, musica, exposiciones e infantiles",
        "participacion cultural",
        "encuentros con el publico - funciones matinales",
    ]
    return any(p in t for p in patrones)


def _extraer_lugar(textos, lugar_base):
    joined = " | ".join(textos).lower()

    if "sala guirau" in joined:
        return f"{lugar_base} - Sala Guirau"
    if "sala jardiel poncela" in joined:
        return f"{lugar_base} - Sala Jardiel Poncela"
    if "sala de exposiciones" in joined:
        return f"{lugar_base} - Sala de Exposiciones"
    if "sala polivalente" in joined:
        return f"{lugar_base} - Sala Polivalente"
    if "otros espacios" in joined:
        return f"{lugar_base} - Otros espacios"

    return lugar_base


def _extraer_bloques_programacion(soup, url_base):
    resultado = []
    bloques = soup.find_all("div", class_="views-row")

    for bloque in bloques:
        enlaces = bloque.find_all("a", href=True)
        if not enlaces:
            continue

        url_evento = None
        titulo_anchor = ""

        for a in enlaces:
            href = (a.get("href") or "").strip()
            if not href:
                continue

            href_l = href.lower()

            # Aceptamos actividades y también eventos reales bajo /programacion/
            if (
                "/actividades/" in href_l
                or "/programacion/" in href_l
                or "/avances/" in href_l
            ):
                url_evento = urljoin(url_base, href)
                titulo_anchor = _limpiar(a.get_text(" ", strip=True))
                break

        if not url_evento:
            continue

        textos_portada = []
        for s in bloque.stripped_strings:
            t = _limpiar(s)
            if t and t not in textos_portada:
                textos_portada.append(t)

        resultado.append({
            "url_evento": url_evento,
            "titulo_anchor": titulo_anchor,
            "textos_portada": textos_portada,
        })

    return resultado


def _seleccionar_lineas_relevantes(textos, limitar=True):
    if limitar:
        textos = textos[:35]

    relevantes = []

    for texto in textos:
        t = _limpiar(texto)
        tn = _normalizar(t)

        if not t:
            continue

        if tn.startswith("del "):
            relevantes.append(t)
            continue

        if tn.startswith("horario"):
            relevantes.append(t)
            continue

        if re.fullmatch(r"\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}", t, re.I):
            relevantes.append(t)
            continue

        if re.fullmatch(r"\d{1,2}\s+de\s+[a-záéíóú]+", t, re.I):
            relevantes.append(t)
            continue

        if re.fullmatch(r"\d{1,2}\s+y\s+\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}", t, re.I):
            relevantes.append(t)
            continue

        if re.fullmatch(r"\d{1,2}\s*,\s*\d{1,2}\s+y\s+\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}", t, re.I):
            relevantes.append(t)
            continue

        if any(d in tn for d in ORDEN_DIAS) and (
            "horas" in tn or "cerrado" in tn or "a las" in tn or ":" in tn
        ):
            relevantes.append(t)
            continue

    return relevantes


def _buscar_rango(textos):
    patrones = [
        re.compile(
            r"^del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})$",
            re.I,
        ),
        re.compile(
            r"^del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})$",
            re.I,
        ),
    ]

    for texto in textos:
        t = _limpiar(texto)

        m = patrones[0].match(t)
        if m:
            inicio = _construir_fecha(m.group(1), m.group(2), m.group(5))
            fin = _construir_fecha(m.group(3), m.group(4), m.group(5))
            if inicio and fin:
                return inicio, fin, t

        m = patrones[1].match(t)
        if m:
            inicio = _construir_fecha(m.group(1), m.group(3), m.group(4))
            fin = _construir_fecha(m.group(2), m.group(3), m.group(4))
            if inicio and fin:
                return inicio, fin, t

    return None, None, None


def _buscar_lista_fechas(textos):
    for texto in textos:
        t = _limpiar(texto)

        m = re.fullmatch(
            r"(\d{1,2})\s*,\s*(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
            t,
            re.I,
        )
        if m:
            anio = m.group(5)
            mes = m.group(4)
            fechas = []
            for d in [m.group(1), m.group(2), m.group(3)]:
                f = _construir_fecha(d, mes, anio)
                if f:
                    fechas.append(f)
            return sorted(set(fechas)), t

        m = re.fullmatch(
            r"(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
            t,
            re.I,
        )
        if m:
            anio = m.group(4)
            mes = m.group(3)
            fechas = []
            for d in [m.group(1), m.group(2)]:
                f = _construir_fecha(d, mes, anio)
                if f:
                    fechas.append(f)
            return sorted(set(fechas)), t

    return [], None


def _buscar_fecha_unica(textos):
    for texto in textos:
        t = _limpiar(texto)

        m = re.fullmatch(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", t, re.I)
        if m:
            fecha = _construir_fecha(m.group(1), m.group(2), m.group(3))
            if fecha:
                return fecha, t

        m = re.fullmatch(r"(\d{1,2})\s+de\s+([a-záéíóú]+)", t, re.I)
        if m:
            anio = _inferir_anio(textos, m.group(2))
            fecha = _construir_fecha(m.group(1), m.group(2), anio)
            if fecha:
                return fecha, t

        m = re.fullmatch(
            r"(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\s+(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+de\s+(\d{4}))?",
            t,
            re.I,
        )
        if m:
            anio = m.group(4) or _inferir_anio(textos, m.group(3))
            fecha = _construir_fecha(m.group(2), m.group(3), anio)
            if fecha:
                return fecha, t

    return None, None


def _expandir_rango_dias(d1, d2):
    i1 = ORDEN_DIAS.index(d1)
    i2 = ORDEN_DIAS.index(d2)
    if i1 <= i2:
        tramo = ORDEN_DIAS[i1:i2 + 1]
    else:
        tramo = ORDEN_DIAS[i1:] + ORDEN_DIAS[:i2 + 1]
    return [MAPA_DIAS[d] for d in tramo]


def _parsear_dias_semana(textos):
    t = _normalizar(" ".join(textos))
    dias = set()

    for m in re.finditer(
        r"de\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t,
    ):
        for idx in _expandir_rango_dias(m.group(1), m.group(2)):
            dias.add(idx)

    for m in re.finditer(
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+y\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b",
        t,
    ):
        dias.add(MAPA_DIAS[m.group(1)])
        dias.add(MAPA_DIAS[m.group(2)])

    for nombre, idx in MAPA_DIAS.items():
        if re.search(rf"\b{re.escape(nombre)}s?\b(?:\s*[:\-]|\s+a\s+las?|\s+de)\s*", t):
            dias.add(idx)

    if "lunes cerrado" in t:
        dias.discard(0)

    return sorted(dias)


def _construir_info_fecha(textos_ficha, textos_portada):
    relevantes_ficha = _seleccionar_lineas_relevantes(textos_ficha or [], limitar=True)
    relevantes_portada = _seleccionar_lineas_relevantes(textos_portada or [], limitar=False)

    fecha_inicio, fecha_fin, linea_rango = _buscar_rango(relevantes_ficha)
    if not fecha_inicio or not fecha_fin:
        fecha_inicio, fecha_fin, linea_rango = _buscar_rango(relevantes_portada)

    dias_semana = _parsear_dias_semana(relevantes_ficha)

    if fecha_inicio and fecha_fin and dias_semana:
        return {
            "tipo_fecha": "patron",
            "tipo": "patron",
            "fecha": fecha_inicio.isoformat(),
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "fechas_funcion": [],
            "dias_semana": dias_semana,
            "texto_fecha_original": linea_rango or "",
        }

    if fecha_inicio and fecha_fin:
        return {
            "tipo_fecha": "rango",
            "tipo": "rango",
            "fecha": fecha_inicio.isoformat(),
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "fechas_funcion": [],
            "dias_semana": [],
            "texto_fecha_original": linea_rango or "",
        }

    fechas_lista, texto_lista = _buscar_lista_fechas(relevantes_ficha)
    if not fechas_lista:
        fechas_lista, texto_lista = _buscar_lista_fechas(relevantes_portada)

    if len(fechas_lista) >= 2:
        fechas_iso = [f.isoformat() for f in fechas_lista]
        return {
            "tipo_fecha": "lista",
            "tipo": "lista",
            "fecha": fechas_iso[0],
            "fecha_inicio": fechas_iso[0],
            "fecha_fin": fechas_iso[-1],
            "fechas_funcion": fechas_iso,
            "dias_semana": [],
            "texto_fecha_original": texto_lista or "",
        }

    fecha_unica, texto_unico = _buscar_fecha_unica(relevantes_ficha)
    if not fecha_unica:
        fecha_unica, texto_unico = _buscar_fecha_unica(relevantes_portada)

    if fecha_unica:
        iso = fecha_unica.isoformat()
        return {
            "tipo_fecha": "unica",
            "tipo": "unica",
            "fecha": iso,
            "fecha_inicio": iso,
            "fecha_fin": iso,
            "fechas_funcion": [iso],
            "dias_semana": [],
            "texto_fecha_original": texto_unico or "",
        }

    return None


def sacar_fernangomez():
    url = "https://www.teatrofernangomez.es/programacion"
    lugar_base = "Teatro Fernán Gómez"

    eventos = []
    vistos = set()
    session = requests.Session()

    respuesta = get_url(url, timeout=20, session=session)
    if not respuesta:
        return []

    soup = BeautifulSoup(respuesta.text, "html.parser")
    bloques = _extraer_bloques_programacion(soup, url)

    por_url = {}

    for bloque in bloques:
        url_evento = bloque["url_evento"]
        if _es_url_excluida(url_evento):
            continue

        textos_portada = bloque["textos_portada"]

        if url_evento not in por_url:
            por_url[url_evento] = {
                "titulo_anchor": bloque["titulo_anchor"],
                "textos_portada": textos_portada[:],
            }
        else:
            for t in textos_portada:
                if t not in por_url[url_evento]["textos_portada"]:
                    por_url[url_evento]["textos_portada"].append(t)

    for url_evento, data in por_url.items():
        soup_ficha = abrir_ficha(session, url_evento)
        if not soup_ficha:
            continue

        titulo = _limpiar(extraer_titulo(soup_ficha) or data["titulo_anchor"])
        if not titulo:
            continue

        if _es_titulo_excluido(titulo):
            continue

        textos_ficha = extraer_lineas(soup_ficha)
        textos_portada = data["textos_portada"]

        info_fecha = _construir_info_fecha(textos_ficha, textos_portada)
        if not info_fecha:
            continue

        lugar = _extraer_lugar(textos_ficha + textos_portada, lugar_base)

        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=titulo,
            fecha_evento=info_fecha.get("fecha"),
            lugar=lugar,
            url_evento=url_evento,
            fuente=url,
            info_fecha=info_fecha,
        )

    return eventos