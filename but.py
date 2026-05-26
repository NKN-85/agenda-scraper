import re
from bs4 import BeautifulSoup

from utils import (
    limpiar_texto,
    es_futura_o_hoy,
    agregar_evento,
    construir_fecha,
    get_url
)


def convertir_fecha_but(fecha_texto):
    fecha_texto = limpiar_texto(fecha_texto).lower()

    # Ejemplos:
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

    respuesta = get_url(url, timeout=20)
    soup = BeautifulSoup(respuesta.text, "html.parser")

    for a in soup.find_all("a", href=True):
        texto_boton = limpiar_texto(a.get_text(" ", strip=True)).upper()

        if texto_boton != "COMPRAR ENTRADAS":
            continue

        url_evento = a.get("href", "").strip()

        if not url_evento:
            continue

        # Subimos por los padres del botón hasta encontrar
        # un bloque que contenga título + fecha + botón.
        bloque = a

        for _ in range(8):
            if not bloque.parent:
                break

            bloque = bloque.parent

            textos = [
                limpiar_texto(x)
                for x in bloque.get_text("\n", strip=True).splitlines()
                if limpiar_texto(x)
            ]

            fecha_evento = None
            fecha_idx = None

            for i, linea in enumerate(textos):
                fecha = convertir_fecha_but(linea)

                if fecha:
                    fecha_evento = fecha
                    fecha_idx = i
                    break

            if not fecha_evento or fecha_idx is None:
                continue

            if fecha_idx == 0:
                continue

            titulo = limpiar_texto(textos[fecha_idx - 1])

            if not titulo:
                continue

            # Filtros por si el bloque contiene textos basura
            if titulo.upper() in {
                "AGENDA",
                "VVV",
                "COMPRAR ENTRADAS",
                "INFORMACIÓN CONCIERTOS",
                "MAIL",
                "HORARIO",
                "TELÉFONO",
            }:
                continue

            if not es_futura_o_hoy(fecha_evento):
                continue

            agregar_evento(
                eventos,
                vistos,
                titulo,
                fecha_evento,
                lugar,
                url_evento,
                url
            )

            # Ya hemos procesado este botón/evento
            break

    return eventos