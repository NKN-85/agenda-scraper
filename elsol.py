import requests
from bs4 import BeautifulSoup
import re
from datetime import date

from utils import HEADERS, convertir_fecha_elsol, get_url


def sacar_elsol():
    url = "https://salaelsol.com/agenda/"
    eventos = []
    vistos = set()

    # 🔥 CAMBIO AQUÍ
    respuesta = get_url(url, timeout=15)

    soup = BeautifulSoup(respuesta.text, "html.parser")

    # mapa titulo -> url evento
    urls_por_titulo = {}

    ignorar_textos = {
        "Agenda", "Clubbing El Sol", "La Sala", "Contacto",
        "Info", "Tickets", "Hoy", "Conciertos", "Clubbing",
        "Más información"
    }

    for a in soup.find_all("a", href=True):
        texto = a.get_text(" ", strip=True)
        href = a["href"].strip()

        if not texto or texto in ignorar_textos:
            continue

        if "salaelsol.com" in href and "/eventos/" in href:
            urls_por_titulo[texto] = href

    # texto de la agenda
    lineas = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]

    patron_fecha = re.compile(
        r"^(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+\d{1,2}\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)$",
        re.IGNORECASE
    )

    patron_hora = re.compile(
        r"^\d{1,2}[:.]\d{2}\s*[–-]\s*\d{1,2}[:.]\d{2}h?$",
        re.IGNORECASE
    )

    basura = {
        "Conciertos", "Clubbing", "Info", "Tickets",
        "Hoy", "Agenda", "Todo", "Todo el día",
        "Más información"
    }

    meses_bloque_malo = {"julio", "agosto"}

    i = 0
    while i < len(lineas):
        linea = lineas[i]

        if patron_fecha.match(linea):
            fecha = linea
            fecha_evento = convertir_fecha_elsol(fecha)

            # descartar bloque raro de verano
            partes_fecha = fecha.lower().split()
            mes_fecha = partes_fecha[2] if len(partes_fecha) == 3 else ""
            if mes_fecha in meses_bloque_malo:
                i += 1
                continue

            titulo = None

            for j in range(i + 1, min(i + 10, len(lineas))):
                candidato = lineas[j]

                if candidato in basura:
                    continue
                if patron_fecha.match(candidato):
                    continue
                if patron_hora.match(candidato):
                    continue
                if len(candidato) < 3:
                    continue

                if len(candidato) > 60:
                    continue

                if "," in candidato and len(candidato.split()) > 6:
                    continue

                if "..." in candidato or "…" in candidato:
                    continue

                if candidato.lower() in {"todo el día", "info", "tickets", "más información"}:
                    continue

                if candidato.lower().startswith("eventos el "):
                    continue

                if " en concierto " in candidato.lower():
                    continue

                palabras_desc = {
                    "concierto", "visita", "presenta", "proyecto", "regresa",
                    "potente", "directo", "banda", "legendaria", "agrupación",
                    "músicos", "sonido", "rock", "disco", "películas",
                    "formato", "apoyar", "cultura", "fusionan", "espacio único",
                    "trabajo", "transformará", "estrellas", "invitación gratuita",
                    "temporada", "agradeceros", "directo", "danza", "folclor",
                    "platos", "aperitivos", "madrid", "actuarán", "nuevo disco"
                }

                candidato_norm = candidato.lower()
                if sum(1 for p in palabras_desc if p in candidato_norm) >= 2:
                    continue

                titulo = candidato
                break

            if titulo and fecha_evento and fecha_evento >= date.today():
                clave = (fecha, titulo, "Sala El Sol")

                if clave not in vistos:
                    vistos.add(clave)

                    fecha_formateada = fecha_evento.strftime("%d/%m/%Y")
                    url_evento = urls_por_titulo.get(titulo, url)

                    eventos.append([
                        titulo,
                        fecha_formateada,
                        "Sala El Sol",
                        url_evento,
                        url
                    ])

        i += 1

    return eventos