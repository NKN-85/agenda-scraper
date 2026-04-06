import requests
from bs4 import BeautifulSoup
import re

from utils import (
    HEADERS,
    convertir_fecha_eslava,
    limpiar_texto,
    es_futura_o_hoy,
    agregar_evento,
)


def sacar_eslava():
    url = "https://teatroeslava.com/conciertos-madrid/"
    lugar = "Teatro Eslava"

    eventos = []
    vistos = set()

    respuesta = requests.get(url, headers=HEADERS, verify=False, timeout=15)
    respuesta.raise_for_status()
    soup = BeautifulSoup(respuesta.text, "html.parser")

    urls_por_titulo = {}

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        texto = limpiar_texto(a.get_text(" ", strip=True))

        if "/conciertos/" in href and texto and texto not in {"ENTRADAS", "Conciertos"}:
            urls_por_titulo[texto] = href

    texto_total = limpiar_texto(soup.get_text(" ", strip=True))

    patron = (
        r"(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+"
        r"(\d{2}\.\d{2}\.\d{4})\s+"
        r"(.*?)"
        r"(?=(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+\d{2}\.\d{2}\.\d{4}|$)"
    )
    coincidencias = re.findall(patron, texto_total, flags=re.IGNORECASE)

    for _, fecha, titulo, _ in coincidencias:
        titulo = limpiar_texto(titulo)

        for palabra in ["ENTRADAS", "ÚLTIMAS", "SOLD OUT", "Buscar"]:
            titulo = titulo.replace(palabra, "")

        for corte in [
            "Best Moments",
            "Si quieres programar tu concierto",
            "¡No te pierdas nada!",
            "Apúntate a nuestro newsletter",
            "Contacto",
            "Instagram",
            "Facebook",
            "Youtube",
            "Spotify",
            "MEMBER OF",
            "BUY YOUR TICKETS",
            "Calle Arenal",
        ]:
            if corte in titulo:
                titulo = titulo.split(corte)[0].strip()

        titulo = limpiar_texto(titulo).strip(" -–|")
        fecha_evento = convertir_fecha_eslava(fecha)

        if not es_futura_o_hoy(fecha_evento):
            continue

        url_evento = urls_por_titulo.get(titulo, url)

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