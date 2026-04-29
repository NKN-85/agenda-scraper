import requests
from bs4 import BeautifulSoup
import re
from datetime import date

from utils import HEADERS, convertir_fecha_elsol, get_url


def sacar_elsol():
    url = "https://salaelsol.com/agenda/"
    eventos = []
    vistos = set()

    respuesta = get_url(url, timeout=15)
    if not respuesta:
        return []

    soup = BeautifulSoup(respuesta.text, "html.parser")

    # ✅ CAMBIO CLAVE 1: Solo buscamos en los contenedores reales de la agenda
    # Esto ignora automáticamente a Perinetti y compañía que están en 'em-item-info'
    bloques_agenda = soup.find_all("div", class_="gran-contenedor-agenda")
    
    if not bloques_agenda:
        return []

    # Extraemos las URLs solo de los bloques de la agenda para evitar colisiones
    urls_por_titulo = {}
    for bloque in bloques_agenda:
        for a in bloque.find_all("a", href=True):
            texto = a.get_text(" ", strip=True)
            href = a["href"].strip()
            if "/eventos/" in href and len(texto) > 3:
                urls_por_titulo[texto] = href

    patron_fecha = re.compile(
        r"^(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d{1,2})\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
        re.IGNORECASE
    )

    # ✅ CAMBIO CLAVE 2: Iteramos bloque por bloque de la agenda
    for bloque in bloques_agenda:
        texto_bloque = bloque.get_text("\n", strip=True)
        lineas = [l.strip() for l in texto_bloque.splitlines() if l.strip()]

        i = 0
        while i < len(lineas):
            linea = lineas[i]
            match = patron_fecha.search(linea)
            
            if match:
                fecha_str = match.group(0)
                fecha_evento = convertir_fecha_elsol(fecha_str)
                
                if not fecha_evento or fecha_evento < date.today():
                    i += 1
                    continue

                titulo = None
                url_evento = url

                # Buscamos el nombre del evento (en la web de El Sol suele ser 'nombre_evento')
                # Pero siguiendo tu lógica de líneas para asegurar compatibilidad:
                for j in range(i + 1, min(i + 6, len(lineas))):
                    candidato = lineas[j]
                    
                    # Filtro de basura rápido
                    if "Tickets" in candidato or "Info" in candidato or "23.59" in candidato:
                        continue

                    # Si el candidato está en nuestro mapa de URLs del bloque, es el título
                    if candidato in urls_por_titulo:
                        titulo = candidato
                        url_evento = urls_por_titulo[candidato]
                        break
                    
                    # Búsqueda flexible por mayúsculas
                    found_flex = False
                    for t_url, h_url in urls_por_titulo.items():
                        if candidato.lower() == t_url.lower():
                            titulo = candidato
                            url_evento = h_url
                            found_flex = True
                            break
                    if found_flex: break

                if titulo:
                    clave = (fecha_str, titulo, "Sala El Sol")
                    if clave not in vistos:
                        vistos.add(clave)
                        eventos.append([
                            titulo,
                            fecha_evento.strftime("%d/%m/%Y"),
                            "Sala El Sol",
                            url_evento,
                            url
                        ])
            i += 1

    return eventos