import csv
import json
import os
import re
import urllib3
from datetime import datetime, date
from bs4 import BeautifulSoup

from eslava import sacar_eslava
from but import sacar_but
from elsol import sacar_elsol
from vistalegre import sacar_vistalegre
from granvia import sacar_granvia
from alcazar import sacar_alcazar
from maravillas import sacar_maravillas
from figaro import sacar_figaro
from pequenogranvia import sacar_pequenogranvia
from capitol import sacar_capitol
from aranjuez import sacar_aranjuez
from matadero import sacar_matadero
from canal import sacar_canal
from riviera import sacar_riviera
from berlin import sacar_berlin
from movistararena import sacar_movistararena
from auditorio import sacar_auditorio
from fernangomez import sacar_fernangomez
from teatroespanol import sacar_teatroespanol
from ifema import sacar_ifema
from condeduque import sacar_condeduque
from salavillanos import sacar_salavillanos
from galileo import sacar_galileo
from clamores import sacar_clamores
from nazca import sacar_nazca
from replika import sacar_replika
from labtheclub import sacar_labtheclub
from maria_guerrero import sacar_maria_guerrero
from grupomarquina import sacar_grupomarquina
from valle_inclan import sacar_valle_inclan
from abadia import sacar_abadia
from circulo_bellas_artes import sacar_circulo_bellas_artes
from lara import sacar_lara
from bellasartes import sacar_bellasartes
from price import sacar_price
from teatrolalatina import sacar_teatrolalatina
from teatroreal import sacar_teatroreal
from zarzuela import sacar_zarzuela
from lazarogaldiano import sacar_lazarogaldiano

from utils import get_url, limpiar_texto, construir_fecha, normalizar_info_fecha

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def evento_es_dict(evento):
    return isinstance(evento, dict)


def fila_antigua_a_evento_dict(fila):
    if not isinstance(fila, (list, tuple)) or len(fila) < 5:
        return None

    titulo, fecha, lugar, url_evento, fuente = fila[:5]

    info_fecha = normalizar_info_fecha(fecha_evento=fecha)
    if not info_fecha:
        return None

    return {
        "titulo": limpiar_texto(titulo),
        "fecha": info_fecha.get("fecha"),
        "lugar": limpiar_texto(lugar),
        "url_evento": limpiar_texto(url_evento),
        "fuente": limpiar_texto(fuente),
        "tipo_fecha": info_fecha.get("tipo_fecha"),
        "rango_fechas": info_fecha.get("rango_fechas", False),
        "fecha_inicio": info_fecha.get("fecha_inicio"),
        "fecha_fin": info_fecha.get("fecha_fin"),
        "fechas_funcion": info_fecha.get("fechas_funcion", []),
        "dias_semana": info_fecha.get("dias_semana", []),
        "texto_fecha_original": info_fecha.get("texto_fecha_original", ""),
    }


def normalizar_evento_entrada(evento):
    if evento_es_dict(evento):
        info_fecha = normalizar_info_fecha(
            info_fecha={
                "tipo_fecha": evento.get("tipo_fecha"),
                "tipo": evento.get("tipo_fecha"),
                "fecha": evento.get("fecha"),
                "rango_fechas": evento.get("rango_fechas"),
                "fecha_inicio": evento.get("fecha_inicio"),
                "fecha_fin": evento.get("fecha_fin"),
                "fechas_funcion": evento.get("fechas_funcion", []),
                "dias_semana": evento.get("dias_semana", []),
                "texto_fecha_original": evento.get("texto_fecha_original", ""),
            },
            fecha_evento=evento.get("fecha")
        )

        if not info_fecha:
            return None

        return {
            "titulo": limpiar_texto(evento.get("titulo", "")),
            "fecha": info_fecha.get("fecha"),
            "lugar": limpiar_texto(evento.get("lugar", "")),
            "url_evento": limpiar_texto(evento.get("url_evento", "")),
            "fuente": limpiar_texto(evento.get("fuente", "")),
            "tipo_fecha": info_fecha.get("tipo_fecha"),
            "rango_fechas": info_fecha.get("rango_fechas", False),
            "fecha_inicio": info_fecha.get("fecha_inicio"),
            "fecha_fin": info_fecha.get("fecha_fin"),
            "fechas_funcion": info_fecha.get("fechas_funcion", []),
            "dias_semana": info_fecha.get("dias_semana", []),
            "texto_fecha_original": info_fecha.get("texto_fecha_original", ""),
        }

    return fila_antigua_a_evento_dict(evento)


def limpiar_eventos(eventos):
    resultado = []

    for evento in eventos:
        normalizado = normalizar_evento_entrada(evento)
        if not normalizado:
            continue

        if not normalizado.get("titulo"):
            continue
        if not normalizado.get("lugar"):
            continue
        if not normalizado.get("url_evento"):
            continue
        if not normalizado.get("fecha") and not normalizado.get("fecha_fin"):
            continue

        resultado.append(normalizado)

    return resultado


def guardar_csv(eventos, nombre_archivo="eventos.csv"):
    with open(nombre_archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "TITULO EVENTO",
            "FECHA",
            "LUGAR",
            "URL EVENTO",
            "FUENTE",
            "TIPO_FECHA",
            "RANGO_FECHAS",
            "FECHA_INICIO",
            "FECHA_FIN",
            "FECHAS_FUNCION",
            "DIAS_SEMANA",
            "TEXTO_FECHA_ORIGINAL",
        ])

        for evento in eventos:
            writer.writerow([
                evento.get("titulo", ""),
                evento.get("fecha", ""),
                evento.get("lugar", ""),
                evento.get("url_evento", ""),
                evento.get("fuente", ""),
                evento.get("tipo_fecha", ""),
                evento.get("rango_fechas", False),
                evento.get("fecha_inicio", ""),
                evento.get("fecha_fin", ""),
                ",".join(evento.get("fechas_funcion", [])),
                ",".join(str(x) for x in evento.get("dias_semana", [])),
                evento.get("texto_fecha_original", ""),
            ])


def eventos_a_json(eventos):
    eventos_json = []

    for evento in eventos:
        normalizado = normalizar_evento_entrada(evento)
        if not normalizado:
            continue

        eventos_json.append({
            "titulo": normalizado.get("titulo"),
            "fecha": normalizado.get("fecha"),
            "lugar": normalizado.get("lugar"),
            "url_evento": normalizado.get("url_evento"),
            "fuente": normalizado.get("fuente"),
            "tipo_fecha": normalizado.get("tipo_fecha"),
            "rango_fechas": normalizado.get("rango_fechas", False),
            "fecha_inicio": normalizado.get("fecha_inicio"),
            "fecha_fin": normalizado.get("fecha_fin"),
            "fechas_funcion": normalizado.get("fechas_funcion", []),
            "dias_semana": normalizado.get("dias_semana", []),
            "texto_fecha_original": normalizado.get("texto_fecha_original", ""),
        })

    return eventos_json


def guardar_json(eventos, nombre_archivo="eventos.json"):
    eventos_json = eventos_a_json(eventos)

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        json.dump(eventos_json, f, ensure_ascii=False, indent=2)


def cargar_master(nombre="eventos_master.json"):
    if not os.path.exists(nombre):
        return []

    with open(nombre, encoding="utf-8") as f:
        return json.load(f)


def guardar_master(eventos, nombre="eventos_master.json"):
    with open(nombre, "w", encoding="utf-8") as f:
        json.dump(eventos, f, ensure_ascii=False, indent=2)


def clave_evento_json(evento):
    url = (evento.get("url_evento", "") or "").strip().lower()
    lugar = (evento.get("lugar", "") or "").strip().lower()
    titulo = (evento.get("titulo", "") or "").strip().lower()

    # Para fichas únicas tipo Teatro Real:
    # evita duplicados si cambia el lugar entre "Teatro Real" y "Teatro Real - Sala Principal".
    if url and "/espectaculo/" in url:
        return (url,)

    # Resto de salas: no fusiona eventos distintos que comparten URL genérica.
    return (url, lugar, titulo)


def indexar_por_clave(eventos):
    indice = {}

    for evento in eventos:
        clave = clave_evento_json(evento)
        if clave[0]:
            indice[clave] = evento

    return indice


def clave_orden_fecha(evento):
    if not isinstance(evento, dict):
        evento = fila_antigua_a_evento_dict(evento)
        if not evento:
            return (datetime.max, "", "")

    fecha = evento.get("fecha") or evento.get("fecha_fin") or ""

    try:
        return (
            datetime.strptime(fecha, "%Y-%m-%d"),
            evento.get("lugar", "").lower(),
            evento.get("titulo", "").lower(),
        )
    except Exception:
        return (
            datetime.max,
            evento.get("lugar", "").lower(),
            evento.get("titulo", "").lower(),
        )


def clasificar_tipo_evento(evento):
    titulo = evento.get("titulo", "").lower()
    lugar = evento.get("lugar", "").lower()
    fuente = evento.get("fuente", "").lower()

    texto = f"{titulo} {lugar} {fuente}"

    if any(p in texto for p in ["exposición", "exposicion", "muestra", "instalación", "instalacion"]):
        return "exposicion"

    if any(p in texto for p in ["taller", "workshop", "editatona"]):
        return "taller"

    if any(p in texto for p in ["danza", "dance", "ballet", "flamenco", "milonga"]):
        return "danza"

    if any(p in texto for p in ["teatro", "dramaturgia", "obra", "berenice", "medea"]):
        return "teatro"

    if any(p in texto for p in ["musical", "zarzuela", "opera", "ópera"]):
        return "musical"

    if any(p in texto for p in ["cine", "film", "película", "pelicula", "cortometrajes", "sesión de cortometrajes", "sesion de cortometrajes"]):
        return "cine"

    if any(p in texto for p in ["comedia", "humor", "monólogo", "monologo", "podcast"]):
        return "comedia"

    if any(p in texto for p in ["circo"]):
        return "circo"

    if any(p in texto for p in ["vs.", "jornada", "euroliga", "liga endesa", "baloncesto"]):
        return "deporte"

    if any(p in texto for p in ["concierto", "tour", "band", "trío", "trio", "orquesta", "sinfónico", "sinfonico", "quartet", "cuarteto", "gira"]):
        return "concierto"

    if any(p in lugar for p in [
        "teatro",
        "teatros del canal",
        "figaro",
        "alcázar",
        "alcazar",
        "gran vía",
        "gran via",
        "maravillas",
        "fernán gómez",
        "fernan gomez",
        "guirau",
        "jardiel poncela",
    ]):
        return "teatro"

    if any(p in lugar for p in [
        "arena",
        "café berlín",
        "cafe berlin",
        "auditorio",
        "teatro eslava",
        "sala but",
        "sala el sol",
        "la riviera",
        "palacio vistalegre",
        "movistar arena",
    ]):
        return "concierto"

    return "otros"


def generar_tags(evento, tipo_evento):
    titulo = evento.get("titulo", "").lower()
    lugar = evento.get("lugar", "").lower()

    tags = set()
    tags.add(tipo_evento)

    if "matadero" in lugar:
        tags.add("matadero")

    if "riviera" in lugar:
        tags.add("riviera")

    if "movistar arena" in lugar:
        tags.add("movistar-arena")

    if "berlín" in lugar or "berlin" in lugar:
        tags.add("cafe-berlin")

    if "canal" in lugar:
        tags.add("teatros-del-canal")

    if "alcázar" in lugar or "alcazar" in lugar:
        tags.add("teatro-alcazar")

    if "gran vía" in lugar or "gran via" in lugar:
        tags.add("teatro-gran-via")

    if "maravillas" in lugar:
        tags.add("teatro-maravillas")

    if "fígaro" in lugar or "figaro" in lugar:
        tags.add("teatro-figaro")

    if "capitol" in lugar:
        tags.add("capitol-gran-via")

    if "pequeño teatro gran vía" in lugar or "pequeno teatro gran via" in lugar:
        tags.add("pequeno-teatro-gran-via")

    if "fernán gómez" in lugar or "fernan gomez" in lugar:
        tags.add("teatro-fernan-gomez")

    if "guirau" in lugar:
        tags.add("sala-guirau")

    if "jardiel poncela" in lugar:
        tags.add("sala-jardiel-poncela")

    if any(p in titulo for p in ["flamenco"]):
        tags.add("flamenco")

    if any(p in titulo for p in ["infantil", "familia", "niños", "niñas", "cuento", "cantacuentos"]):
        tags.add("infantil")

    if any(p in titulo for p in ["festival"]):
        tags.add("festival")

    if any(p in titulo for p in ["jazz"]):
        tags.add("jazz")

    if any(p in titulo for p in ["opera", "ópera", "zarzuela"]):
        tags.add("clasica")

    if any(p in titulo for p in ["rock", "metal", "punk"]):
        tags.add("rock")

    if any(p in titulo for p in ["electro", "techno", "club", "microdosis"]):
        tags.add("electronica")

    return sorted(tags)


def _lineas_limpias_html(html):
    soup = BeautifulSoup(html, "html.parser")
    return [
        limpiar_texto(l)
        for l in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(l)
    ]


def _parsear_linea_fechas_canal(linea):
    texto = limpiar_texto(linea).lower()

    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        inicio = construir_fecha(int(m.group(1)), m.group(2), int(m.group(5)))
        fin = construir_fecha(int(m.group(3)), m.group(4), int(m.group(5)))
        if inicio and fin:
            return {
                "tipo_fecha": "rango",
                "fecha_inicio": inicio.isoformat(),
                "fecha_fin": fin.isoformat(),
                "fechas_funcion": []
            }

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
                "tipo_fecha": "rango",
                "fecha_inicio": inicio.isoformat(),
                "fecha_fin": fin.isoformat(),
                "fechas_funcion": []
            }

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
        fechas = [f.isoformat() for f in fechas if f]
        if fechas:
            return {
                "tipo_fecha": "lista",
                "fechas_funcion": fechas
            }

    m = re.search(
        r"(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        fechas = [
            construir_fecha(int(m.group(1)), m.group(3), int(m.group(4))),
            construir_fecha(int(m.group(2)), m.group(3), int(m.group(4))),
        ]
        fechas = [f.isoformat() for f in fechas if f]
        if fechas:
            return {
                "tipo_fecha": "lista",
                "fechas_funcion": fechas
            }

    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        f = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        if f:
            return {
                "tipo_fecha": "unica",
                "fecha": f.isoformat()
            }

    return None


def extraer_metadatos_canal(url_evento):
    try:
        r = get_url(url_evento, timeout=30)
    except Exception:
        return {}

    lineas = _lineas_limpias_html(r.text)

    for linea in lineas:
        datos = _parsear_linea_fechas_canal(linea)
        if datos:
            return normalizar_info_fecha(datos) or {}

    return {}


def _parsear_linea_fechas_gruposmedia(linea):
    texto = limpiar_texto(linea).lower()

    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        inicio = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        fin = construir_fecha(int(m.group(4)), m.group(5), int(m.group(6)))
        if inicio and fin:
            return {
                "tipo_fecha": "rango",
                "fecha_inicio": inicio.isoformat(),
                "fecha_fin": fin.isoformat(),
                "fechas_funcion": []
            }

    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        inicio = construir_fecha(int(m.group(1)), m.group(2), int(m.group(5)))
        fin = construir_fecha(int(m.group(3)), m.group(4), int(m.group(5)))
        if inicio and fin:
            return {
                "tipo_fecha": "rango",
                "fecha_inicio": inicio.isoformat(),
                "fecha_fin": fin.isoformat(),
                "fechas_funcion": []
            }

    m = re.search(
        r"(\d{1,2})\s*,\s*(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        anio = int(m.group(5))
        fechas = [
            construir_fecha(int(m.group(1)), m.group(4), anio),
            construir_fecha(int(m.group(2)), m.group(4), anio),
            construir_fecha(int(m.group(3)), m.group(4), anio),
        ]
        fechas = [f.isoformat() for f in fechas if f]
        if fechas:
            return {
                "tipo_fecha": "lista",
                "fechas_funcion": fechas
            }

    m = re.search(
        r"(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        anio = int(m.group(4))
        fechas = [
            construir_fecha(int(m.group(1)), m.group(3), anio),
            construir_fecha(int(m.group(2)), m.group(3), anio),
        ]
        fechas = [f.isoformat() for f in fechas if f]
        if fechas:
            return {
                "tipo_fecha": "lista",
                "fechas_funcion": fechas
            }

    m = re.search(
        r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        fin = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        if fin:
            return {
                "tipo_fecha": "hasta",
                "fecha_fin": fin.isoformat()
            }

    m = re.search(
        r"desde\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        inicio = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        if inicio:
            return {
                "tipo_fecha": "desde",
                "fecha_inicio": inicio.isoformat()
            }

    return None


def extraer_metadatos_gruposmedia(url_evento):
    try:
        r = get_url(url_evento, timeout=30)
    except Exception:
        return {}

    lineas = _lineas_limpias_html(r.text)

    for linea in lineas[:200]:
        datos = _parsear_linea_fechas_gruposmedia(linea)
        if datos:
            return normalizar_info_fecha(datos) or {}

    return {}


def extraer_metadatos_fuente(url_evento):
    url = (url_evento or "").lower()

    if "teatroscanal.com/espectaculo/" in url:
        return extraer_metadatos_canal(url_evento)

    if "gruposmedia.com/cartelera/" in url:
        return extraer_metadatos_gruposmedia(url_evento)

    return {}


def enriquecer_evento_nuevo(evento):
    ahora = datetime.now().isoformat()
    tipo_evento = clasificar_tipo_evento(evento)
    tags = generar_tags(evento, tipo_evento)

    evento["first_seen"] = ahora
    evento["last_seen"] = ahora
    evento["estado"] = "nuevo"
    evento["enriched"] = True
    evento["tipo_evento"] = tipo_evento
    evento["tags"] = tags

    return evento


def actualizar_evento_existente(evento_master, evento_actual):
    ahora = datetime.now().isoformat()

    evento_master["titulo"] = evento_actual.get("titulo", evento_master.get("titulo", ""))
    evento_master["fecha"] = evento_actual.get("fecha", evento_master.get("fecha", ""))
    evento_master["lugar"] = evento_actual.get("lugar", evento_master.get("lugar", ""))
    evento_master["fuente"] = evento_actual.get("fuente", evento_master.get("fuente", ""))
    evento_master["url_evento"] = evento_actual.get("url_evento", evento_master.get("url_evento", ""))

    evento_master["tipo_fecha"] = evento_actual.get("tipo_fecha", evento_master.get("tipo_fecha", ""))
    evento_master["rango_fechas"] = evento_actual.get("rango_fechas", evento_master.get("rango_fechas", False))
    evento_master["fecha_inicio"] = evento_actual.get("fecha_inicio", evento_master.get("fecha_inicio"))
    evento_master["fecha_fin"] = evento_actual.get("fecha_fin", evento_master.get("fecha_fin"))
    evento_master["fechas_funcion"] = evento_actual.get("fechas_funcion", evento_master.get("fechas_funcion", []))
    evento_master["dias_semana"] = evento_actual.get("dias_semana", evento_master.get("dias_semana", []))
    evento_master["texto_fecha_original"] = evento_actual.get(
        "texto_fecha_original",
        evento_master.get("texto_fecha_original", "")
    )

    evento_master["last_seen"] = ahora
    evento_master["estado"] = "activo"
    evento_master["enriched"] = True

    if "tipo_evento" not in evento_master:
        tipo_evento = clasificar_tipo_evento(evento_actual)
        evento_master["tipo_evento"] = tipo_evento
        evento_master["tags"] = generar_tags(evento_actual, tipo_evento)

    return evento_master


def reconciliar_master(eventos_json_actuales, master_anterior):
    ahora = datetime.now().isoformat()

    master_por_clave = indexar_por_clave(master_anterior)
    claves_master_anteriores = set(master_por_clave.keys())
    claves_actuales = set()

    nuevos = 0
    existentes = 0
    duplicados_en_lote = 0

    for evento in eventos_json_actuales:
        clave = clave_evento_json(evento)

        if not clave[0]:
            continue

        if clave in claves_actuales:
            duplicados_en_lote += 1
            continue

        claves_actuales.add(clave)

        if clave in claves_master_anteriores:
            actualizar_evento_existente(master_por_clave[clave], evento)
            existentes += 1
        else:
            master_por_clave[clave] = enriquecer_evento_nuevo(evento)
            nuevos += 1

    desaparecidos = 0

    for clave, evento_master in master_por_clave.items():
        if clave not in claves_actuales:
            evento_master["estado"] = "desaparecido"
            if "last_seen" not in evento_master:
                evento_master["last_seen"] = ahora
            desaparecidos += 1

    master_actualizado = list(master_por_clave.values())
    master_actualizado.sort(
        key=lambda e: (
            e.get("fecha", "") or e.get("fecha_fin", "") or "",
            e.get("lugar", ""),
            e.get("titulo", ""),
        )
    )

    return master_actualizado, nuevos, existentes, desaparecidos, duplicados_en_lote


def main():
    todos_los_eventos = []
    master_anterior = cargar_master()

    print(f"[DEBUG] eventos en master anterior: {len(master_anterior)}")

    fuentes = [
        sacar_eslava,
        sacar_but,
        sacar_elsol,
        sacar_vistalegre,
        sacar_granvia,
        sacar_alcazar,
        sacar_maravillas,
        sacar_figaro,
        sacar_pequenogranvia,
        sacar_capitol,
        sacar_aranjuez,
        sacar_matadero,
        sacar_canal,
        sacar_riviera,
        sacar_berlin,
        sacar_movistararena,
        sacar_auditorio,
        sacar_fernangomez,
        sacar_teatroespanol,
        sacar_ifema,
        sacar_condeduque,
        sacar_salavillanos,
        sacar_galileo,
        sacar_clamores,
        sacar_nazca,
        sacar_replika,
        sacar_labtheclub,
        sacar_maria_guerrero,
        sacar_grupomarquina,
        sacar_valle_inclan,
        sacar_abadia,
        sacar_circulo_bellas_artes,
        sacar_lara,
        sacar_bellasartes,
        sacar_price,
        sacar_teatrolalatina,
        sacar_teatroreal,
        sacar_zarzuela,
        sacar_lazarogaldiano,
    ]

    for funcion in fuentes:
        try:
            eventos = funcion()
            eventos = limpiar_eventos(eventos)
            todos_los_eventos.extend(eventos)
            print(f"[OK] {funcion.__name__}: {len(eventos)} eventos")
        except Exception as e:
            print(f"[ERROR] {funcion.__name__}: {e}")

    todos_los_eventos.sort(key=clave_orden_fecha)

    eventos_json_actuales = eventos_a_json(todos_los_eventos)

    master_actualizado, nuevos, existentes, desaparecidos, duplicados_en_lote = reconciliar_master(
        eventos_json_actuales,
        master_anterior
    )

    guardar_csv(todos_los_eventos)
    guardar_json(todos_los_eventos)
    guardar_master(master_actualizado)

    print("[OK] Archivo eventos.csv generado correctamente")
    print("[OK] Archivo eventos.json generado correctamente")
    print("[OK] Archivo eventos_master.json generado correctamente")
    print(f"[OK] Total eventos snapshot: {len(todos_los_eventos)}")
    print(f"[OK] Eventos nuevos: {nuevos}")
    print(f"[OK] Eventos existentes: {existentes}")
    print(f"[OK] Eventos desaparecidos: {desaparecidos}")
    print(f"[OK] Duplicados exactos en lote: {duplicados_en_lote}")


if __name__ == "__main__":
    main()