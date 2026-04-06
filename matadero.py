import requests
import re
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils import HEADERS


def limpiar_texto(texto):
    return " ".join(texto.split()).strip()


def parsear_rango_matadero(texto):
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
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    texto = limpiar_texto(texto).lower()
    hoy = date.today()
    anio_actual = hoy.year

    def mk(d, mes_txt, anio):
        mes = meses.get(mes_txt)
        if not mes:
            return None
        try:
            return date(anio, mes, d)
        except ValueError:
            return None

    def mk_mes(mes_txt, anio, primer_dia=True):
        mes = meses.get(mes_txt)
        if not mes:
            return None
        try:
            return date(anio, mes, 1 if primer_dia else 28)
        except ValueError:
            return None

    # miércoles, 25 de marzo 2026
    m = re.search(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo),?\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(\d{4})",
        texto
    )
    if m:
        d = mk(int(m.group(1)), m.group(2), int(m.group(3)))
        return d, d

    # 25 de marzo 2026
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(\d{4})", texto)
    if m:
        d = mk(int(m.group(1)), m.group(2), int(m.group(3)))
        return d, d

    # 25 marzo 2026
    m = re.search(r"(\d{1,2})\s+([a-záéíóú]+)\s+(\d{4})", texto)
    if m:
        d = mk(int(m.group(1)), m.group(2), int(m.group(3)))
        return d, d

    # 24 marzo / 26 MARZO / 1 Abril
    m = re.search(r"^(\d{1,2})\s+([a-záéíóú]+)$", texto)
    if m:
        d = mk(int(m.group(1)), m.group(2), anio_actual)
        return d, d

    # 8 y 9 abril / 28 y 29 marzo / 25, 26 y 28 marzo
    m = re.search(
        r"(\d{1,2})(?:\s*,\s*\d{1,2})*(?:\s+y\s+\d{1,2})\s+([a-záéíóú]+)(?:\s+(\d{4}))?$",
        texto
    )
    if m:
        anio = int(m.group(3)) if m.group(3) else anio_actual
        inicio = mk(int(m.group(1)), m.group(2), anio)
        # como fecha_fin aproximada, usamos el mismo mes y el último número del texto
        nums = [int(x) for x in re.findall(r"\d{1,2}", texto)]
        fin = mk(max(nums), m.group(2), anio) if nums else inicio
        return inicio, fin

    # 26 a 29 marzo / 18 a 22 marzo / 1 a 29 marzo
    m = re.search(r"(\d{1,2})\s+a\s+(\d{1,2})\s+([a-záéíóú]+)(?:\s+(\d{4}))?$", texto)
    if m:
        anio = int(m.group(4)) if m.group(4) else anio_actual
        return (
            mk(int(m.group(1)), m.group(3), anio),
            mk(int(m.group(2)), m.group(3), anio),
        )

    # 31 marzo a 5 abril / 31 marzo a 5 abril 2026
    m = re.search(
        r"(\d{1,2})\s+([a-záéíóú]+)\s+a\s+(\d{1,2})\s+([a-záéíóú]+)(?:\s+(\d{4}))?$",
        texto
    )
    if m:
        anio = int(m.group(5)) if m.group(5) else anio_actual
        return (
            mk(int(m.group(1)), m.group(2), anio),
            mk(int(m.group(3)), m.group(4), anio),
        )

    # Hasta 24 mayo / Hasta 24 mayo 2026
    m = re.search(r"hasta\s+(\d{1,2})\s+([a-záéíóú]+)(?:\s+(\d{4}))?$", texto)
    if m:
        anio = int(m.group(3)) if m.group(3) else anio_actual
        fin = mk(int(m.group(1)), m.group(2), anio)
        return fin, fin

    # Hasta junio 2026 / Hasta junio
    m = re.search(r"hasta\s+([a-záéíóú]+)(?:\s+(\d{4}))?$", texto)
    if m:
        anio = int(m.group(2)) if m.group(2) else anio_actual
        fin = mk_mes(m.group(1), anio, primer_dia=True)
        return fin, fin

    # 11 marzo a 9 abril / 20 marzo a 12 abril
    m = re.search(
        r"(\d{1,2})\s+([a-záéíóú]+)\s+a\s+(\d{1,2})\s+([a-záéíóú]+)$",
        texto
    )
    if m:
        return (
            mk(int(m.group(1)), m.group(2), anio_actual),
            mk(int(m.group(3)), m.group(4), anio_actual),
        )

    # Septiembre de 2025 a junio de 2026
    m = re.search(
        r"([a-záéíóú]+)\s+de\s+(\d{4})\s+a\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        return (
            mk_mes(m.group(1), int(m.group(2)), primer_dia=True),
            mk_mes(m.group(3), int(m.group(4)), primer_dia=True),
        )

    # Enero a marzo 2026
    m = re.search(r"([a-záéíóú]+)\s+a\s+([a-záéíóú]+)\s+(\d{4})", texto)
    if m:
        return (
            mk_mes(m.group(1), int(m.group(3)), primer_dia=True),
            mk_mes(m.group(2), int(m.group(3)), primer_dia=True),
        )

    # Curso escolar 25/26
    m = re.search(r"curso\s+escolar\s+(\d{2})/(\d{2})", texto)
    if m:
        inicio = date(2000 + int(m.group(1)), 9, 1)
        fin = date(2000 + int(m.group(2)), 6, 30)
        return inicio, fin

    return None, None


def obtener_paginas(session, base_url):
    paginas = []
    visitadas = set()
    actual = base_url

    while actual and actual not in visitadas:
        visitadas.add(actual)
        paginas.append(actual)

        r = session.get(actual, headers=HEADERS, verify=False, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        siguiente = None
        for a in soup.find_all("a", href=True):
            texto = limpiar_texto(a.get_text(" ", strip=True)).lower()
            if "next page" in texto:
                siguiente = urljoin(base_url, a["href"].strip())
                break

        actual = siguiente

    return paginas


def sacar_eventos_de_pagina(soup, base_url, vistos):
    eventos = []
    lugar = "Matadero Madrid"
    hoy = date.today()

    lineas = [
        limpiar_texto(x)
        for x in soup.get_text("\n").splitlines()
        if limpiar_texto(x)
    ]

    enlaces = {}
    for a in soup.find_all("a", href=True):
        texto = limpiar_texto(a.get_text(" ", strip=True))
        href = a.get("href", "").strip()

        if not texto or not href:
            continue

        href_abs = href if href.startswith("http") else urljoin(base_url, href)

        if "/programacion/" not in href_abs:
            continue
        if href_abs.rstrip("/") == base_url.rstrip("/"):
            continue

        enlaces.setdefault(texto, href_abs)

    for i in range(len(lineas) - 1):
        fecha_inicio, fecha_fin = parsear_rango_matadero(lineas[i])
        if not fecha_inicio or not fecha_fin:
            continue

        titulo = lineas[i + 1]
        url_evento = enlaces.get(titulo)
        if not url_evento:
            continue

        # clave: incluir también fecha_fin para no mezclar ciclos con mismo título
        clave = (titulo.lower(), fecha_inicio, fecha_fin, url_evento)
        if clave in vistos:
            continue

        # filtro correcto para Matadero: sigue vigente si la fecha fin no ha pasado
        if fecha_fin < hoy:
            continue

        vistos.add(clave)

        eventos.append([
            titulo,
            fecha_inicio.strftime("%d/%m/%Y"),
            lugar,
            url_evento,
            base_url
        ])

    return eventos


def sacar_matadero():
    base_url = "https://www.mataderomadrid.org/programacion"

    session = requests.Session()
    vistos = set()
    eventos = []

    paginas = obtener_paginas(session, base_url)

    for pagina in paginas:
        try:
            r = session.get(pagina, headers=HEADERS, verify=False, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            eventos.extend(sacar_eventos_de_pagina(soup, base_url, vistos))
        except Exception as e:
            print(f"[AVISO] Error en página Matadero {pagina}: {e}")

    return eventos