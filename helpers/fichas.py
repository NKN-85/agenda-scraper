import requests
from bs4 import BeautifulSoup

from utils import HEADERS
from helpers.avisos import avisar


def abrir_ficha(session, url):
    try:
        respuesta = session.get(url, headers=HEADERS, verify=False, timeout=5)
        respuesta.raise_for_status()
        return BeautifulSoup(respuesta.text, "html.parser")

    except Exception:
        avisar(f"No se pudo abrir la ficha: {url}")
        return None


def extraer_titulo(soup):
    for tag in ["h1", "h2"]:
        el = soup.find(tag)
        if el:
            texto = el.get_text(" ", strip=True)
            if texto and 3 <= len(texto) <= 150:
                return texto

    if soup.title:
        texto = soup.title.get_text(" ", strip=True)
        if texto:
            return texto.split("|")[0].strip()

    return None


def extraer_lineas(soup):
    return [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]