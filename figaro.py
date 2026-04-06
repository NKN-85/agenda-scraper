import requests
import re
from datetime import date
from urllib.parse import urljoin

from utils import HEADERS, agregar_evento, get_url
from helpers.texto import normalizar_texto
from helpers.avisos import avisar
from helpers.fichas import abrir_ficha, extraer_titulo, extraer_lineas


def convertir_fecha_figaro(texto):
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        "gennaio": 1, "febbraio": 2, "aprile": 4, "maggio": 5,
        "giugno": 6, "luglio": 7, "settembre": 9,
        "ottobre": 10, "dicembre": 12,
    }

    texto = texto.strip().lower()

    patrones = [
        r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        r"desde\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        r"(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\s+(\d{1,2})\s+([a-zàéèìòù]+)\s+(\d{4})",
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+y\s+\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+(\d{4})",
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s*,\s*\d{1,2}\s+de\s+[a-záéíóú]+\s*,\s*\d{1,2}\s+de\s+[a-záéíóú]+\s+y\s+\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+(\d{4})",
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s*,\s*\d{1,2}\s+de\s+[a-záéíóú]+\s+y\s+\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+(\d{4})",
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
    ]

    for patron in patrones:
        m = re.search(patron, texto)
        if m:
            dia = int(m.group(1))
            mes = meses.get(m.group(2))
            anio = int(m.group(3))
            if mes:
                return date(anio, mes, dia)

    m1 = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s*,", texto)
    m2 = re.search(r"de\s+(\d{4})", texto)
    if m1 and m2:
        dia = int(m1.group(1))
        mes = meses.get(m1.group(2))
        anio = int(m2.group(1))
        if mes:
            return date(anio, mes, dia)

    return None


def sacar_fecha_desde_pagina_evento(session, url_evento):
    soup = abrir_ficha(session, url_evento)
    if not soup:
        return None, None, None

    titulo = extraer_titulo(soup)
    lineas = extraer_lineas(soup)

    for linea in lineas[:140]:
        fecha = convertir_fecha_figaro(linea)
        if fecha:
            return titulo, fecha, linea

    avisar(f"Sin fecha en ficha: {url_evento}")
    return None, None, None


def sacar_figaro():
    url = "https://gruposmedia.com/teatro-figaro/"
    eventos = []
    vistos = set()

    session = requests.Session()

    # 🔥 CAMBIO AQUÍ
    respuesta = get_url(url, session=session, timeout=8)

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(respuesta.text, "html.parser")

    lineas = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]

    titulos_ignorar = {
        "entradas", "espectáculos en cartelera", "teatro fígaro",
        "teatro figaro", "cartelera", "home", "inicio",
        "cómo llegar", "plano de localidades", "crea tu evento",
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

        texto_norm = normalizar_texto(texto)

        if texto_norm in titulos_ignorar:
            continue

        if "/cartelera/" in href and href != "https://gruposmedia.com/cartelera/":
            if 4 <= len(texto) <= 120:
                titulos_validos[texto_norm] = (texto, href)

    candidatos = []
    for i, linea in enumerate(lineas):
        linea_norm = normalizar_texto(linea)
        if linea_norm in titulos_validos:
            titulo, url_evento = titulos_validos[linea_norm]
            candidatos.append((titulo, url_evento, i))

    candidatos_unicos = []
    urls_vistas = set()
    for titulo, url_evento, idx in candidatos:
        if url_evento not in urls_vistas:
            urls_vistas.add(url_evento)
            candidatos_unicos.append((titulo, url_evento, idx))

    rescatar = []

    for titulo, url_evento, idx in candidatos_unicos:
        fecha_evento = None
        texto_fecha = None

        ventana = lineas[idx + 1:min(idx + 15, len(lineas))]

        for candidato in ventana:
            fecha_evento = convertir_fecha_figaro(candidato)
            if fecha_evento:
                texto_fecha = candidato
                break

        if fecha_evento:
            if fecha_evento >= date.today() or (
                texto_fecha and normalizar_texto(texto_fecha).startswith("desde el ")
            ):
                agregar_evento(
                    eventos,
                    vistos,
                    titulo,
                    fecha_evento,
                    "Teatro Fígaro",
                    url_evento,
                    url
                )
        else:
            rescatar.append((titulo, url_evento))

    for titulo, url_evento in rescatar:
        titulo_real, fecha_evento, texto_fecha = sacar_fecha_desde_pagina_evento(session, url_evento)

        if fecha_evento:
            if fecha_evento >= date.today() or (
                texto_fecha and normalizar_texto(texto_fecha).startswith("desde el ")
            ):
                agregar_evento(
                    eventos,
                    vistos,
                    titulo_real or titulo,
                    fecha_evento,
                    "Teatro Fígaro",
                    url_evento,
                    url
                )

    return eventos