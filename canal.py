import requests
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import (
    HEADERS,
    limpiar_texto,
    es_futura_o_hoy,
    agregar_evento,
    construir_fecha,
    get_url
)


def convertir_fecha_canal(texto):
    texto = limpiar_texto(texto).lower()

    def mk(dia, mes_txt, anio):
        return construir_fecha(dia, mes_txt, anio)

    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+(\d{4})",
        texto
    )
    if m:
        return mk(int(m.group(1)), m.group(2), int(m.group(3)))

    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+\d{1,2}\s+de\s+[a-záéíóú]+",
        texto
    )
    if m:
        return mk(int(m.group(1)), m.group(2), date.today().year)

    m = re.search(
        r"(\d{1,2})\s*,\s*\d{1,2}\s+y\s+\d{1,2}\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return mk(int(m.group(1)), m.group(2), int(m.group(3)))

    m = re.search(
        r"(\d{1,2})(?:\s*,\s*\d{1,2})+\s+y\s+\d{1,2}\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return mk(int(m.group(1)), m.group(2), int(m.group(3)))

    m = re.search(
        r"(\d{1,2})\s+y\s+\d{1,2}\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return mk(int(m.group(1)), m.group(2), int(m.group(3)))

    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(\d{4})",
        texto
    )
    if m:
        return mk(int(m.group(1)), m.group(2), int(m.group(3)))

    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return mk(int(m.group(1)), m.group(2), int(m.group(3)))

    return None


def sacar_canal():
    url = "https://www.teatroscanal.com/cartelera-madrid/"
    lugar = "Teatros del Canal"

    eventos = []
    vistos = set()

    try:
        # 🔥 CAMBIO AQUÍ (adiós get_html)
        r = get_url(url, timeout=40)
    except requests.exceptions.RequestException as e:
        print(f"[canal] fuente omitida: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    lineas = [
        limpiar_texto(l)
        for l in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(l)
    ]

    urls_ordenadas = []
    for a in soup.find_all("a", href=True):
        texto = limpiar_texto(a.get_text(" ", strip=True))
        href = urljoin(url, a.get("href", "").strip())

        if texto == "+ Info" and href not in urls_ordenadas:
            urls_ordenadas.append(href)

    candidatos = []

    i = 0
    while i < len(lineas):
        linea = lineas[i]

        if linea in {
            "+ Info",
            "Comprar",
            "PRÓXIMAMENTE",
            "CONSULTA AQUÍ EL PDF CON LA PROGRAMACIÓN",
        }:
            i += 1
            continue

        fecha_evento = convertir_fecha_canal(linea)
        if not fecha_evento:
            i += 1
            continue

        anterior_1 = lineas[i - 1] if i >= 1 else ""
        anterior_2 = lineas[i - 2] if i >= 2 else ""

        titulo = None

        pistas_subtitulo = [
            "dirección:",
            "música",
            "teatro",
            "danza",
            "circo",
            "festival",
            "programación",
            "canal",
            "estreno",
            "comisario",
        ]

        if anterior_2 and anterior_1:
            if len(anterior_1) < 80 and any(x in anterior_1.lower() for x in pistas_subtitulo):
                titulo = anterior_2
            else:
                titulo = anterior_1
        else:
            titulo = anterior_1

        titulo = limpiar_texto(titulo)

        if not titulo:
            i += 1
            continue

        if es_futura_o_hoy(fecha_evento):
            candidatos.append((titulo, fecha_evento))

        i += 1

    total = min(len(candidatos), len(urls_ordenadas))

    for idx in range(total):
        titulo, fecha_evento = candidatos[idx]
        url_evento = urls_ordenadas[idx]

        agregar_evento(
            eventos,
            vistos,
            titulo,
            fecha_evento,
            lugar,
            url_evento,
            url
        )

    def _parse_fecha(fila):
        try:
            return date(
                int(fila[1][6:10]),
                int(fila[1][3:5]),
                int(fila[1][0:2]),
            )
        except Exception:
            return date.max

    eventos.sort(key=lambda fila: (_parse_fecha(fila), fila[0].lower()))
    return eventos