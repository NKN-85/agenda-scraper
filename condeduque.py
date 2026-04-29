import requests
import re
import calendar
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils import get_url, limpiar_texto, agregar_evento, construir_fecha
from helpers.avisos import avisar
from helpers.fechas_eventos import info_fecha_sigue_vigente, fecha_representativa
from helpers.resolver_fechas import resolver_info_fecha_de_bloques
from helpers.parser_fechas import (
    normalizar_texto_fecha,
    MESES,
    extraer_fechas_explicitas,
)


BASE_URL = "https://www.condeduquemadrid.es/programacion"
LUGAR = "Condeduque Madrid"

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

ORDEN_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


# -------------------------
# HELPERS GENERALES
# -------------------------

def ultimo_dia_mes(mes_txt, anio):
    mes_num = MESES.get(normalizar_texto_fecha(mes_txt))
    if not mes_num:
        return None
    return calendar.monthrange(int(anio), mes_num)[1]


def extraer_lineas(soup):
    return [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]


def extraer_titulo(soup):
    h1 = soup.find("h1")
    if h1:
        return limpiar_texto(h1.get_text(" ", strip=True))
    if soup.title:
        return limpiar_texto(soup.title.get_text(" ", strip=True).split("|")[0])
    return None


def extraer_seccion(lineas, nombre, stop_extra=None):
    stop_extra = stop_extra or set()

    stops = {
        "info",
        "ficha artística",
        "ficha artistica",
        "espacio",
        "fecha",
        "horario",
        "edad recomendada",
        "tipo de público",
        "tipo de publico",
        "precio",
        "duración",
        "duracion",
        "disciplina",
        "formato",
        "accesible",
        "publico",
        "público",
        "inscripción",
        "inscripcion",
        "recommended age",
    } | {normalizar_texto_fecha(x) for x in stop_extra}

    objetivo = normalizar_texto_fecha(nombre)

    for i, linea in enumerate(lineas):
        if normalizar_texto_fecha(linea) != objetivo:
            continue

        out = []
        j = i + 1
        while j < len(lineas):
            lj = normalizar_texto_fecha(lineas[j])
            if lj in stops and lj != objetivo:
                break
            out.append(lineas[j])
            j += 1
        return out

    return []


# -------------------------
# LIMPIEZA ESPECIFICA
# -------------------------

def limpiar_ruido_fecha(texto):
    if not texto:
        return ""

    t = limpiar_texto(texto)

    # bug tipo: "de a abril"
    t = re.sub(
        r"\bde\s+a\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
        r"de \1",
        t,
        flags=re.I
    )

    # quitar rangos horarios
    t = re.sub(
        r"\bde\s+\d{1,2}[.:]\d{2}h?\s+a\s+\d{1,2}[.:]\d{2}h?\b",
        "",
        t,
        flags=re.I
    )

    # quitar horas sueltas
    t = re.sub(r"\b\d{1,2}[.:]\d{2}h?\b", "", t, flags=re.I)

    t = re.sub(r"\s+", " ", t).strip(" -,:;")
    return t


def limpiar_lineas_contexto_fecha(lineas):
    limpias = []

    for linea in lineas:
        l = limpiar_ruido_fecha(linea)
        if not l:
            continue
        if re.fullmatch(r"[0-9\s:.\-h]+", l, flags=re.I):
            continue
        limpias.append(l)

    return limpias


# -------------------------
# PARSERS DE FECHA CONDEDUQUE
# -------------------------

def _anio_por_defecto_para_mes(mes_txt):
    hoy = date.today()
    mes_num = MESES.get(normalizar_texto_fecha(mes_txt))
    if not mes_num:
        return hoy.year

    anio = hoy.year
    if mes_num < hoy.month - 1:
        anio += 1
    return anio


def info_unica_local(f, texto):
    return {
        "tipo": "unica",
        "fecha": f,
        "fecha_inicio": f,
        "fecha_fin": f,
        "fechas_funcion": [f],
        "dias_semana": [],
        "texto_fecha_original": texto,
    }


def info_lista_local(fechas, texto):
    fechas = sorted(set(f for f in fechas if f))
    if not fechas:
        return None

    return {
        "tipo": "lista",
        "fecha": fechas[0],
        "fecha_inicio": fechas[0],
        "fecha_fin": fechas[-1],
        "fechas_funcion": fechas,
        "dias_semana": [],
        "texto_fecha_original": texto,
    }


def info_rango_local(fi, ff, texto):
    return {
        "tipo": "rango",
        "fecha": fi,
        "fecha_inicio": fi,
        "fecha_fin": ff,
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": texto,
    }


def info_patron_local(fi, ff, dias_semana, texto):
    dias_semana = sorted(set(d for d in dias_semana if isinstance(d, int) and 0 <= d <= 6))
    if not dias_semana:
        return None

    return {
        "tipo": "patron",
        "fecha": fi or ff,
        "fecha_inicio": fi,
        "fecha_fin": ff,
        "fechas_funcion": [],
        "dias_semana": dias_semana,
        "texto_fecha_original": texto,
    }


def parsear_fecha_texto_condeduque(texto):
    """
    Cubre:
    - Jueves 30 de abril de 2026
    - Viernes 29 de mayo 2026
    - 29 de mayo de 2026
    - 29 de mayo 2026
    - Viernes 24 de abril
    """
    if not texto:
        return None

    t = normalizar_texto_fecha(texto)

    patrones = [
        r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})",
        r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})\s+de\s+([a-z]+)\s+(20\d{2})",
        r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})",
        r"(\d{1,2})\s+de\s+([a-z]+)\s+(20\d{2})",
        r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})\s+de\s+([a-z]+)",
    ]

    for patron in patrones:
        m = re.fullmatch(patron, t)
        if not m:
            continue

        dia = int(m.group(1))
        mes_txt = m.group(2)

        if len(m.groups()) >= 3 and m.group(3):
            anio = int(m.group(3))
        else:
            anio = _anio_por_defecto_para_mes(mes_txt)

        f = construir_fecha(dia, mes_txt, anio)
        if f:
            return info_unica_local(f, texto)

    return None


def parsear_lista_breve_condeduque(texto):
    """
    Cubre:
    - 5 y 6 de junio de 2026
    - 8 y 9 de mayo de 2026
    """
    if not texto:
        return None

    t = normalizar_texto_fecha(texto)

    m = re.fullmatch(
        r"(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})",
        t
    )
    if not m:
        return None

    anio = int(m.group(4))
    fechas = [
        construir_fecha(int(m.group(1)), m.group(3), anio),
        construir_fecha(int(m.group(2)), m.group(3), anio),
    ]
    return info_lista_local(fechas, texto)


def parsear_rango_dias_condeduque(texto):
    """
    Cubre:
    - Del 24 de abril al 19 de julio de 2026
    """
    if not texto:
        return None

    t = normalizar_texto_fecha(texto)

    m = re.fullmatch(
        r"del\s+(\d{1,2})\s+de\s+([a-z]+)\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})",
        t
    )
    if not m:
        return None

    anio = int(m.group(5))
    fi = construir_fecha(int(m.group(1)), m.group(2), anio)
    ff = construir_fecha(int(m.group(3)), m.group(4), anio)
    if fi and ff:
        return info_rango_local(fi, ff, texto)

    return None


def parsear_rango_meses_condeduque(texto):
    """
    Cubre:
    - De octubre de 2025 a mayo de 2026
    - De octubre de 2025 a junio de 2026
    """
    if not texto:
        return None

    t = normalizar_texto_fecha(texto)

    m = re.fullmatch(
        r"de\s+([a-z]+)\s+de\s+(20\d{2})\s+a\s+([a-z]+)\s+de\s+(20\d{2})",
        t
    )
    if not m:
        return None

    mes_ini = m.group(1)
    anio_ini = int(m.group(2))
    mes_fin = m.group(3)
    anio_fin = int(m.group(4))

    fi = construir_fecha(1, mes_ini, anio_ini)
    udm = ultimo_dia_mes(mes_fin, anio_fin)
    ff = construir_fecha(udm, mes_fin, anio_fin) if udm else None

    if fi and ff:
        return info_rango_local(fi, ff, texto)

    return None


# -------------------------
# PARSER DE HORARIO CONDEDUQUE
# -------------------------

def _expandir_rango_dias(d1, d2):
    d1 = normalizar_texto_fecha(d1)
    d2 = normalizar_texto_fecha(d2)

    if d1 not in ORDEN_DIAS or d2 not in ORDEN_DIAS:
        return []

    i1 = ORDEN_DIAS.index(d1)
    i2 = ORDEN_DIAS.index(d2)

    if i1 <= i2:
        nombres = ORDEN_DIAS[i1:i2 + 1]
    else:
        nombres = ORDEN_DIAS[i1:] + ORDEN_DIAS[:i2 + 1]

    return [MAPA_DIAS[n] for n in nombres]


def extraer_dias_apertura_desde_horario(horario_lineas):
    """
    Ejemplos:
    - De martes a sábado ...
    - Domingos y festivos ...
    - Lunes cerrado
    """
    texto = " | ".join(horario_lineas or [])
    t = normalizar_texto_fecha(texto)

    incluidos = set()
    excluidos = set()

    # rangos: de martes a sabado
    for m in re.finditer(
        r"de\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t
    ):
        incluidos.update(_expandir_rango_dias(m.group(1), m.group(2)))

    # pares: domingos y festivos / viernes y sabados
    for m in re.finditer(
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+y\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b",
        t
    ):
        incluidos.add(MAPA_DIAS[m.group(1)])
        incluidos.add(MAPA_DIAS[m.group(2)])

    # días sueltos explícitos de apertura
    for nombre, idx in MAPA_DIAS.items():
        if re.search(rf"\b{re.escape(nombre)}\b", t):
            # si el propio fragmento dice cerrado, lo tratamos aparte
            pass

    # cierres explícitos
    for m in re.finditer(
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+cerrado\b",
        t
    ):
        excluidos.add(MAPA_DIAS[m.group(1)])

    # casos como "domingos y festivos"
    for m in re.finditer(
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b",
        t
    ):
        nombre = m.group(1)
        frag = t[max(0, m.start() - 20): min(len(t), m.end() + 20)]

        if "cerrado" in frag:
            excluidos.add(MAPA_DIAS[nombre])
        elif any(x in frag for x in [":", " h", " horas", " de "]):
            incluidos.add(MAPA_DIAS[nombre])

    dias = sorted(incluidos - excluidos)
    return dias


def convertir_rango_y_horario_a_patron(info_rango, horario_lineas):
    if not info_rango or info_rango.get("tipo") != "rango":
        return info_rango

    dias = extraer_dias_apertura_desde_horario(horario_lineas)
    if not dias:
        return info_rango

    texto = f"{info_rango.get('texto_fecha_original', '')} | {' | '.join(horario_lineas or [])}"

    return info_patron_local(
        info_rango.get("fecha_inicio"),
        info_rango.get("fecha_fin"),
        dias,
        texto,
    )


# -------------------------
# FALLBACK CUERPO
# -------------------------

def filtrar_fechas_futuras_de_textos(textos):
    hoy = date.today()
    futuras = []

    for texto in textos:
        texto_limpio = limpiar_ruido_fecha(texto)
        for f in extraer_fechas_explicitas(texto_limpio):
            if f >= hoy:
                futuras.append(f)

    futuras = sorted(set(futuras))

    if not futuras:
        return None

    if len(futuras) == 1:
        return info_unica_local(futuras[0], "fechas futuras extraidas del cuerpo")

    return info_lista_local(futuras, "fechas futuras extraidas del cuerpo")


# -------------------------
# PORTADA
# -------------------------

def es_url_evento_valida(url):
    if not url:
        return False

    url = url.strip().lower().rstrip("/")

    if "/actividades/" not in url:
        return False

    if url == "https://www.condeduquemadrid.es/programacion":
        return False

    return True


def extraer_urls_evento(soup):
    urls = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue

        href_abs = href if href.startswith("http") else urljoin(BASE_URL, href)

        if not es_url_evento_valida(href_abs):
            continue

        if href_abs not in vistos:
            vistos.add(href_abs)
            urls.append(href_abs)

    return urls


# -------------------------
# FICHA
# -------------------------

def extraer_lugar(lineas):
    espacio = extraer_seccion(lineas, "Espacio")
    if espacio:
        return limpiar_texto(espacio[0])
    return LUGAR


def resolver_fecha_condeduque(lineas, titulo_evento):
    fecha_lineas = extraer_seccion(lineas, "Fecha")
    horario_lineas = extraer_seccion(lineas, "Horario")

    fecha_txt = limpiar_ruido_fecha(" ".join(fecha_lineas))
    lineas_contexto = limpiar_lineas_contexto_fecha(lineas[:220])

    # 1) lista breve
    info = parsear_lista_breve_condeduque(fecha_txt)
    if info and info_fecha_sigue_vigente(info):
        return info

    # 2) fecha única específica Condeduque
    info = parsear_fecha_texto_condeduque(fecha_txt)
    if info and info_fecha_sigue_vigente(info):
        return info

    # 3) rango de días + posible patrón por horario
    info_rango = parsear_rango_dias_condeduque(fecha_txt)
    if info_rango:
        info_final = convertir_rango_y_horario_a_patron(info_rango, horario_lineas)
        if info_final and info_fecha_sigue_vigente(info_final):
            return info_final

    # 4) rango de meses + posible patrón por horario
    info_rango = parsear_rango_meses_condeduque(fecha_txt)
    if info_rango:
        info_final = convertir_rango_y_horario_a_patron(info_rango, horario_lineas)
        if info_final and info_fecha_sigue_vigente(info_final):
            return info_final

    # 5) resolvedor general como red de seguridad
    info = resolver_info_fecha_de_bloques(
        textos_portada=[],
        textos_ficha=[fecha_txt] + horario_lineas + lineas_contexto,
        titulo_evento=titulo_evento,
    )
    if info and info_fecha_sigue_vigente(info):
        return info

    # 6) fallback con fechas futuras explícitas del cuerpo
    info = filtrar_fechas_futuras_de_textos(lineas_contexto)
    if info and info_fecha_sigue_vigente(info):
        return info

    return None


def extraer_evento_desde_ficha(session, url_evento):
    soup = BeautifulSoup(get_url(url_evento, session=session, timeout=20).text, "html.parser")
    lineas = extraer_lineas(soup)

    titulo = extraer_titulo(soup)
    if not titulo:
        return None

    lugar = extraer_lugar(lineas)
    info_fecha = resolver_fecha_condeduque(lineas, titulo)

    if not info_fecha:
        avisar(f"Sin fecha en Condeduque: {url_evento}")
        return None

    if not info_fecha_sigue_vigente(info_fecha):
        return None

    return {
        "titulo": titulo,
        "fecha": fecha_representativa(info_fecha),
        "lugar": lugar,
        "url_evento": url_evento,
        "fuente": BASE_URL,
        "tipo_fecha": info_fecha.get("tipo"),
        "rango_fechas": info_fecha.get("tipo") in {"rango", "hasta", "desde", "patron"},
        "fecha_inicio": info_fecha.get("fecha_inicio"),
        "fecha_fin": info_fecha.get("fecha_fin"),
        "fechas_funcion": [
            f.isoformat() if hasattr(f, "isoformat") else f
            for f in (info_fecha.get("fechas_funcion") or [])
        ],
        "dias_semana": info_fecha.get("dias_semana", []),
        "texto_fecha_original": info_fecha.get("texto_fecha_original", ""),
    }


def sacar_condeduque():
    eventos = []
    vistos = set()
    session = requests.Session()

    soup = BeautifulSoup(get_url(BASE_URL, session=session, timeout=20).text, "html.parser")
    urls_evento = extraer_urls_evento(soup)

    for url_evento in urls_evento:
        try:
            evento = extraer_evento_desde_ficha(session, url_evento)
            if not evento:
                continue

            agregar_evento(
                eventos,
                vistos,
                evento["titulo"],
                evento["fecha"],
                evento["lugar"],
                evento["url_evento"],
                evento["fuente"],
                info_fecha={
                    "tipo_fecha": evento["tipo_fecha"],
                    "fecha": evento["fecha"],
                    "fecha_inicio": evento["fecha_inicio"],
                    "fecha_fin": evento["fecha_fin"],
                    "fechas_funcion": evento["fechas_funcion"],
                    "dias_semana": evento["dias_semana"],
                    "texto_fecha_original": evento["texto_fecha_original"],
                }
            )
        except Exception as e:
            avisar(f"Error en ficha Condeduque {url_evento}: {e}")

    return eventos