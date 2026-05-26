import requests
import re
import unicodedata
from urllib.parse import urljoin

from utils import agregar_evento, get_url
from helpers.texto import normalizar_texto
from helpers.avisos import avisar
from helpers.fichas import abrir_ficha, extraer_titulo, extraer_lineas
from helpers.fechas_eventos import fecha_representativa, info_fecha_sigue_vigente
from helpers.resolver_fechas import resolver_info_fecha_de_bloques


MESES_FIGARO_RE = (
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre"
)

DIAS_FIGARO_RE = r"lunes|martes|miercoles|jueves|viernes|sabado|domingo"


def _normalizar_para_regex(texto):
    if not texto:
        return ""

    texto = " ".join(str(texto).split()).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def _deduplicar_lineas(lineas):
    resultado = []
    vistos = set()

    for linea in lineas:
        if not linea:
            continue

        clave = _normalizar_para_regex(linea)
        if not clave or clave in vistos:
            continue

        vistos.add(clave)
        resultado.append(linea)

    return resultado


def _lineas_extra_figaro(linea):
    """
    Normalizaciones locales para GruposMedia / Teatro Figaro.

    La idea es NO tocar los parsers compartidos, para no afectar a otras salas.
    Generamos lineas sintéticas que el resolver actual ya sabe interpretar.
    """
    extras = []
    t = _normalizar_para_regex(linea)

    if not t:
        return extras

    # Caso Los del Camping:
    # "Martes a sábados a las 20:00 horas"
    # El parser compartido entiende mejor "De martes a sabado".
    for m in re.finditer(
        rf"\b({DIAS_FIGARO_RE})s?\s+a\s+({DIAS_FIGARO_RE})s?\b",
        t,
    ):
        dia_inicio = m.group(1)
        dia_fin = m.group(2)
        extras.append(f"De {dia_inicio} a {dia_fin}")

    # Caso Angel Martin:
    # "22 mayo y 6 y 12 junio de 2026"
    # Lo convertimos en fechas que el parser compartido ya contempla.
    for m in re.finditer(
        rf"\b(\d{{1,2}})\s+(?:de\s+)?({MESES_FIGARO_RE})\s+y\s+"
        rf"(\d{{1,2}})\s+y\s+(\d{{1,2}})\s+(?:de\s+)?({MESES_FIGARO_RE})\s+"
        rf"(?:de\s+)?(20\d{{2}})\b",
        t,
    ):
        dia_1, mes_1, dia_2, dia_3, mes_2, anio = m.groups()
        extras.append(f"{dia_1} de {mes_1} de {anio}")
        extras.append(f"{dia_2} y {dia_3} de {mes_2} de {anio}")

    # Caso Noticiero de Nosoloviernes:
    # "20 de noviembre 2026 y 16 de enero 2027"
    # Evitamos tocar rangos tipo "Del 2 de julio al 9 de agosto de 2026".
    if " y " in t and not re.search(r"\bdel\b.*\bal\b", t):
        for m in re.finditer(
            rf"\b(\d{{1,2}})\s+(?:de\s+)?({MESES_FIGARO_RE})\s+(?:de\s+)?(20\d{{2}})\b",
            t,
        ):
            dia, mes, anio = m.groups()
            extras.append(f"{dia} de {mes} de {anio}")

    return extras


def preprocesar_textos_figaro(textos):
    textos = [str(t).strip() for t in (textos or []) if t and str(t).strip()]

    resultado = []
    for linea in textos:
        resultado.append(linea)
        resultado.extend(_lineas_extra_figaro(linea))

    return _deduplicar_lineas(resultado)


def es_url_evento_valida(href):
    if not href:
        return False

    href = href.strip().lower()

    if not href.startswith("http"):
        return False

    if "/cartelera/" not in href:
        return False

    if href.rstrip("/") == "https://gruposmedia.com/cartelera":
        return False

    return True


def extraer_textos_fecha_ficha(session, url_evento):
    soup = abrir_ficha(session, url_evento)
    if not soup:
        return None, [], []

    titulo = extraer_titulo(soup)

    lineas_helper = extraer_lineas(soup)[:300]

    lineas_crudas = [
        l.strip()
        for l in soup.get_text("\n", strip=True).splitlines()
        if l.strip()
    ][:400]

    return titulo, lineas_helper, lineas_crudas


def sacar_figaro():
    url = "https://gruposmedia.com/teatro-figaro/"
    eventos = []
    vistos = set()

    session = requests.Session()
    respuesta = get_url(url, session=session, timeout=10)

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(respuesta.text, "html.parser")

    enlaces = soup.find_all("a", href=True)

    candidatos = {}

    for a in enlaces:
        texto = a.get_text(" ", strip=True)
        href = a["href"].strip()

        href = urljoin(url, href)

        if not es_url_evento_valida(href):
            continue

        # No filtramos por texto visible del enlace.
        # Algunas tarjetas pueden tener enlaces de imagen/boton con texto vacio,
        # y el titulo real lo sacamos despues desde la ficha.
        if href not in candidatos:
            candidatos[href] = texto or ""

    for url_evento, titulo in candidatos.items():
        titulo_final = titulo

        titulo_ficha, lineas_helper, lineas_crudas = extraer_textos_fecha_ficha(session, url_evento)

        if titulo_ficha:
            titulo_final = titulo_ficha

        textos_ficha = []
        textos_ficha.extend(lineas_helper or [])
        textos_ficha.extend(lineas_crudas or [])
        textos_ficha = preprocesar_textos_figaro(textos_ficha)

        info_fecha = resolver_info_fecha_de_bloques(
            textos_portada=[],
            textos_ficha=textos_ficha,
            titulo_evento=titulo_final,
        )

        if not info_fecha:
            avisar(f"Sin fecha resuelta en Figaro: {url_evento}")
            continue

        if not info_fecha_sigue_vigente(info_fecha):
            continue

        agregar_evento(
            eventos,
            vistos,
            titulo_final,
            fecha_representativa(info_fecha),
            "Teatro Figaro",
            url_evento,
            url,
            info_fecha=info_fecha
        )

    return eventos