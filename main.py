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

from utils import get_url, limpiar_texto, construir_fecha

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# -------------------------
# EXPORTACIÓN
# -------------------------

def guardar_csv(eventos, nombre_archivo="eventos.csv"):
    with open(nombre_archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["TITULO EVENTO", "FECHA", "LUGAR", "URL EVENTO", "FUENTE"])

        for fila in eventos:
            writer.writerow(fila)


def eventos_a_json(eventos):
    eventos_json = []

    for fila in eventos:
        if len(fila) < 5:
            continue

        titulo, fecha, lugar, url_evento, fuente = fila

        if not fecha or "/" not in fecha:
            continue

        partes = fecha.split("/")
        if len(partes) != 3:
            continue

        dia, mes, anio = partes

        if not (dia.isdigit() and mes.isdigit() and anio.isdigit()):
            continue

        fecha_iso = f"{anio}-{mes.zfill(2)}-{dia.zfill(2)}"

        eventos_json.append({
            "titulo": titulo,
            "fecha": fecha_iso,
            "lugar": lugar,
            "url_evento": url_evento,
            "fuente": fuente
        })

    return eventos_json


def guardar_json(eventos, nombre_archivo="eventos.json"):
    eventos_json = eventos_a_json(eventos)

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        json.dump(eventos_json, f, ensure_ascii=False, indent=2)


# -------------------------
# MASTER
# -------------------------

def cargar_master(nombre="eventos_master.json"):
    if not os.path.exists(nombre):
        return []

    with open(nombre, encoding="utf-8") as f:
        return json.load(f)


def guardar_master(eventos, nombre="eventos_master.json"):
    with open(nombre, "w", encoding="utf-8") as f:
        json.dump(eventos, f, ensure_ascii=False, indent=2)


# -------------------------
# CLAVE
# -------------------------

def clave_evento_json(evento):
    return (
        evento.get("url_evento", "").strip(),
        evento.get("fecha", "").strip(),
        evento.get("lugar", "").strip().lower(),
    )


def indexar_por_clave(eventos):
    indice = {}

    for evento in eventos:
        clave = clave_evento_json(evento)
        if clave[0] and clave[1]:
            indice[clave] = evento

    return indice


# -------------------------
# ORDEN
# -------------------------

def clave_orden_fecha(fila):
    if len(fila) < 2:
        return datetime.max

    fecha = fila[1]

    try:
        return datetime.strptime(fecha, "%d/%m/%Y")
    except Exception:
        return datetime.max


# -------------------------
# CLASIFICACIÓN BÁSICA
# -------------------------

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

    if any(p in lugar for p in ["sala", "arena", "café berlín", "cafe berlin", "auditorio", "teatro eslava"]):
        return "concierto"

    if any(p in lugar for p in ["teatro", "teatros del canal", "figaro", "alcázar", "alcazar", "gran vía", "gran via", "maravillas"]):
        return "teatro"

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


# -------------------------
# METADATOS EXTRA CANAL
# -------------------------

def _lineas_limpias_html(html):
    soup = BeautifulSoup(html, "html.parser")
    return [
        limpiar_texto(l)
        for l in soup.get_text("\n", strip=True).splitlines()
        if limpiar_texto(l)
    ]


def _parsear_linea_fechas_canal(linea):
    texto = limpiar_texto(linea).lower()

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
                "rango_fechas": True,
                "fecha_inicio": inicio.isoformat(),
                "fecha_fin": fin.isoformat(),
                "fechas_funcion": []
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
                "rango_fechas": True,
                "fecha_inicio": inicio.isoformat(),
                "fecha_fin": fin.isoformat(),
                "fechas_funcion": []
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
        fechas = [f.isoformat() for f in fechas if f]
        if fechas:
            return {
                "rango_fechas": False,
                "fecha_inicio": fechas[0],
                "fecha_fin": fechas[-1],
                "fechas_funcion": fechas
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
        fechas = [f.isoformat() for f in fechas if f]
        if fechas:
            return {
                "rango_fechas": False,
                "fecha_inicio": fechas[0],
                "fecha_fin": fechas[-1],
                "fechas_funcion": fechas
            }

    # 12 de abril de 2026
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        texto
    )
    if m:
        f = construir_fecha(int(m.group(1)), m.group(2), int(m.group(3)))
        if f:
            iso = f.isoformat()
            return {
                "rango_fechas": False,
                "fecha_inicio": iso,
                "fecha_fin": iso,
                "fechas_funcion": [iso]
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
            return datos

    return {}


# -------------------------
# ENRIQUECIMIENTO
# -------------------------

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

    if "teatroscanal.com/espectaculo/" in evento.get("url_evento", ""):
        evento.update(extraer_metadatos_canal(evento["url_evento"]))

    return evento


def actualizar_evento_existente(evento_master, evento_actual):
    ahora = datetime.now().isoformat()

    evento_master["titulo"] = evento_actual.get("titulo", evento_master.get("titulo", ""))
    evento_master["fecha"] = evento_actual.get("fecha", evento_master.get("fecha", ""))
    evento_master["lugar"] = evento_actual.get("lugar", evento_master.get("lugar", ""))
    evento_master["fuente"] = evento_actual.get("fuente", evento_master.get("fuente", ""))
    evento_master["last_seen"] = ahora
    evento_master["estado"] = "activo"

    if "tipo_evento" not in evento_master:
        tipo_evento = clasificar_tipo_evento(evento_actual)
        evento_master["tipo_evento"] = tipo_evento
        evento_master["tags"] = generar_tags(evento_actual, tipo_evento)

    if "teatroscanal.com/espectaculo/" in evento_master.get("url_evento", ""):
        if (
            "fechas_funcion" not in evento_master and
            "fecha_inicio" not in evento_master and
            "fecha_fin" not in evento_master
        ):
            evento_master.update(extraer_metadatos_canal(evento_master["url_evento"]))

    return evento_master


# -------------------------
# CORE INCREMENTAL
# -------------------------

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

        if not clave[0] or not clave[1]:
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
        key=lambda e: (e.get("fecha", ""), e.get("lugar", ""), e.get("titulo", ""))
    )

    return master_actualizado, nuevos, existentes, desaparecidos, duplicados_en_lote


# -------------------------
# MAIN
# -------------------------

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
    ]

    for funcion in fuentes:
        try:
            eventos = funcion()
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