import requests
from urllib.parse import urljoin

from utils import agregar_evento, get_url
from helpers.texto import normalizar_texto
from helpers.avisos import avisar
from helpers.fichas import abrir_ficha, extraer_titulo, extraer_lineas
from helpers.fechas_eventos import fecha_representativa, info_fecha_sigue_vigente
from helpers.resolver_fechas import resolver_info_fecha_de_bloques


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


def sacar_granvia():
    url = "https://gruposmedia.com/teatro-gran-via/"
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

        if not texto or len(texto) < 4:
            continue

        texto_norm = normalizar_texto(texto)

        # evitar duplicados por URL
        if href not in candidatos:
            candidatos[href] = texto

    for url_evento, titulo in candidatos.items():
        titulo_final = titulo

        # ⚠️ ya no usamos portada → solo ficha (mucho más fiable)
        titulo_ficha, lineas_helper, lineas_crudas = extraer_textos_fecha_ficha(session, url_evento)

        if titulo_ficha:
            titulo_final = titulo_ficha

        textos_ficha = []
        textos_ficha.extend(lineas_helper or [])
        textos_ficha.extend(lineas_crudas or [])

        info_fecha = resolver_info_fecha_de_bloques(
            textos_portada=[],
            textos_ficha=textos_ficha,
            titulo_evento=titulo_final,
        )

        if not info_fecha:
            avisar(f"Sin fecha resuelta en Gran Vía: {url_evento}")
            continue

        if not info_fecha_sigue_vigente(info_fecha):
            continue

        agregar_evento(
            eventos,
            vistos,
            titulo_final,
            fecha_representativa(info_fecha),
            "Teatro Gran Vía",
            url_evento,
            url,
            info_fecha=info_fecha
        )

    return eventos