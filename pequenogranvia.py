import requests
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin

from utils import agregar_evento, get_url
from helpers.texto import normalizar_texto
from helpers.avisos import avisar
from helpers.fichas import abrir_ficha, extraer_titulo, extraer_lineas


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


MESES_RE = (
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre"
)


def normalizar_fecha_texto(texto):
    if not texto:
        return ""

    texto = " ".join(str(texto).split()).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def construir_fecha_segura(dia, mes_txt, anio):
    mes = MESES.get(normalizar_fecha_texto(mes_txt))
    if not mes:
        return None

    try:
        return date(int(anio), mes, int(dia))
    except Exception:
        return None


def inferir_anio(texto):
    anios = re.findall(r"\b(20\d{2})\b", normalizar_fecha_texto(texto))
    if not anios:
        return None
    return int(anios[-1])


def extraer_info_funciones_pequenogranvia(texto):
    """
    Parser específico para líneas/bloques tipo:
    Del 29 de mayo al 25 de septiembre de 2026 - Funciones:
    29 mayo, 19 junio, 10 julio, 7 agosto y 25 septiembre.

    Solo devuelve las fechas que aparecen DESPUÉS de "Funciones",
    no el rango completo.
    """
    if not texto:
        return None

    original = texto
    t = normalizar_fecha_texto(texto)

    if "funcion" not in t:
        return None

    anio = inferir_anio(t)
    if not anio:
        return None

    m = re.search(r"funciones?\s*:?\s*(.+)$", t)
    if not m:
        return None

    bloque = m.group(1)

    # Cortes defensivos por si el texto completo de la ficha continúa con otros apartados.
    bloque = re.split(
        r"\b(?:comprar|entradas|sinopsis|reparto|ficha|duracion|duración|precio|horario|teatro|accesibilidad)\b",
        bloque,
        maxsplit=1,
    )[0]

    fechas = []
    for m_fecha in re.finditer(
        rf"\b(\d{{1,2}})\s+(?:de\s+)?({MESES_RE})\b",
        bloque,
    ):
        f = construir_fecha_segura(m_fecha.group(1), m_fecha.group(2), anio)
        if f:
            fechas.append(f)

    fechas = sorted(set(fechas))

    if not fechas:
        return None

    return {
        "tipo": "lista" if len(fechas) >= 2 else "unica",
        "fechas": fechas,
        "fecha": fechas[0],
        "texto_fecha_original": original,
    }


def extraer_fechas_explicitas_pequenogranvia(texto):
    """
    Extrae fechas explícitas típicas de GruposMedia / Pequeño Teatro Gran Vía.

    Casos soportados, entre otros:
    - 13 de junio 2026
    - 12 de junio y 14 de julio de 2026
    - 6 de junio y 17 de julio de 2026
    - Funciones: 29 mayo, 19 junio, 10 julio, 7 agosto y 25 septiembre.
    - 29 de mayo, 19 de junio, 10 de julio, 7 de agosto y 25 de septiembre de 2026
    """
    t = normalizar_fecha_texto(texto)
    fechas = set()
    anio_inferido = inferir_anio(t)

    # 12 de junio y 14 de julio de 2026
    # 6 de junio y 17 de julio de 2026
    for m in re.finditer(
        rf"\b(\d{{1,2}})\s+(?:de\s+)?({MESES_RE})\s+y\s+"
        rf"(\d{{1,2}})\s+(?:de\s+)?({MESES_RE})\s+(?:de\s+)?(20\d{{2}})\b",
        t,
    ):
        anio = int(m.group(5))
        for dia, mes in ((m.group(1), m.group(2)), (m.group(3), m.group(4))):
            f = construir_fecha_segura(dia, mes, anio)
            if f:
                fechas.add(f)

    # 10 y 11 de mayo de 2026 / 10 y 11 mayo 2026
    for m in re.finditer(
        rf"\b(\d{{1,2}})\s+y\s+(\d{{1,2}})\s+(?:de\s+)?({MESES_RE})\s+(?:de\s+)?(20\d{{2}})\b",
        t,
    ):
        anio = int(m.group(4))
        for dia in (m.group(1), m.group(2)):
            f = construir_fecha_segura(dia, m.group(3), anio)
            if f:
                fechas.add(f)

    # Listas tipo:
    # Funciones: 29 mayo, 19 junio, 10 julio, 7 agosto y 25 septiembre.
    # El año se infiere del texto completo: "... de 2026 - Funciones: ..."
    if anio_inferido:
        for m in re.finditer(
            rf"\b(\d{{1,2}})\s+(?:de\s+)?({MESES_RE})\b",
            t,
        ):
            # Evita duplicar rangos, no pasa nada si se duplica, pero dejamos set igualmente.
            f = construir_fecha_segura(m.group(1), m.group(2), anio_inferido)
            if f:
                fechas.add(f)

    # Fechas con año propio:
    # 13 de junio 2026 / 13 de junio de 2026 / 13 junio 2026
    for m in re.finditer(
        rf"\b(\d{{1,2}})\s+(?:de\s+)?({MESES_RE})\s+(?:de\s+)?(20\d{{2}})\b",
        t,
    ):
        f = construir_fecha_segura(m.group(1), m.group(2), m.group(3))
        if f:
            fechas.add(f)

    return sorted(fechas)


def convertir_info_a_info_fecha(info, texto_original=None):
    if not info:
        return None

    tipo = info.get("tipo")

    if tipo == "unica":
        fecha = info.get("fecha")
        return {
            "tipo": "unica",
            "fecha": fecha,
            "fecha_inicio": fecha,
            "fecha_fin": fecha,
            "fechas_funcion": [fecha] if fecha else [],
            "dias_semana": [],
            "texto_fecha_original": texto_original or info.get("texto_fecha_original"),
        }

    if tipo == "lista":
        fechas = sorted(info.get("fechas") or [])
        return {
            "tipo": "lista",
            "fecha": fechas[0] if fechas else None,
            "fecha_inicio": fechas[0] if fechas else None,
            "fecha_fin": fechas[-1] if fechas else None,
            "fechas_funcion": fechas,
            "dias_semana": [],
            "texto_fecha_original": texto_original or info.get("texto_fecha_original"),
        }

    if tipo == "rango":
        return {
            "tipo": "rango",
            "fecha": info.get("fecha_inicio"),
            "fecha_inicio": info.get("fecha_inicio"),
            "fecha_fin": info.get("fecha_fin"),
            "fechas_funcion": [],
            "dias_semana": [],
            "texto_fecha_original": texto_original or info.get("texto_fecha_original"),
        }

    if tipo == "hasta":
        return {
            "tipo": "hasta",
            "fecha": info.get("fecha_fin"),
            "fecha_inicio": None,
            "fecha_fin": info.get("fecha_fin"),
            "fechas_funcion": [],
            "dias_semana": [],
            "texto_fecha_original": texto_original or info.get("texto_fecha_original"),
        }

    if tipo == "desde":
        return {
            "tipo": "desde",
            "fecha": info.get("fecha_inicio"),
            "fecha_inicio": info.get("fecha_inicio"),
            "fecha_fin": None,
            "fechas_funcion": [],
            "dias_semana": [],
            "texto_fecha_original": texto_original or info.get("texto_fecha_original"),
        }

    return None


def convertir_fecha_pequenogranvia(texto):
    texto_original = texto
    texto = normalizar_fecha_texto(texto)

    # Prioridad máxima: si hay "Funciones", solo deben contar las fechas
    # posteriores a esa etiqueta. No mezclamos con el rango "Del ... al ...".
    info_funciones = extraer_info_funciones_pequenogranvia(texto_original)
    if info_funciones:
        return info_funciones

    fechas_explicitas = extraer_fechas_explicitas_pequenogranvia(texto_original)

    # Del 15 de abril de 2026 al 27 de mayo de 2026
    m = re.search(
        rf"del\s+(\d{{1,2}})\s+de\s+({MESES_RE})\s+de\s+(\d{{4}})\s+al\s+"
        rf"(\d{{1,2}})\s+de\s+({MESES_RE})\s+de\s+(\d{{4}})",
        texto,
    )
    if m:
        return {
            "tipo": "rango",
            "fecha_inicio": construir_fecha_segura(m.group(1), m.group(2), m.group(3)),
            "fecha_fin": construir_fecha_segura(m.group(4), m.group(5), m.group(6)),
            "texto_fecha_original": texto_original,
        }

    # Del 15 de abril al 27 de mayo de 2026
    m = re.search(
        rf"del\s+(\d{{1,2}})\s+de\s+({MESES_RE})\s+al\s+"
        rf"(\d{{1,2}})\s+de\s+({MESES_RE})\s+de\s+(\d{{4}})",
        texto,
    )
    if m:
        return {
            "tipo": "rango",
            "fecha_inicio": construir_fecha_segura(m.group(1), m.group(2), m.group(5)),
            "fecha_fin": construir_fecha_segura(m.group(3), m.group(4), m.group(5)),
            "texto_fecha_original": texto_original,
        }

    # Del 15 al 27 de mayo de 2026
    m = re.search(
        rf"del\s+(\d{{1,2}})\s+al\s+(\d{{1,2}})\s+de\s+({MESES_RE})\s+de\s+(\d{{4}})",
        texto,
    )
    if m:
        return {
            "tipo": "rango",
            "fecha_inicio": construir_fecha_segura(m.group(1), m.group(3), m.group(4)),
            "fecha_fin": construir_fecha_segura(m.group(2), m.group(3), m.group(4)),
            "texto_fecha_original": texto_original,
        }

    # Hasta el 27 de mayo de 2026
    m = re.search(
        rf"hasta\s+el\s+(\d{{1,2}})\s+de\s+({MESES_RE})\s+de\s+(\d{{4}})",
        texto,
    )
    if m:
        return {
            "tipo": "hasta",
            "fecha_fin": construir_fecha_segura(m.group(1), m.group(2), m.group(3)),
            "texto_fecha_original": texto_original,
        }

    # Desde el 15 de abril de 2026
    m = re.search(
        rf"desde\s+el\s+(\d{{1,2}})\s+de\s+({MESES_RE})\s+de\s+(\d{{4}})",
        texto,
    )
    if m:
        return {
            "tipo": "desde",
            "fecha_inicio": construir_fecha_segura(m.group(1), m.group(2), m.group(3)),
            "texto_fecha_original": texto_original,
        }

    if len(fechas_explicitas) >= 2:
        return {
            "tipo": "lista",
            "fechas": fechas_explicitas,
            "texto_fecha_original": texto_original,
        }

    if len(fechas_explicitas) == 1:
        return {
            "tipo": "unica",
            "fecha": fechas_explicitas[0],
            "texto_fecha_original": texto_original,
        }

    return None


def evento_sigue_vigente(info):
    hoy = date.today()

    if info["tipo"] == "unica":
        return info["fecha"] >= hoy

    if info["tipo"] == "lista":
        return any(f >= hoy for f in info["fechas"])

    if info["tipo"] == "rango":
        return info["fecha_fin"] >= hoy

    if info["tipo"] == "hasta":
        return info["fecha_fin"] >= hoy

    if info["tipo"] == "desde":
        return True

    return False


def obtener_fecha_representativa(info):
    if info["tipo"] == "unica":
        return info["fecha"]

    if info["tipo"] == "lista":
        return min(info["fechas"])

    if info["tipo"] == "rango":
        return info["fecha_inicio"]

    if info["tipo"] == "hasta":
        return date.today()

    if info["tipo"] == "desde":
        return info["fecha_inicio"]

    return None


def es_url_cartelera_generica(url_evento):
    if not url_evento:
        return True
    return url_evento.strip().rstrip("/").lower() == "https://gruposmedia.com/cartelera"


def sacar_fecha_desde_pagina_evento(session, url_evento):
    if es_url_cartelera_generica(url_evento):
        return None, None

    soup = abrir_ficha(session, url_evento)
    if not soup:
        return None, None

    titulo = extraer_titulo(soup)

    lineas_helper = extraer_lineas(soup)[:180]
    lineas_crudas = [
        l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()
    ][:320]

    todas_lineas = []
    for linea in lineas_helper + lineas_crudas:
        linea = limpiar_texto(linea)
        if linea and linea not in todas_lineas:
            todas_lineas.append(linea)

    # 1) PRIORIDAD ABSOLUTA: bloque "Funciones".
    # Buscamos en el texto completo primero porque en GruposMedia a veces
    # el rango y las funciones quedan separados por saltos de línea.
    texto_completo = " ".join(todas_lineas)
    info = extraer_info_funciones_pequenogranvia(texto_completo)
    if info:
        return titulo, info

    # 2) Ventanas cortas alrededor de la palabra "Funciones".
    # Esto cubre fichas donde la etiqueta "Funciones:" aparece en una línea
    # y la lista de fechas en la siguiente.
    for i, linea in enumerate(todas_lineas):
        if "funcion" not in normalizar_fecha_texto(linea):
            continue

        inicio = max(0, i - 2)
        fin = min(len(todas_lineas), i + 8)
        ventana = " ".join(todas_lineas[inicio:fin])

        info = extraer_info_funciones_pequenogranvia(ventana)
        if info:
            return titulo, info

    # 3) Si no hay funciones explícitas, usamos el comportamiento anterior.
    for linea in lineas_helper:
        info = convertir_fecha_pequenogranvia(linea)
        if info:
            return titulo, info

    for linea in lineas_crudas:
        info = convertir_fecha_pequenogranvia(linea)
        if info:
            return titulo, info

    avisar(f"Sin fecha en ficha: {url_evento}")
    return titulo, None

def sacar_pequenogranvia():
    url = "https://gruposmedia.com/pequeno-teatro-gran-via/"
    eventos = []
    vistos = set()

    session = requests.Session()
    respuesta = get_url(url, session=session, timeout=10)

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(respuesta.text, "html.parser")

    lineas = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]

    titulos_ignorar = {
        "entradas",
        "espectáculos en cartelera",
        "espectaculos en cartelera",
        "pequeño teatro gran vía",
        "pequeno teatro gran via",
        "cartelera",
        "home",
        "inicio",
        "cómo llegar",
        "como llegar",
        "plano de localidades",
        "crea tu evento",
        "calendario de actuaciones",
    }

    titulos_validos = {}

    for a in soup.find_all("a", href=True):
        texto = a.get_text(" ", strip=True)
        href = a["href"].strip()

        if not texto or not href:
            continue

        href = urljoin(url, href)

        if not href.startswith("http"):
            continue

        if es_url_cartelera_generica(href):
            continue

        texto_norm = normalizar_texto(texto)

        if texto_norm in titulos_ignorar:
            continue

        if "/cartelera/" in href:
            if 4 <= len(texto) <= 120:
                titulos_validos[texto_norm] = (texto, href)

    urls_vistas = set()

    for i, linea in enumerate(lineas):
        linea_norm = normalizar_texto(linea)

        if linea_norm not in titulos_validos:
            continue

        titulo, url_evento = titulos_validos[linea_norm]

        if url_evento in urls_vistas or es_url_cartelera_generica(url_evento):
            continue

        urls_vistas.add(url_evento)

        info_portada = None
        titulo_final = titulo

        for j in range(i + 1, min(i + 15, len(lineas))):
            info_portada = convertir_fecha_pequenogranvia(lineas[j])
            if info_portada:
                break

        # Importante: en esta sala la portada puede tener una fecha representativa
        # o de calendario que no coincide con la ficha. Por eso la ficha manda.
        titulo_real, info_ficha = sacar_fecha_desde_pagina_evento(session, url_evento)
        if titulo_real:
            titulo_final = titulo_real

        info = info_ficha or info_portada

        if not info:
            continue

        if not evento_sigue_vigente(info):
            continue

        fecha_evento = obtener_fecha_representativa(info)
        if not fecha_evento:
            continue

        info_fecha = convertir_info_a_info_fecha(
            info,
            texto_original=info.get("texto_fecha_original"),
        )

        agregar_evento(
            eventos,
            vistos,
            titulo_final,
            fecha_evento,
            "Pequeño Teatro Gran Vía",
            url_evento,
            url,
            info_fecha=info_fecha,
        )

    return eventos