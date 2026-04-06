import requests
import re
from bs4 import BeautifulSoup

from utils import (
    HEADERS,
    limpiar_texto,
    es_futura_o_hoy,
    agregar_evento,
    construir_fecha,
    get_url
)


def convertir_fecha_but(fecha_texto):
    fecha_texto = limpiar_texto(fecha_texto).lower()

    # Ejemplos actuales:
    # 24 MAR 2026
    # 2 MAYO 2026
    m = re.fullmatch(r"(\d{1,2})\s+([a-záéíóú]+)\s+(\d{4})", fecha_texto)
    if not m:
        return None

    dia = int(m.group(1))
    mes_txt = m.group(2)
    anio = int(m.group(3))

    return construir_fecha(dia, mes_txt, anio)


def sacar_but():
    url = "https://www.salabut.es/agenda-conciertos/"
    lugar = "Sala But"

    eventos = []
    vistos = set()

    # 🔥 CAMBIO AQUÍ
    respuesta = get_url(url, timeout=20)

    soup = BeautifulSoup(respuesta.text, "html.parser")

    lineas = [
        limpiar_texto(x)
        for x in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(x)
    ]

    # URLs de compra en el orden en que aparecen en la página
    urls_compra = []
    for a in soup.find_all("a", href=True):
        texto = limpiar_texto(a.get_text(" ", strip=True)).upper()
        href = a.get("href", "").strip()

        if texto == "COMPRAR ENTRADAS" and href:
            urls_compra.append(href)

    candidatos = []

    for i, linea in enumerate(lineas):
        fecha_evento = convertir_fecha_but(linea)
        if not fecha_evento:
            continue

        if i == 0:
            continue

        titulo = limpiar_texto(lineas[i - 1])

        # filtros de basura por si acaso
        if not titulo or titulo.upper() in {
            "AGENDA",
            "VVV",
            "COMPRAR ENTRADAS",
            "INFORMACIÓN CONCIERTOS",
            "MAIL",
            "HORARIO",
            "TELÉFONO",
        }:
            continue

        if es_futura_o_hoy(fecha_evento):
            candidatos.append((titulo, fecha_evento))

    total = min(len(candidatos), len(urls_compra))

    for idx in range(total):
        titulo, fecha_evento = candidatos[idx]
        url_evento = urls_compra[idx]

        agregar_evento(
            eventos,
            vistos,
            titulo,
            fecha_evento,
            lugar,
            url_evento,
            url
        )

    return eventos