import requests
import re
from datetime import date
from urllib.parse import urljoin

from utils import HEADERS, agregar_evento
from helpers.texto import normalizar_texto
from helpers.avisos import avisar
from helpers.fichas import abrir_ficha, extraer_titulo, extraer_lineas


def convertir_fecha_alcazar(texto):
    meses = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    texto = texto.strip().lower()

    # Caso especial: "Del 15 de agosto de 2025 al 28 de junio de 2026"
    # Nos interesa la fecha FINAL.
    m = re.search(
        r"del\s+\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        dia = int(m.group(1))
        mes = meses.get(m.group(2))
        anio = int(m.group(3))
        if mes:
            return date(anio, mes, dia)

    # Caso: "Del 20 de agosto al 27 de septiembre de 2026"
    # Nos interesa la fecha FINAL.
    m = re.search(
        r"del\s+\d{1,2}\s+de\s+[a-záéíóú]+\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        dia = int(m.group(1))
        mes = meses.get(m.group(2))
        anio = int(m.group(3))
        if mes:
            return date(anio, mes, dia)

    patrones = [
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        r"desde\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        r"días?\s+(\d{1,2})\s*,\s*\d{1,2}\s+y\s+\d{1,2}\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        r"(\d{1,2})\s+y\s+\d{1,2}\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
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

    # Caso: "20 de marzo, 24 de abril, 22 de mayo y 19 de junio de 2026"
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

    for linea in lineas[:150]:
        fecha = convertir_fecha_alcazar(linea)
        if fecha:
            return titulo, fecha, linea

    avisar(f"Sin fecha en ficha: {url_evento}")
    return None, None, None


def sacar_alcazar():
    url = "https://gruposmedia.com/teatro-alcazar/"
    eventos = []
    vistos = set()

    session = requests.Session()

    respuesta = session.get(url, headers=HEADERS, verify=False, timeout=10)
    respuesta.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(respuesta.text, "html.parser")

    lineas = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]

    titulos_ignorar = {
        "entradas",
        "espectáculos en cartelera",
        "teatro alcázar",
        "cartelera",
        "home",
        "inicio",
        "cómo llegar",
        "plano de localidades",
        "crea tu evento",
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
            if 4 <= len(texto) <= 100:
                titulos_validos[texto_norm] = (texto, href)

    candidatos = []

    for i, linea in enumerate(lineas):
        linea_norm = normalizar_texto(linea)

        if linea_norm in titulos_validos:
            titulo, url_evento = titulos_validos[linea_norm]
            candidatos.append((titulo, url_evento, i))

    # quitar duplicados por URL
    candidatos_unicos = []
    urls_vistas = set()
    for titulo, url_evento, idx in candidatos:
        if url_evento not in urls_vistas:
            urls_vistas.add(url_evento)
            candidatos_unicos.append((titulo, url_evento, idx))

    for titulo, url_evento, idx in candidatos_unicos:
        fecha_evento = None

        # primero: intentar sacar fecha en la página principal
        for j in range(idx + 1, min(idx + 12, len(lineas))):
            candidato = lineas[j]
            fecha_evento = convertir_fecha_alcazar(candidato)
            if fecha_evento:
                break

        # segundo: si no sale, mirar ficha individual
        titulo_final = titulo
        if not fecha_evento:
            titulo_real, fecha_evento, _ = sacar_fecha_desde_pagina_evento(session, url_evento)
            if titulo_real:
                titulo_final = titulo_real

        if fecha_evento and fecha_evento >= date.today():
            agregar_evento(
                eventos,
                vistos,
                titulo_final,
                fecha_evento,
                "Teatro Alcázar",
                url_evento,
                url
            )

    return eventos