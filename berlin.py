from collections import defaultdict
import re
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils import agregar_evento, get_url
from helpers.texto import normalizar_texto


def convertir_fecha_berlin(dia_texto, mes_texto, anio):
    meses = {
        "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
        "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    }

    dia_texto = dia_texto.strip()
    mes_texto = normalizar_texto(mes_texto).lower()[:3]

    if not dia_texto.isdigit():
        return None

    mes = meses.get(mes_texto)
    if not mes:
        return None

    try:
        return date(anio, mes, int(dia_texto))
    except ValueError:
        return None


def sacar_berlin():
    url = "https://berlincafe.es/programas/"
    lugar = "Café Berlín"

    eventos = []
    vistos = set()

    respuesta = get_url(url, timeout=20)
    soup = BeautifulSoup(respuesta.text, "html.parser")
    lineas = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]

    titulos_validos = {}
    for a in soup.find_all("a", href=True):
        texto = a.get_text(" ", strip=True)
        href = a["href"].strip()

        if not texto or not href:
            continue

        href = urljoin(url, href)

        if "/programa/" not in href:
            continue

        texto_norm = normalizar_texto(texto)
        if texto_norm in {"read more", "<< todo el programa", "leer mas", "leer más"}:
            continue

        if 3 <= len(texto) <= 180:
            titulos_validos[texto_norm] = (texto, href)

    hoy = date.today()
    anio_actual = hoy.year
    mes_anterior = hoy.month

    candidatos = []

    for i, linea in enumerate(lineas):
        linea_norm = normalizar_texto(linea)

        if linea_norm not in titulos_validos:
            continue

        titulo, url_evento = titulos_validos[linea_norm]

        dia = None
        mes_txt = None

        inicio = max(0, i - 6)
        ventana = lineas[inicio:i]

        for j in range(len(ventana) - 1):
            posible_dia = ventana[j].strip()
            posible_mes = ventana[j + 1].strip()

            if re.fullmatch(r"\d{1,2}", posible_dia) and re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóú]{3,}", posible_mes):
                dia = posible_dia
                mes_txt = posible_mes
                break

        if not dia or not mes_txt:
            continue

        mes_abrev = normalizar_texto(mes_txt).lower()[:3]
        meses_num = {
            "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
            "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
        }
        mes_num = meses_num.get(mes_abrev)
        if not mes_num:
            continue

        if mes_num < mes_anterior - 6:
            anio_actual += 1
        mes_anterior = mes_num

        fecha_evento = convertir_fecha_berlin(dia, mes_txt, anio_actual)
        if not fecha_evento or fecha_evento < hoy:
            continue

        candidatos.append((titulo, fecha_evento, url_evento))

    # Agrupar todas las fechas por evento
    agrupados = defaultdict(set)

    for titulo, fecha_evento, url_evento in candidatos:
        clave = (titulo.strip(), url_evento.strip())
        agrupados[clave].add(fecha_evento)

    for (titulo, url_evento), fechas in agrupados.items():
        fechas_ordenadas = sorted(fechas)

        if not fechas_ordenadas:
            continue

        info_fecha = {
            "tipo_fecha": "lista" if len(fechas_ordenadas) > 1 else "unica",
            "fechas_funcion": [f.isoformat() for f in fechas_ordenadas],
            "fecha": fechas_ordenadas[0].isoformat(),
            "fecha_inicio": fechas_ordenadas[0].isoformat(),
            "fecha_fin": fechas_ordenadas[-1].isoformat(),
            "texto_fecha_original": "programa berlin"
        }

        agregar_evento(
            eventos=eventos,
            vistos=vistos,
            titulo=titulo,
            fecha_evento=fechas_ordenadas[0],
            lugar=lugar,
            url_evento=url_evento,
            fuente=url,
            info_fecha=info_fecha,
        )

    return eventos