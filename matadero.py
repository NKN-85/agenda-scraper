import requests
import re
import calendar
from datetime import date, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils import get_url


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

MAPA_DIAS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "sabados": 5,
    "sábados": 5,
    "domingo": 6,
    "domingos": 6,
}

ORDEN_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def limpiar_texto(texto):
    return " ".join(str(texto).split()).strip()


def normalizar_texto(texto):
    t = limpiar_texto(texto).lower()
    return (
        t.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def construir_fecha(dia, mes_txt, anio):
    mes = MESES.get(normalizar_texto(mes_txt))
    if not mes:
        return None
    try:
        return date(int(anio), mes, int(dia))
    except Exception:
        return None


def ultimo_dia_mes(mes_txt, anio):
    mes = MESES.get(normalizar_texto(mes_txt))
    if not mes:
        return None
    return calendar.monthrange(int(anio), mes)[1]


def anio_por_defecto_para_mes(mes_txt):
    hoy = date.today()
    mes = MESES.get(normalizar_texto(mes_txt))
    if not mes:
        return hoy.year
    if mes < hoy.month - 2:
        return hoy.year + 1
    return hoy.year


def fechas_en_rango(fi, ff):
    if not fi or not ff or ff < fi:
        return []
    out = []
    cur = fi
    while cur <= ff:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def info_unica(f, texto):
    if not f:
        return None
    iso = f.isoformat()
    return {
        "fecha": iso,
        "tipo_fecha": "unica",
        "rango_fechas": False,
        "fecha_inicio": iso,
        "fecha_fin": iso,
        "fechas_funcion": [iso],
        "dias_semana": [],
        "texto_fecha_original": limpiar_texto(texto),
    }


def info_lista(fechas, texto, tipo="lista"):
    fechas = sorted({f for f in fechas if f})
    if not fechas:
        return None
    return {
        "fecha": fechas[0].isoformat(),
        "tipo_fecha": tipo,
        "rango_fechas": False,
        "fecha_inicio": fechas[0].isoformat(),
        "fecha_fin": fechas[-1].isoformat(),
        "fechas_funcion": [f.isoformat() for f in fechas],
        "dias_semana": [],
        "texto_fecha_original": limpiar_texto(texto),
    }


def info_rango(fi, ff, texto, tipo="rango"):
    if not fi or not ff:
        return None
    return {
        "fecha": fi.isoformat(),
        "tipo_fecha": tipo,
        "rango_fechas": fi != ff,
        "fecha_inicio": fi.isoformat(),
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [] if fi != ff else [fi.isoformat()],
        "dias_semana": [],
        "texto_fecha_original": limpiar_texto(texto),
    }


def info_patron(fi, ff, dias_semana, texto):
    if not ff or not dias_semana:
        return None
    fecha_repr = fi if fi else date.today()
    return {
        "fecha": fecha_repr.isoformat(),
        "tipo_fecha": "patron",
        "rango_fechas": True,
        "fecha_inicio": fi.isoformat() if fi else None,
        "fecha_fin": ff.isoformat(),
        "fechas_funcion": [],
        "dias_semana": sorted(set(dias_semana)),
        "texto_fecha_original": limpiar_texto(texto),
    }


def es_pasado(info):
    if not info:
        return True
    fin = info.get("fecha_fin")
    if not fin:
        return False
    try:
        return date.fromisoformat(fin) < date.today()
    except Exception:
        return False


def extraer_dias_semana_en_texto(texto):
    t = normalizar_texto(texto)
    dias = set()

    for m in re.finditer(
        r"(?:\bde\s+)?(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t,
    ):
        d1 = m.group(1)
        d2 = m.group(2)
        i1 = ORDEN_DIAS.index(d1)
        i2 = ORDEN_DIAS.index(d2)
        for nombre in ORDEN_DIAS[i1:i2 + 1]:
            dias.add(MAPA_DIAS[nombre])

    for m in re.finditer(
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+y\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b",
        t,
    ):
        dias.add(MAPA_DIAS[m.group(1)])
        dias.add(MAPA_DIAS[m.group(2)])

    if re.search(r"\d", t):
        for nombre, idx in MAPA_DIAS.items():
            if re.search(rf"\b{re.escape(nombre)}\b", t):
                dias.add(idx)

    return sorted(dias)


def extraer_fechas_lista_mismo_mes(texto, mes_txt, anio):
    nums = [int(x) for x in re.findall(r"\d{1,2}", texto)]
    return [construir_fecha(n, mes_txt, anio) for n in nums]


def parsear_fecha_ficha(fecha_texto, horario_lineas=None):
    horario_lineas = horario_lineas or []
    original = limpiar_texto(fecha_texto)
    if not original:
        return None

    t = normalizar_texto(original)
    horario_txt = " ".join(limpiar_texto(x) for x in horario_lineas)
    horario_norm = normalizar_texto(horario_txt)

    m = re.fullmatch(r"hasta\s+([a-z]+)\s+(\d{4})", t)
    if m:
        anio = int(m.group(2))
        udm = ultimo_dia_mes(m.group(1), anio)
        ff = construir_fecha(udm, m.group(1), anio) if udm else None
        dias = extraer_dias_semana_en_texto(horario_norm)
        if dias:
            return info_patron(None, ff, dias, original + " | " + horario_txt)
        return info_rango(ff, ff, original, tipo="hasta")

    m = re.fullmatch(r"hasta\s+(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?", t)
    if m:
        anio = int(m.group(3)) if m.group(3) else anio_por_defecto_para_mes(m.group(2))
        ff = construir_fecha(m.group(1), m.group(2), anio)
        dias = extraer_dias_semana_en_texto(horario_norm)
        if dias:
            return info_patron(None, ff, dias, original + " | " + horario_txt)
        return info_rango(ff, ff, original, tipo="hasta")

    m = re.fullmatch(
        r"(?:lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)\s+(\d{1,2})\s+de\s+([a-z]+)\s*,\s*(\d{1,2})\s+de\s+([a-z]+)\s+y\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
        t,
    )
    if m:
        anio = int(m.group(7))
        fechas = [
            construir_fecha(m.group(1), m.group(2), anio),
            construir_fecha(m.group(3), m.group(4), anio),
            construir_fecha(m.group(5), m.group(6), anio),
        ]
        return info_lista(fechas, original)

    m = re.fullmatch(
        r"(?:lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)\s+(.+?)\s+de\s+([a-z]+)\s*;\s*(.+?)\s+de\s+([a-z]+)\s+y\s+(.+?)\s+de\s+([a-z]+)\s+(\d{4})",
        t,
    )
    if m:
        anio = int(m.group(7))
        fechas = []
        fechas.extend(extraer_fechas_lista_mismo_mes(m.group(1), m.group(2), anio))
        fechas.extend(extraer_fechas_lista_mismo_mes(m.group(3), m.group(4), anio))
        fechas.extend(extraer_fechas_lista_mismo_mes(m.group(5), m.group(6), anio))
        return info_lista(fechas, original)

    m = re.fullmatch(
        r"(?:lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)\s+(\d{1,2})\s+([a-z]+)\s+y\s+(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?",
        t,
    )
    if m:
        anio = int(m.group(5)) if m.group(5) else anio_por_defecto_para_mes(m.group(2))
        fechas = [
            construir_fecha(m.group(1), m.group(2), anio),
            construir_fecha(m.group(3), m.group(4), anio),
        ]
        return info_lista(fechas, original)

    m = re.fullmatch(r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", t)
    if m:
        fi = construir_fecha(m.group(1), m.group(3), m.group(4))
        ff = construir_fecha(m.group(2), m.group(3), m.group(4))
        dias = extraer_dias_semana_en_texto(horario_norm)
        if dias:
            return info_patron(fi, ff, dias, original + " | " + horario_txt)
        return info_lista(fechas_en_rango(fi, ff), original)

    m = re.fullmatch(
        r"(?:del\s+)?(\d{1,2})\s+([a-z]+)\s+(?:al|a)\s+(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?",
        t,
    )
    if m:
        anio = int(m.group(5)) if m.group(5) else anio_por_defecto_para_mes(m.group(2))
        fi = construir_fecha(m.group(1), m.group(2), anio)
        ff = construir_fecha(m.group(3), m.group(4), anio)
        dias = extraer_dias_semana_en_texto(horario_norm)
        if dias:
            return info_patron(fi, ff, dias, original + " | " + horario_txt)
        return info_rango(fi, ff, original)

    m = re.fullmatch(r"(\d{1,2})\s*(?:-|–|\s)\s*(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?", t)
    if m:
        anio = int(m.group(4)) if m.group(4) else anio_por_defecto_para_mes(m.group(3))
        fi = construir_fecha(m.group(1), m.group(3), anio)
        ff = construir_fecha(m.group(2), m.group(3), anio)
        return info_lista(fechas_en_rango(fi, ff), original)

    m = re.fullmatch(r"(\d{1,2})\s+a\s+(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?", t)
    if m:
        anio = int(m.group(4)) if m.group(4) else anio_por_defecto_para_mes(m.group(3))
        fi = construir_fecha(m.group(1), m.group(3), anio)
        ff = construir_fecha(m.group(2), m.group(3), anio)
        return info_lista(fechas_en_rango(fi, ff), original)

    m = re.fullmatch(
        r"((?:\d{1,2}\s*,\s*)*\d{1,2}\s+y\s+\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?",
        t,
    )
    if m:
        anio = int(m.group(3)) if m.group(3) else anio_por_defecto_para_mes(m.group(2))
        fechas = extraer_fechas_lista_mismo_mes(m.group(1), m.group(2), anio)
        return info_lista(fechas, original)

    m = re.fullmatch(
        r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})\s+y\s+(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?",
        t,
    )
    if m:
        anio = int(m.group(4)) if m.group(4) else anio_por_defecto_para_mes(m.group(3))
        fechas = [
            construir_fecha(m.group(1), m.group(3), anio),
            construir_fecha(m.group(2), m.group(3), anio),
        ]
        return info_lista(fechas, original)

    m = re.fullmatch(
        r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?",
        t,
    )
    if m:
        anio = int(m.group(3)) if m.group(3) else anio_por_defecto_para_mes(m.group(2))
        f = construir_fecha(m.group(1), m.group(2), anio)
        return info_unica(f, original)

    m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?", t)
    if m:
        anio = int(m.group(3)) if m.group(3) else anio_por_defecto_para_mes(m.group(2))
        f = construir_fecha(m.group(1), m.group(2), anio)
        return info_unica(f, original)

    m = re.search(r"(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?$", t)
    if m:
        anio = int(m.group(3)) if m.group(3) else anio_por_defecto_para_mes(m.group(2))
        ff = construir_fecha(m.group(1), m.group(2), anio)
        dias = extraer_dias_semana_en_texto(horario_norm)
        if dias:
            return info_patron(None, ff, dias, original + " | " + horario_txt)

    return None


def obtener_paginas(session, base_url):
    paginas = []
    visitadas = set()
    actual = base_url

    while actual and actual not in visitadas:
        visitadas.add(actual)

        r = get_url(actual, session=session, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        paginas.append((actual, soup))

        siguiente = None
        for a in soup.find_all("a", href=True):
            texto = limpiar_texto(a.get_text(" ", strip=True)).lower()
            if "next page" in texto:
                siguiente = urljoin(base_url, a["href"].strip())
                break

        actual = siguiente

    return paginas


def es_url_programacion_valida(href_abs, base_url):
    url = href_abs.rstrip("/")
    base = base_url.rstrip("/")

    if "/programacion/" not in url:
        return False
    if url == base:
        return False

    # excluir rutas no ficha o repetidas
    excluidos = [
        "/programacion/page/",
        "/programacion/categoria/",
        "/programacion/etiqueta/",
        "/programacion/tag/",
        "/programacion/search",
    ]
    if any(x in url.lower() for x in excluidos):
        return False

    return True


def extraer_urls_programacion_de_portada(soup, base_url):
    urls = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue

        href_abs = href if href.startswith("http") else urljoin(base_url, href)

        if not es_url_programacion_valida(href_abs, base_url):
            continue

        if href_abs not in vistos:
            vistos.add(href_abs)
            urls.append(href_abs)

    return urls


def extraer_lineas(soup):
    return [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]


def extraer_titulo_ficha(soup):
    h1 = soup.find("h1")
    if h1:
        return limpiar_texto(h1.get_text(" ", strip=True))
    return None


def extraer_seccion(lineas, nombre, stop_extra=None):
    stop_extra = stop_extra or set()
    stops = {
        "fecha", "horario", "espacio", "lugar", "precio",
        "categoria", "categoría", "formato", "institucion", "institución",
        "accesibilidad", "actividades", "actividades pasadas", "contact",
    } | {normalizar_texto(x) for x in stop_extra}

    objetivo = normalizar_texto(nombre)
    for i, linea in enumerate(lineas):
        if normalizar_texto(linea) != objetivo:
            continue

        out = []
        j = i + 1
        while j < len(lineas):
            lj = normalizar_texto(lineas[j])
            if lj in stops and lj != objetivo:
                break
            out.append(lineas[j])
            j += 1
        return out

    return []


def unir_lineas_fecha(fecha_lineas):
    fecha_lineas = [limpiar_texto(x) for x in fecha_lineas if limpiar_texto(x)]
    if not fecha_lineas:
        return ""
    if len(fecha_lineas) == 1:
        return fecha_lineas[0]
    return " ".join(fecha_lineas)


def construir_evento(titulo, lugar, url_evento, fuente, info_fecha):
    return {
        "titulo": titulo,
        "fecha": info_fecha.get("fecha"),
        "lugar": lugar,
        "url_evento": url_evento,
        "fuente": fuente,
        "tipo_fecha": info_fecha.get("tipo_fecha"),
        "rango_fechas": info_fecha.get("rango_fechas", False),
        "fecha_inicio": info_fecha.get("fecha_inicio"),
        "fecha_fin": info_fecha.get("fecha_fin"),
        "fechas_funcion": info_fecha.get("fechas_funcion", []),
        "dias_semana": info_fecha.get("dias_semana", []),
        "texto_fecha_original": info_fecha.get("texto_fecha_original", ""),
    }


def tiene_secciones_utiles(lineas):
    claves = {"fecha", "horario", "actividades"}
    presentes = {normalizar_texto(x) for x in lineas}
    return bool(claves & presentes)


def extraer_actividades_hijas(lineas, soup, url_ficha, fuente, vistos):
    eventos = []
    lugar = "Matadero Madrid"

    if "actividades" not in {normalizar_texto(x) for x in lineas}:
        return eventos

    anchors = {}
    for a in soup.find_all("a", href=True):
        texto = limpiar_texto(a.get_text(" ", strip=True))
        href = a.get("href", "").strip()
        if not texto or not href:
            continue
        href_abs = href if href.startswith("http") else urljoin(url_ficha, href)
        if not es_url_programacion_valida(href_abs, fuente):
            continue
        anchors[texto] = href_abs

    try:
        idx = next(i for i, x in enumerate(lineas) if normalizar_texto(x) == "actividades")
    except StopIteration:
        return eventos

    j = idx + 1
    while j < len(lineas):
        lj = normalizar_texto(lineas[j])

        if lj in {"actividades pasadas", "contact"}:
            break

        if lj == "fecha":
            fecha_bloque = []
            k = j + 1
            while k < len(lineas) and normalizar_texto(lineas[k]) not in {
                "fecha", "horario", "espacio", "lugar", "precio",
                "categoria", "categoría", "formato", "institucion", "institución",
                "accesibilidad", "actividades", "actividades pasadas", "contact"
            }:
                fecha_bloque.append(lineas[k])
                k += 1

            fecha_txt = unir_lineas_fecha(fecha_bloque)
            titulo = lineas[k] if k < len(lineas) else None
            url_hija = anchors.get(titulo) if titulo else None

            info = parsear_fecha_ficha(fecha_txt, [])
            if info and not es_pasado(info) and url_hija and titulo:
                clave = (titulo.lower(), url_hija.lower(), info.get("fecha_inicio"), info.get("fecha_fin"))
                if clave not in vistos:
                    vistos.add(clave)
                    eventos.append(construir_evento(titulo, lugar, url_hija, fuente, info))

        j += 1

    return eventos


def extraer_evento_desde_ficha(session, url_ficha, fuente, vistos):
    r = get_url(url_ficha, session=session, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    lineas = extraer_lineas(soup)

    if not tiene_secciones_utiles(lineas):
        return [], []

    titulo = extraer_titulo_ficha(soup)
    if not titulo:
        return [], []

    fecha_lineas = extraer_seccion(lineas, "Fecha")
    horario_lineas = extraer_seccion(lineas, "Horario")

    fecha_txt = unir_lineas_fecha(fecha_lineas)
    info = parsear_fecha_ficha(fecha_txt, horario_lineas)

    eventos_principales = []
    lugar = "Matadero Madrid"

    if info and not es_pasado(info):
        clave = (titulo.lower(), url_ficha.lower(), info.get("fecha_inicio"), info.get("fecha_fin"))
        if clave not in vistos:
            vistos.add(clave)
            eventos_principales.append(construir_evento(titulo, lugar, url_ficha, fuente, info))

    eventos_hijos = extraer_actividades_hijas(lineas, soup, url_ficha, fuente, vistos)

    return eventos_principales, eventos_hijos


def sacar_matadero():
    base_url = "https://www.mataderomadrid.org/programacion"

    session = requests.Session()
    vistos = set()
    eventos = []
    urls_evento = []
    vistos_urls = set()

    paginas = obtener_paginas(session, base_url)

    for pagina, soup in paginas:
        try:
            for url in extraer_urls_programacion_de_portada(soup, base_url):
                if url not in vistos_urls:
                    vistos_urls.add(url)
                    urls_evento.append(url)
        except Exception as e:
            print(f"[AVISO] Error leyendo portada Matadero {pagina}: {e}")

    for url_ficha in urls_evento:
        try:
            principales, hijos = extraer_evento_desde_ficha(
                session=session,
                url_ficha=url_ficha,
                fuente=base_url,
                vistos=vistos,
            )
            eventos.extend(principales)
            eventos.extend(hijos)
        except Exception as e:
            print(f"[AVISO] Error en ficha Matadero {url_ficha}: {e}")

    return eventos