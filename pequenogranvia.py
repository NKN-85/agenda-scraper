import requests
import re
from datetime import date
from urllib.parse import urljoin

from utils import agregar_evento, get_url
from helpers.texto import normalizar_texto
from helpers.avisos import avisar
from helpers.fichas import abrir_ficha, extraer_titulo, extraer_lineas


def convertir_fecha_pequenogranvia(texto):
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    }

    texto = texto.strip().lower()

    # Del 15 de abril de 2026 al 27 de mayo de 2026
    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "rango",
            "fecha_inicio": date(int(m.group(3)), meses[m.group(2)], int(m.group(1))),
            "fecha_fin": date(int(m.group(6)), meses[m.group(5)], int(m.group(4))),
        }

    # Del 15 de abril al 27 de mayo de 2026
    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "rango",
            "fecha_inicio": date(int(m.group(5)), meses[m.group(2)], int(m.group(1))),
            "fecha_fin": date(int(m.group(5)), meses[m.group(4)], int(m.group(3))),
        }

    # Del 15 al 27 de mayo de 2026
    m = re.search(
        r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "rango",
            "fecha_inicio": date(int(m.group(4)), meses[m.group(3)], int(m.group(1))),
            "fecha_fin": date(int(m.group(4)), meses[m.group(3)], int(m.group(2))),
        }

    # Hasta el 27 de mayo de 2026
    m = re.search(
        r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "hasta",
            "fecha_fin": date(int(m.group(3)), meses[m.group(2)], int(m.group(1))),
        }

    # Desde el 15 de abril de 2026
    m = re.search(
        r"desde\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "desde",
            "fecha_inicio": date(int(m.group(3)), meses[m.group(2)], int(m.group(1))),
        }

    # 10, 11 y 12 de mayo de 2026
    m = re.search(
        r"(\d{1,2})\s*,\s*(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "lista",
            "fechas": [
                date(int(m.group(5)), meses[m.group(4)], int(m.group(1))),
                date(int(m.group(5)), meses[m.group(4)], int(m.group(2))),
                date(int(m.group(5)), meses[m.group(4)], int(m.group(3))),
            ],
        }

    # 10 y 11 de mayo de 2026
    m = re.search(
        r"(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "lista",
            "fechas": [
                date(int(m.group(4)), meses[m.group(3)], int(m.group(1))),
                date(int(m.group(4)), meses[m.group(3)], int(m.group(2))),
            ],
        }

    # 10 de mayo, 23 de mayo y 30 de mayo de 2026
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s*,\s*(\d{1,2})\s+de\s+([a-záéíóú]+)\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "lista",
            "fechas": [
                date(int(m.group(7)), meses[m.group(2)], int(m.group(1))),
                date(int(m.group(7)), meses[m.group(4)], int(m.group(3))),
                date(int(m.group(7)), meses[m.group(6)], int(m.group(5))),
            ],
        }

    # Fecha única con día de la semana
    m = re.search(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "unica",
            "fecha": date(int(m.group(3)), meses[m.group(2)], int(m.group(1))),
        }

    # Fecha única simple
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return {
            "tipo": "unica",
            "fecha": date(int(m.group(3)), meses[m.group(2)], int(m.group(1))),
        }

    # Respaldo: 10 de mayo, ... de 2026
    m1 = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s*,", texto)
    m2 = re.search(r"de\s+(\d{4})", texto)
    if m1 and m2:
        return {
            "tipo": "unica",
            "fecha": date(int(m2.group(1)), meses[m1.group(2)], int(m1.group(1))),
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

    # intento 1
    for linea in extraer_lineas(soup)[:150]:
        info = convertir_fecha_pequenogranvia(linea)
        if info:
            return titulo, info

    # intento 2 (fallback fuerte)
    lineas_crudas = [
        l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()
    ]
    for linea in lineas_crudas[:250]:
        info = convertir_fecha_pequenogranvia(linea)
        if info:
            return titulo, info

    avisar(f"Sin fecha en ficha: {url_evento}")
    return None, None


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

        info = None
        titulo_final = titulo

        for j in range(i + 1, min(i + 15, len(lineas))):
            info = convertir_fecha_pequenogranvia(lineas[j])
            if info:
                break

        if not info:
            titulo_real, info = sacar_fecha_desde_pagina_evento(session, url_evento)
            if titulo_real:
                titulo_final = titulo_real

        if not info:
            continue

        if not evento_sigue_vigente(info):
            continue

        fecha_evento = obtener_fecha_representativa(info)
        if not fecha_evento:
            continue

        agregar_evento(
            eventos,
            vistos,
            titulo_final,
            fecha_evento,
            "Pequeño Teatro Gran Vía",
            url_evento,
            url
        )

    return eventos