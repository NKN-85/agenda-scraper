import requests
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import (
    limpiar_texto,
    construir_fecha,
    get_url,
    agregar_evento
)


def primera_fecha_canal(texto):
    texto = limpiar_texto(texto).lower()

    # Del 26 de marzo al 19 de abril de 2026 -> devolver 26 marzo 2026
    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return construir_fecha(int(m.group(1)), m.group(2), int(m.group(5)))

    # Del 19 de marzo al 8 de mayo -> devolver 19 marzo año actual
    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)",
        texto
    )
    if m:
        return construir_fecha(int(m.group(1)), m.group(2), date.today().year)

    # 10, 11 y 12 de abril de 2026 -> devolver 10 abril 2026
    m = re.search(
        r"(\d{1,2})\s*,\s*(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return construir_fecha(int(m.group(1)), m.group(4), int(m.group(5)))

    # 11 y 12 de abril de 2026 -> devolver 11 abril 2026
    m = re.search(
        r"(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return construir_fecha(int(m.group(1)), m.group(3), int(m.group(4)))

    # 12 de abril de 2026
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))

    # 12 de abril 2026
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(\d{4})",
        texto
    )
    if m:
        return construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))

    return None


def lineas_limpias(soup):
    return [
        limpiar_texto(l)
        for l in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(l)
    ]


def parsear_metadatos_fechas_canal(texto):
    texto = limpiar_texto(texto).lower()

    # Del 26 de marzo al 19 de abril de 2026
    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        inicio = construir_fecha(int(m.group(1)), m.group(2), int(m.group(5)))
        fin = construir_fecha(int(m.group(3)), m.group(4), int(m.group(5)))
        if inicio and fin:
            return {
                "tipo": "rango",
                "fecha": inicio,
                "fecha_inicio": inicio,
                "fecha_fin": fin,
                "fechas_funcion": [],
                "texto_fecha_original": texto,
            }

    # Del 19 de marzo al 8 de mayo
    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)",
        texto
    )
    if m:
        anio = date.today().year
        inicio = construir_fecha(int(m.group(1)), m.group(2), anio)
        fin = construir_fecha(int(m.group(3)), m.group(4), anio)
        if inicio and fin:
            return {
                "tipo": "rango",
                "fecha": inicio,
                "fecha_inicio": inicio,
                "fecha_fin": fin,
                "fechas_funcion": [],
                "texto_fecha_original": texto,
            }

    # 10, 11 y 12 de abril de 2026
    m = re.search(
        r"(\d{1,2})\s*,\s*(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        fechas = [
            construir_fecha(int(m.group(1)), m.group(4), int(m.group(5))),
            construir_fecha(int(m.group(2)), m.group(4), int(m.group(5))),
            construir_fecha(int(m.group(3)), m.group(4), int(m.group(5))),
        ]
        fechas = [f for f in fechas if f]
        if fechas:
            return {
                "tipo": "lista",
                "fecha": fechas[0],
                "fecha_inicio": fechas[0],
                "fecha_fin": fechas[-1],
                "fechas_funcion": fechas,
                "texto_fecha_original": texto,
            }

    # 11 y 12 de abril de 2026
    m = re.search(
        r"(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        fechas = [
            construir_fecha(int(m.group(1)), m.group(3), int(m.group(4))),
            construir_fecha(int(m.group(2)), m.group(3), int(m.group(4))),
        ]
        fechas = [f for f in fechas if f]
        if fechas:
            return {
                "tipo": "lista",
                "fecha": fechas[0],
                "fecha_inicio": fechas[0],
                "fecha_fin": fechas[-1],
                "fechas_funcion": fechas,
                "texto_fecha_original": texto,
            }

    # 12 de abril de 2026
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        f = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        if f:
            return {
                "tipo": "unica",
                "fecha": f,
                "fecha_inicio": f,
                "fecha_fin": f,
                "fechas_funcion": [f],
                "texto_fecha_original": texto,
            }

    return None


def ficha_canal_sigue_vigente(soup):
    hoy = date.today()
    lineas = lineas_limpias(soup)

    for linea in lineas:
        datos = parsear_metadatos_fechas_canal(linea)
        if not datos:
            continue

        if datos["tipo"] == "rango":
            return datos["fecha_fin"] >= hoy

        if datos["tipo"] == "lista":
            return any(f >= hoy for f in datos["fechas_funcion"])

        if datos["tipo"] == "unica":
            return datos["fecha"] >= hoy

    return False


def extraer_titulo_y_metadatos_desde_ficha(soup):
    lineas = lineas_limpias(soup)

    descartes = {
        "información útil",
        "informacion útil",
        "informacion util",
        "fechas y precios",
        "información práctica",
        "informacion práctica",
        "informacion practica",
        "comprar",
        "comprar entradas >",
        "comprar entradas",
        "ficha artística",
        "ficha artistica",
        "ofertas",
        "programa",
    }

    for i, linea in enumerate(lineas):
        datos_fecha = parsear_metadatos_fechas_canal(linea)
        if not datos_fecha:
            continue

        j = i - 1
        while j >= 0:
            candidata = limpiar_texto(lineas[j])
            candidata_l = candidata.lower()

            if not candidata:
                j -= 1
                continue

            if candidata_l in descartes:
                j -= 1
                continue

            if len(candidata) > 160:
                j -= 1
                continue

            return candidata, datos_fecha

        break

    return None, None


def sacar_canal():
    url = "https://www.teatroscanal.com/cartelera-madrid/"
    lugar = "Teatros del Canal"

    eventos = []
    vistos = set()

    try:
        r = get_url(url, timeout=40)
    except requests.exceptions.RequestException as e:
        print(f"[canal] fuente omitida: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    urls_evento = []
    urls_vistas = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(url, a.get("href", "").strip())

        if "/espectaculo/" not in href:
            continue

        if href in urls_vistas:
            continue

        urls_vistas.add(href)
        urls_evento.append(href)

    for href in urls_evento:
        try:
            r_det = get_url(href, timeout=40)
        except requests.exceptions.RequestException:
            continue

        soup_det = BeautifulSoup(r_det.text, "html.parser")
        titulo, datos_fecha = extraer_titulo_y_metadatos_desde_ficha(soup_det)

        if not titulo or not datos_fecha:
            continue

        if not ficha_canal_sigue_vigente(soup_det):
            continue

        agregar_evento(
            eventos,
            vistos,
            titulo,
            datos_fecha.get("fecha"),
            lugar,
            href,
            url,
            info_fecha=datos_fecha
        )

    eventos.sort(
        key=lambda e: (
            e.get("fecha") or "9999-12-31",
            e.get("titulo", "").lower()
        )
    )
    return eventos