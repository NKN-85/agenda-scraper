from fastapi import FastAPI, Query, Response
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union
import requests
import unicodedata
import os
import json
import re
from datetime import date, timedelta, datetime

app = FastAPI(
    title="API Agenda Cultural",
    description="API para consultar eventos de agenda cultural",
    version="2.7.0",
    servers=[
        {
            "url": "https://agenda-api-zpmf.onrender.com",
            "description": "Render production"
        }
    ]
)


class RootResponse(BaseModel):
    ok: bool
    servicio: str


class EventosResponse(BaseModel):
    total: int
    eventos: List[Dict[str, Any]]


class EventosRangoResponse(BaseModel):
    desde: str
    hasta: str
    total: int
    eventos: List[Dict[str, Any]]


class EventosDiaResponse(BaseModel):
    fecha: str
    total: int
    eventos: List[Dict[str, Any]]


class EvergreenItem(BaseModel):
    id: str
    titulo: str
    url: str
    fuente: str
    categoria: str
    intencion: str
    tipo_contenido: str
    pagina_padre: str
    descripcion: Optional[str] = ""
    score_editorial: int


class EvergreenCategoria(BaseModel):
    categoria: str
    total_items: int
    items: List[EvergreenItem]


class EvergreenBloque(BaseModel):
    intencion: str
    total_items: int
    categorias: List[EvergreenCategoria]


class EvergreenResponse(BaseModel):
    total_bloques: int
    bloques: List[EvergreenBloque]


class EvergreenTopResponse(BaseModel):
    intencion: str
    categoria: Optional[str] = None
    limit: int
    total_disponibles: int
    total_devuelto: int
    items: List[EvergreenItem]


class EvergreenSearchResponse(BaseModel):
    q: Optional[str] = None
    intencion: Optional[str] = None
    categoria: Optional[str] = None
    total: int
    total_devuelto: int
    limit: int
    offset: int
    items: List[EvergreenItem]


class EvergreenIntencionesResponse(BaseModel):
    total: int
    intenciones: List[str]


class EvergreenCategoriasResponse(BaseModel):
    total: int
    intencion: Optional[str] = None
    categorias: List[str]


class EvergreenResumenCategoria(BaseModel):
    categoria: str
    total_items: int


class EvergreenResumenBloque(BaseModel):
    intencion: str
    total_items: int
    categorias: List[EvergreenResumenCategoria]


class EvergreenResumenResponse(BaseModel):
    total_bloques: int
    total_items: int
    bloques: List[EvergreenResumenBloque]


class EvergreenRandomResponse(BaseModel):
    intencion: Optional[str] = None
    categoria: Optional[str] = None
    total_disponibles: int
    total_devuelto: int
    items: List[EvergreenItem]


class ErrorResponse(BaseModel):
    error: str
    intenciones_disponibles: List[str]


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


URL_JSON = "https://raw.githubusercontent.com/NKN-85/agenda-scraper/refs/heads/main/eventos_master.json"
URL_EVERGREEN_JSON = "https://raw.githubusercontent.com/NKN-85/agenda-scraper/refs/heads/main/evergreen_output.json"

ENV = os.getenv("ENV", "local")


def cargar_eventos():
    if ENV == "local":
        with open("eventos_master.json", "r", encoding="utf-8") as f:
            return json.load(f)

    response = requests.get(URL_JSON, timeout=20)
    response.raise_for_status()
    return response.json()


def cargar_evergreen():
    if ENV == "local":
        try:
            with open("evergreen_output.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    try:
        response = requests.get(URL_EVERGREEN_JSON, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception:
        return []


def normalizar_texto(texto):
    if not texto:
        return ""

    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def texto_contiene_variante(texto_norm, variante):
    if not texto_norm or not variante:
        return False

    variante_norm = normalizar_texto(variante)
    if not variante_norm:
        return False

    patron = rf"(?<![a-z0-9]){re.escape(variante_norm)}(?![a-z0-9])"
    return re.search(patron, texto_norm) is not None


def parse_fecha_iso(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except Exception:
        return None


def expandir_patron_en_rango(evento, fecha_inicio, fecha_fin):
    dias_semana = evento.get("dias_semana", []) or []
    if not dias_semana:
        return False

    limite_inicio = parse_fecha_iso(evento.get("fecha_inicio"))
    limite_fin = parse_fecha_iso(evento.get("fecha_fin"))

    cursor = fecha_inicio

    while cursor <= fecha_fin:
        if limite_inicio and cursor < limite_inicio:
            cursor += timedelta(days=1)
            continue

        if limite_fin and cursor > limite_fin:
            break

        if cursor.weekday() in dias_semana:
            return True

        cursor += timedelta(days=1)

    return False


def coincide_fechas(evento, fecha_inicio, fecha_fin):
    tipo_fecha = (evento.get("tipo_fecha") or "").strip().lower()

    inicio = parse_fecha_iso(evento.get("fecha_inicio"))
    fin = parse_fecha_iso(evento.get("fecha_fin"))
    fecha_simple = parse_fecha_iso(evento.get("fecha"))
    fechas = evento.get("fechas_funcion", []) or []
    dias_semana = evento.get("dias_semana", []) or []

    if dias_semana:
        return expandir_patron_en_rango(evento, fecha_inicio, fecha_fin)

    if fechas:
        for f in fechas:
            fecha = parse_fecha_iso(f)
            if fecha and fecha_inicio <= fecha <= fecha_fin:
                return True
        return False

    if tipo_fecha == "rango":
        return bool(inicio and fin and not (fin < fecha_inicio or inicio > fecha_fin))

    if tipo_fecha == "hasta":
        return bool(fin and fin >= fecha_inicio)

    if tipo_fecha == "desde":
        return bool(inicio and inicio <= fecha_fin)

    if fecha_simple:
        return fecha_inicio <= fecha_simple <= fecha_fin

    if inicio and fin:
        return not (fin < fecha_inicio or inicio > fecha_fin)

    if fin and not inicio:
        return fin >= fecha_inicio

    if inicio and not fin:
        return inicio <= fecha_fin

    return False


SALA_ALIAS = {
    "alcazar": "teatro alcazar",
    "teatro alcazar": "teatro alcazar",
    "gran via": "teatro gran via",
    "granvia": "teatro gran via",
    "teatro gran via": "teatro gran via",
    "teatro granvia": "teatro gran via",
    "capitol": "capitol gran via",
    "capitol gran via": "capitol gran via",
    "pequeno gran via": "pequeno teatro gran via",
    "pequeno teatro gran via": "pequeno teatro gran via",
    "pequeño gran via": "pequeno teatro gran via",
    "pequeño teatro gran via": "pequeno teatro gran via",
    "pequenogranvia": "pequeno teatro gran via",
    "pequeñogranvia": "pequeno teatro gran via",
    "figaro": "teatro figaro",
    "teatro figaro": "teatro figaro",
    "maravillas": "teatro maravillas",
    "teatro maravillas": "teatro maravillas",
    "canal": "teatros del canal",
    "teatros del canal": "teatros del canal",
    "eslava": "teatro eslava",
    "teatro eslava": "teatro eslava",
    "but": "sala but",
    "sala but": "sala but",
    "elsol": "sala el sol",
    "el sol": "sala el sol",
    "sala el sol": "sala el sol",
    "riviera": "sala la riviera",
    "la riviera": "sala la riviera",
    "sala la riviera": "sala la riviera",
    "berlin": "cafe berlin",
    "cafe berlin": "cafe berlin",
    "café berlin": "cafe berlin",
    "movistar": "movistar arena",
    "movistar arena": "movistar arena",
    "movistararena": "movistar arena",
    "auditorio": "auditorio nacional",
    "inaem": "auditorio nacional",
    "auditorio nacional": "auditorio nacional",
    "auditorio nacional de musica": "auditorio nacional",
    "auditorionacional": "auditorio nacional",
    "aranjuez": "teatro real carlos iii de aranjuez",
    "teatro aranjuez": "teatro real carlos iii de aranjuez",
    "teatro real carlos iii": "teatro real carlos iii de aranjuez",
    "teatro real carlos iii de aranjuez": "teatro real carlos iii de aranjuez",
    "matadero": "matadero madrid",
    "matadero madrid": "matadero madrid",
    "vistalegre": "palacio vistalegre",
    "palacio vistalegre": "palacio vistalegre",
    "vistalegre arena": "palacio vistalegre",
    "fernan": "teatro fernan gomez",
    "fernan gomez": "teatro fernan gomez",
    "fernangomez": "teatro fernan gomez",
    "teatro fernan gomez": "teatro fernan gomez",
    "teatro fernán gómez": "teatro fernan gomez",
    "teatrofernangomez": "teatro fernan gomez",
    "teatro fernangomez": "teatro fernan gomez",
    "fernan-gomez": "teatro fernan gomez",
    "fernan gómez": "teatro fernan gomez",
    "guirau": "teatro fernan gomez",
    "jardiel poncela": "teatro fernan gomez",
    "espanol": "teatro espanol",
    "teatro espanol": "teatro espanol",
    "teatro español": "teatro espanol",
    "teatroespanol": "teatro espanol",
    "ifema": "ifema madrid",
    "ifema madrid": "ifema madrid",
    "condeduque": "condeduque madrid",
    "condeduque madrid": "condeduque madrid",
    "villanos": "sala villanos",
    "sala villanos": "sala villanos",
    "salavillanos": "sala villanos",
    "galileo": "sala galileo galilei",
    "sala galileo": "sala galileo galilei",
    "galileo galilei": "sala galileo galilei",
    "sala galileo galilei": "sala galileo galilei",
    "salagalileo": "sala galileo galilei",
    "clamores": "sala clamores",
    "sala clamores": "sala clamores",
    "nazca": "sala nazca",
    "sala nazca": "sala nazca",
    "nazca conciertos": "sala nazca",
    "replika": "replika teatro",
    "replika teatro": "replika teatro",
    "réplika": "replika teatro",
    "réplika teatro": "replika teatro",
    "lab": "lab the club",
    "lab the club": "lab the club",
    "labtheclub": "lab the club",
    "maria guerrero": "teatro maria guerrero",
    "maria_guerrero": "teatro maria guerrero",
    "maria-guerrero": "teatro maria guerrero",
    "maría guerrero": "teatro maria guerrero",
    "teatro maria guerrero": "teatro maria guerrero",
    "teatro_maria_guerrero": "teatro maria guerrero",
    "teatro-maria-guerrero": "teatro maria guerrero",
    "teatro maría guerrero": "teatro maria guerrero",
    "marquina": "teatro marquina",
    "teatro marquina": "teatro marquina",
    "principe": "teatro principe gran via",
    "principe gran via": "teatro principe gran via",
    "príncipe gran vía": "teatro principe gran via",
    "teatro principe gran via": "teatro principe gran via",
    "teatro príncipe gran vía": "teatro principe gran via",
    "valle inclan": "teatro valle inclan",
    "valle-inclan": "teatro valle inclan",
    "valleinclan": "teatro valle inclan",
    "teatro valle inclan": "teatro valle inclan",
    "teatro valle-inclan": "teatro valle inclan",
    "abadia": "teatro de la abadia",
    "teatro de la abadia": "teatro de la abadia",
    "teatro abadia": "teatro de la abadia",
    "teatroabadia": "teatro de la abadia",
    "circulo de bellas artes": "circulo de bellas artes",
    "circulo bellas artes": "circulo de bellas artes",
    "circulo_bellas_artes": "circulo de bellas artes",
    "circulo-bellas-artes": "circulo de bellas artes",
    "círculo de bellas artes": "circulo de bellas artes",
    "círculo bellas artes": "circulo de bellas artes",
    "cba": "circulo de bellas artes",
    "lara": "teatro lara",
    "teatro lara": "teatro lara",
    "teatro bellas artes": "teatro bellas artes",
    "teatrobellasartes": "teatro bellas artes",
    "teatro-bellas-artes": "teatro bellas artes",
    "price": "teatro circo price",
    "circo price": "teatro circo price",
    "teatro circo price": "teatro circo price",
    "teatrocircoprice": "teatro circo price",
    "la latina": "teatro la latina",
    "teatro la latina": "teatro la latina",
    "teatrolalatina": "teatro la latina",
    "teatro_la_latina": "teatro la latina",
    "teatro-la-latina": "teatro la latina",
    "latina": "teatro la latina",
    "teatroreal": "teatro real",
    "teatro real": "teatro real",
    "zarzuela": "teatro de la zarzuela",
    "teatro zarzuela": "teatro de la zarzuela",
    "teatro de la zarzuela": "teatro de la zarzuela",
    "teatrodelazarzuela": "teatro de la zarzuela",
    "lazaro galdiano": "museo lazaro galdiano",
    "lázaro galdiano": "museo lazaro galdiano",
    "museo lazaro galdiano": "museo lazaro galdiano",
    "museo lázaro galdiano": "museo lazaro galdiano",
    "lazarogaldiano": "museo lazaro galdiano",
    "lazaro_galdiano": "museo lazaro galdiano",
    "lazaro-galdiano": "museo lazaro galdiano",
}


SALA_VARIANTES = {
    "movistar arena": ["movistar arena", "movistararena", "wizink center", "wi zink"],
    "auditorio nacional": [
        "auditorio nacional",
        "auditorio nacional de musica",
        "auditorionacional",
        "auditorio nacional inaem",
        "auditorio nacional de musica inaem",
        "sala sinfonica",
        "sala de camara",
        "sala satelite",
    ],
    "palacio vistalegre": ["palacio vistalegre", "vistalegre"],
    "sala la riviera": ["sala la riviera", "la riviera", "riviera"],
    "sala el sol": ["sala el sol", "salaelsol"],
    "pequeno teatro gran via": [
        "pequeno teatro gran via",
        "pequeno gran via",
        "pequeño teatro gran via",
        "pequeño gran via",
        "pequenogranvia",
    ],
    "teatro fernan gomez": [
        "teatro fernan gomez",
        "teatro fernán gómez",
        "teatrofernangomez",
        "teatro fernangomez",
        "fernan gomez",
        "fernán gómez",
        "fernangomez",
        "guirau",
        "sala guirau",
        "jardiel poncela",
        "sala jardiel poncela",
    ],
    "teatro espanol": ["teatro espanol", "teatro español", "teatroespanol"],
    "ifema madrid": ["ifema", "ifema madrid", "feria de madrid"],
    "condeduque madrid": [
        "condeduque madrid",
        "condeduque",
        "condeduquemadrid",
        "condeduquemadrid es",
        "contemporanea condeduque",
    ],
    "sala villanos": ["sala villanos", "villanos", "salavillanos", "villanosmadrid"],
    "sala galileo galilei": [
        "sala galileo galilei",
        "galileo galilei",
        "sala galileo",
        "salagalileo",
        "salagalileo es",
        "galileo madrid",
    ],
    "sala clamores": ["sala clamores", "clamores", "clamores live"],
    "sala nazca": ["sala nazca", "nazca", "nazca conciertos", "salanazcaconciertos"],
    "replika teatro": ["replika teatro", "réplika teatro", "replika", "réplika", "replikateatro", "replikateatro com"],
    "lab the club": ["lab the club", "labtheclub", "labtheclub com", "www labtheclub com"],
    "teatro maria guerrero": [
        "teatro maria guerrero",
        "teatro maría guerrero",
        "maria guerrero",
        "maría guerrero",
        "sala de la princesa",
        "sala pequena",
        "sala pequeña",
    ],
    "teatro marquina": ["teatro marquina", "marquina", "grupomarquina", "grupo marquina"],
    "teatro principe gran via": [
        "teatro principe gran via",
        "teatro príncipe gran vía",
        "principe gran via",
        "príncipe gran vía",
    ],
    "teatro valle inclan": [
        "teatro valle inclan",
        "teatro valle-inclan",
        "valle inclan",
        "valle-inclan",
        "valleinclan",
        "sala francisco nieva",
        "sala el mirlo blanco",
    ],
    "teatro de la abadia": [
        "teatro de la abadia",
        "teatro abadia",
        "teatroabadia",
        "sala juan de la cruz",
        "sala jose luis alonso",
        "sala josé luis alonso",
    ],
    "circulo de bellas artes": [
        "circulo de bellas artes",
        "círculo de bellas artes",
        "circulo bellas artes",
        "círculo bellas artes",
        "circulobellasartes",
    ],
    "teatro lara": ["teatro lara", "teatrolara", "teatrolara com", "sala candido lara", "sala cándido lara", "sala lola membrives"],
    "teatro bellas artes": ["teatro bellas artes", "teatrobellasartes", "teatrobellasartes es"],
    "teatro circo price": ["teatro circo price", "circo price", "teatrocircoprice", "teatrocircoprice es"],
    "teatro la latina": ["teatro la latina", "la latina", "latina", "teatrolalatina"],
    "teatro real": ["teatroreal"],
    "teatro real carlos iii de aranjuez": [
        "teatro real carlos iii de aranjuez",
        "teatro aranjuez",
        "teatroaranjuez",
        "teatro real carlos iii",
    ],
    "teatro de la zarzuela": ["teatro de la zarzuela", "teatrodelazarzuela", "teatrodelazarzuela inaem gob es"],
    "museo lazaro galdiano": [
        "museo lazaro galdiano",
        "museo lázaro galdiano",
        "lazaro galdiano",
        "lázaro galdiano",
        "lazarogaldiano",
    ],
}


TIPO_EVENTO_ALIAS = {
    "concierto": "concierto",
    "conciertos": "concierto",
    "musica": "concierto",
    "música": "concierto",
    "teatro": "teatro",
    "musical": "musical",
    "musicales": "musical",
    "exposicion": "exposicion",
    "exposición": "exposicion",
    "exposiciones": "exposicion",
    "taller": "taller",
    "talleres": "taller",
    "danza": "danza",
    "cine": "cine",
    "comedia": "comedia",
    "circo": "circo",
    "deporte": "deporte",
    "otros": "otros",
}


def obtener_nombre_sala_canonico(sala_usuario):
    s = normalizar_texto(sala_usuario)
    return SALA_ALIAS.get(s)


def coincide_sala(evento, sala):
    if not sala:
        return True

    sala_norm = normalizar_texto(sala)
    lugar_norm = normalizar_texto(evento.get("lugar", ""))
    fuente_norm = normalizar_texto(evento.get("fuente", ""))
    url_norm = normalizar_texto(evento.get("url_evento", ""))

    sala_canonica = obtener_nombre_sala_canonico(sala)

    if sala_canonica == "teatro real":
        return (
            lugar_norm == "teatro real"
            or texto_contiene_variante(url_norm, "teatroreal")
            or texto_contiene_variante(fuente_norm, "teatroreal")
        )

    if sala_canonica:
        candidatos = [sala_canonica] + SALA_VARIANTES.get(sala_canonica, [])

        for candidato in candidatos:
            if texto_contiene_variante(lugar_norm, candidato):
                return True

        for candidato in candidatos:
            if texto_contiene_variante(url_norm, candidato):
                return True

        for candidato in SALA_VARIANTES.get(sala_canonica, []):
            if texto_contiene_variante(fuente_norm, candidato):
                return True

        return False

    return (
        texto_contiene_variante(lugar_norm, sala_norm)
        or texto_contiene_variante(url_norm, sala_norm)
    )


def normalizar_tipo_evento(tipo_evento):
    if not tipo_evento:
        return None

    tipo_norm = normalizar_texto(tipo_evento)
    return TIPO_EVENTO_ALIAS.get(tipo_norm, tipo_norm)


def coincide_tipo_evento(evento, tipo_evento):
    if not tipo_evento:
        return True

    tipo_evento_norm = normalizar_tipo_evento(tipo_evento)
    tipo_evento_actual = normalizar_tipo_evento(evento.get("tipo_evento", ""))

    return tipo_evento_actual == tipo_evento_norm


def filtrar_eventos(
    eventos,
    fecha_inicio=None,
    fecha_fin=None,
    sala=None,
    tipo_evento=None,
    solo_activos=True
):
    resultado = []

    for evento in eventos:
        if solo_activos and evento.get("estado") not in {"activo", "nuevo"}:
            continue

        if not coincide_sala(evento, sala):
            continue

        if not coincide_tipo_evento(evento, tipo_evento):
            continue

        if fecha_inicio and fecha_fin:
            if not coincide_fechas(evento, fecha_inicio, fecha_fin):
                continue

        resultado.append(evento)

    return resultado


def buscar_bloque_evergreen(bloques, intencion):
    intencion_norm = normalizar_texto(intencion)

    return next(
        (
            b for b in bloques
            if normalizar_texto(b.get("intencion")) == intencion_norm
        ),
        None
    )


def extraer_items_evergreen(bloque, categoria=None):
    if not bloque:
        return []

    categorias_norm = categoria_aliases_evergreen(categoria) if categoria else None
    filtros_categoria = extraer_filtros_desde_q(categoria) if categoria else None
    items = []

    for categoria_data in bloque.get("categorias", []) or []:
        nombre_categoria = categoria_data.get("categoria", "")

        if categorias_norm and normalizar_texto(nombre_categoria) not in categorias_norm:
            # Si categoria no era categoría real sino alias tipo "senderismo",
            # permitimos filtrar a nivel item por los campos enriquecidos.
            if not filtros_categoria:
                continue

        for item in categoria_data.get("items", []) or []:
            if filtros_categoria and not item_cumple_filtros_inteligentes(item, filtros_categoria):
                continue

            if categorias_norm and normalizar_texto(nombre_categoria) not in categorias_norm and not filtros_categoria:
                continue

            items.append(item)

    return sorted(
        items,
        key=lambda x: x.get("score_editorial", 0),
        reverse=True
    )


def paginar_items(items, limit=10, offset=0, max_limit=50):
    if limit < 1:
        limit = 1
    if limit > max_limit:
        limit = max_limit
    if offset < 0:
        offset = 0

    return items[offset:offset + limit], limit, offset


def texto_evergreen_busqueda(item):
    return texto_evergreen_busqueda_ampliado(item)


def listar_intenciones_evergreen(bloques):
    return sorted(
        {
            bloque.get("intencion")
            for bloque in bloques
            if bloque.get("intencion")
        }
    )


def listar_categorias_evergreen(bloques, intencion=None):
    intencion_norm = normalizar_texto(intencion) if intencion else None
    categorias = set()

    for bloque in bloques:
        if intencion_norm and normalizar_texto(bloque.get("intencion")) != intencion_norm:
            continue

        for categoria_data in bloque.get("categorias", []) or []:
            categoria = categoria_data.get("categoria")
            if categoria:
                categorias.add(categoria)

    return sorted(categorias)


def extraer_todos_items_evergreen(bloques, intencion=None, categoria=None):
    intencion_norm = normalizar_intencion_evergreen_alias(intencion) if intencion else None
    categorias_norm = categoria_aliases_evergreen(categoria) if categoria else None
    filtros_categoria = extraer_filtros_desde_q(categoria) if categoria else None
    items = []

    for bloque in bloques:
        if intencion_norm and normalizar_texto(bloque.get("intencion")) != normalizar_texto(intencion_norm):
            continue

        for categoria_data in bloque.get("categorias", []) or []:
            nombre_categoria = categoria_data.get("categoria", "")

            categoria_coincide = True
            if categorias_norm:
                categoria_coincide = normalizar_texto(nombre_categoria) in categorias_norm

            for item in categoria_data.get("items", []) or []:
                if categorias_norm and not categoria_coincide:
                    if not filtros_categoria or not item_cumple_filtros_inteligentes(item, filtros_categoria):
                        continue

                if filtros_categoria and not item_cumple_filtros_inteligentes(item, filtros_categoria):
                    continue

                items.append(item)

    return sorted(
        items,
        key=lambda x: x.get("score_editorial", 0),
        reverse=True
    )


def construir_resumen_evergreen(bloques):
    resumen = []
    total_items = 0

    for bloque in bloques:
        categorias = []

        for categoria_data in bloque.get("categorias", []) or []:
            total_categoria = int(categoria_data.get("total_items", 0) or 0)
            total_items += total_categoria

            categorias.append({
                "categoria": categoria_data.get("categoria", ""),
                "total_items": total_categoria
            })

        resumen.append({
            "intencion": bloque.get("intencion", ""),
            "total_items": int(bloque.get("total_items", 0) or 0),
            "categorias": categorias
        })

    return resumen, total_items



# -------------------------
# BÚSQUEDA EVERGREEN INTELIGENTE SIN CAMBIAR SCHEMA
# -------------------------

EVERGREEN_ALIAS_INTENCION = {
    "viajes": "viaje",
    "viaje": "viaje",
    "escapadas": "viaje",
    "excursiones": "viaje",
    "trenes": "viaje",
    "cultura": "cultura",
    "tradicion": "cultura",
    "tradición": "cultura",
    "historia": "cultura",
    "ocio": "ocio",
    "planes": "ocio",
    "naturaleza": "naturaleza",
    "parques": "naturaleza",
    "jardines": "naturaleza",
    "miradores": "naturaleza",
    "barrios": "barrios",
    "zonas": "barrios",
    "rutas": "rutas",
    "ruta": "rutas",
    "castillos": "castillos",
    "castillo": "castillos",
    "yacimientos": "yacimientos",
    "yacimiento": "yacimientos",
    "arqueologia": "yacimientos",
    "arqueología": "yacimientos",
    "ruinas": "yacimientos",
    "ruina": "yacimientos",
    "monumentos": "monumentos",
    "monumento": "monumentos",
}


EVERGREEN_ALIAS_CATEGORIA = {
    "senderismo": ["rutas_senderismo_madrid", "rutas_naturaleza_sierra_norte"],
    "rutas_senderismo": ["rutas_senderismo_madrid", "rutas_naturaleza_sierra_norte"],
    "bicicleta": ["rutas_naturaleza_sierra_norte"],
    "bici": ["rutas_naturaleza_sierra_norte"],
    "mtb": ["rutas_naturaleza_sierra_norte"],
    "cicloturismo": ["rutas_naturaleza_sierra_norte"],
    "sierra_norte": ["rutas_naturaleza_sierra_norte"],
    "sierra norte": ["rutas_naturaleza_sierra_norte"],
    "sierra_guadarrama": ["rutas_senderismo_madrid"],
    "sierra guadarrama": ["rutas_senderismo_madrid"],
    "sierra_oeste": ["rutas_senderismo_madrid"],
    "sierra oeste": ["rutas_senderismo_madrid"],
    "villas_madrid": ["rutas_naturaleza_madrid"],
    "villas de madrid": ["rutas_naturaleza_madrid"],
    "patrimonio": ["rutas_patrimonio_madrid"],
    "unesco": ["rutas_patrimonio_madrid"],
    "castilla_la_mancha": ["rutas_historicas_clm", "castillos_clm", "arqueologia_clm"],
    "castilla la mancha": ["rutas_historicas_clm", "castillos_clm", "arqueologia_clm"],
    "extremadura": ["imprescindibles_extremadura"],
    "castillos": ["castillos_clm"],
    "castillo": ["castillos_clm"],
    "toledo": ["castillos_clm", "arqueologia_clm", "rutas_historicas_clm"],
    "guadalajara": ["castillos_clm", "arqueologia_clm", "rutas_historicas_clm"],
    "cuenca": ["castillos_clm", "arqueologia_clm", "rutas_historicas_clm"],
    "ciudad_real": ["castillos_clm", "arqueologia_clm", "rutas_historicas_clm"],
    "ciudad real": ["castillos_clm", "arqueologia_clm", "rutas_historicas_clm"],
    "albacete": ["castillos_clm", "arqueologia_clm", "rutas_historicas_clm"],
    "yacimientos": ["arqueologia_clm"],
    "yacimiento": ["arqueologia_clm"],
    "arqueologia": ["arqueologia_clm"],
    "arqueología": ["arqueologia_clm"],
    "ruinas": ["arqueologia_clm"],
    "ruina": ["arqueologia_clm"],
}


def normalizar_valor_evergreen(valor):
    return normalizar_texto(valor).replace(" ", "_")


def normalizar_intencion_evergreen_alias(intencion):
    if not intencion:
        return None

    clave = normalizar_texto(intencion)
    return EVERGREEN_ALIAS_INTENCION.get(clave, normalizar_valor_evergreen(intencion))


def categoria_aliases_evergreen(categoria):
    if not categoria:
        return None

    clave_texto = normalizar_texto(categoria)
    clave_valor = clave_texto.replace(" ", "_")

    aliases = EVERGREEN_ALIAS_CATEGORIA.get(clave_texto) or EVERGREEN_ALIAS_CATEGORIA.get(clave_valor)
    if aliases:
        return {normalizar_texto(a) for a in aliases}

    return {normalizar_texto(categoria)}


def texto_evergreen_busqueda_ampliado(item):
    campos = [
        item.get("titulo"),
        item.get("descripcion"),
        item.get("fuente"),
        item.get("categoria"),
        item.get("intencion"),
        item.get("url"),
        item.get("pagina_padre"),
        item.get("tipo_contenido"),
        item.get("tipo_plan"),
        item.get("subtipo_plan"),
        item.get("zona"),
        item.get("comunidad"),
        item.get("provincia"),
        " ".join(item.get("tags", []) or []),
    ]

    return normalizar_texto(" ".join(str(c or "") for c in campos))


def extraer_filtros_desde_q(q):
    """
    Convierte búsquedas naturales del GPT en filtros internos sin tocar el schema.
    Ejemplos:
    - "rutas de senderismo en Madrid"
    - "rutas de bicicleta en la Sierra Norte"
    - "castillos en Toledo"
    - "ruinas/yacimientos en Madrid"
    """
    q_norm = normalizar_texto(q)
    filtros = {
        "tipo_plan": None,
        "subtipo_plan": None,
        "zona": None,
        "comunidad": None,
        "provincia": None,
        "tags": set(),
    }

    if any(x in q_norm for x in ["ruta", "rutas", "senderismo", "senda", "camino", "bicicleta", "bici", "mtb", "cicloturismo"]):
        filtros["tipo_plan"] = "ruta"
        filtros["tags"].add("ruta")

    if any(x in q_norm for x in ["senderismo", "senda", "camino"]):
        filtros["subtipo_plan"] = "senderismo"
        filtros["tags"].add("senderismo")

    if any(x in q_norm for x in ["bicicleta", "bici", "mtb", "cicloturismo", "gravel"]):
        filtros["subtipo_plan"] = "bicicleta"
        filtros["tags"].add("bicicleta")

    if "castillo" in q_norm or "castillos" in q_norm or "fortaleza" in q_norm:
        filtros["tipo_plan"] = "castillo"
        filtros["tags"].add("castillo")

    if any(x in q_norm for x in ["yacimiento", "yacimientos", "arqueologia", "ruina", "ruinas"]):
        filtros["tipo_plan"] = "yacimiento"
        filtros["tags"].add("yacimiento")

    if any(x in q_norm for x in ["monumento", "monumentos"]):
        filtros["tipo_plan"] = "monumento"

    if "sierra norte" in q_norm or "lozoya" in q_norm or "buitrago" in q_norm:
        filtros["zona"] = "sierra_norte"
        filtros["tags"].add("sierra-norte")

    if "guadarrama" in q_norm:
        filtros["zona"] = "sierra_guadarrama"
        filtros["tags"].add("sierra-guadarrama")

    if "sierra oeste" in q_norm:
        filtros["zona"] = "sierra_oeste"
        filtros["tags"].add("sierra-oeste")

    if "vegas" in q_norm or "alcarria" in q_norm:
        filtros["zona"] = "vegas_alcarria"
        filtros["tags"].add("vegas-alcarria")

    if "villas de madrid" in q_norm:
        filtros["zona"] = "villas_madrid"
        filtros["tags"].add("villas-madrid")

    if "castilla la mancha" in q_norm or "castillalamancha" in q_norm:
        filtros["comunidad"] = "castilla_la_mancha"
        filtros["tags"].add("castilla-la-mancha")

    if "extremadura" in q_norm:
        filtros["comunidad"] = "extremadura"
        filtros["tags"].add("extremadura")

    if "madrid" in q_norm and not filtros["comunidad"]:
        filtros["comunidad"] = "madrid"
        filtros["tags"].add("madrid")

    provincias = {
        "toledo": "toledo",
        "guadalajara": "guadalajara",
        "cuenca": "cuenca",
        "ciudad real": "ciudad_real",
        "albacete": "albacete",
        "caceres": "caceres",
        "caceres": "caceres",
        "badajoz": "badajoz",
    }

    for texto_provincia, valor in provincias.items():
        if texto_provincia in q_norm:
            filtros["provincia"] = valor
            filtros["tags"].add(valor.replace("_", "-"))

    return filtros


def item_cumple_filtros_inteligentes(item, filtros):
    if not filtros:
        return True

    def norm(v):
        return normalizar_valor_evergreen(v)

    tipo_plan = filtros.get("tipo_plan")
    if tipo_plan and norm(item.get("tipo_plan")) != norm(tipo_plan):
        return False

    subtipo_plan = filtros.get("subtipo_plan")
    if subtipo_plan and norm(item.get("subtipo_plan")) != norm(subtipo_plan):
        return False

    zona = filtros.get("zona")
    if zona and norm(item.get("zona")) != norm(zona):
        return False

    comunidad = filtros.get("comunidad")
    if comunidad and norm(item.get("comunidad")) != norm(comunidad):
        return False

    provincia = filtros.get("provincia")
    if provincia and norm(item.get("provincia")) != norm(provincia):
        return False

    tags_filtro = filtros.get("tags") or set()
    if tags_filtro:
        tags_item = {normalizar_texto(t) for t in (item.get("tags", []) or [])}
        # Los tags ayudan al ranking y afinan, pero no obligamos a que estén todos.
        # Los campos tipo/subtipo/zona/comunidad/provincia ya son los filtros duros.
        if not tags_item.intersection({normalizar_texto(t) for t in tags_filtro}):
            texto = texto_evergreen_busqueda_ampliado(item)
            if not any(normalizar_texto(t) in texto for t in tags_filtro):
                return False

    return True


def calcular_score_busqueda_evergreen(item, q=None, filtros=None):
    score = int(item.get("score_editorial", 0) or 0)
    texto = texto_evergreen_busqueda_ampliado(item)
    filtros = filtros or {}

    if q:
        for palabra in normalizar_texto(q).split():
            if len(palabra) >= 3 and palabra in texto:
                score += 3

    for campo in ["tipo_plan", "subtipo_plan", "zona", "comunidad", "provincia"]:
        valor = filtros.get(campo)
        if valor and normalizar_valor_evergreen(item.get(campo)) == normalizar_valor_evergreen(valor):
            score += 20

    tags_filtro = filtros.get("tags") or set()
    tags_item = {normalizar_texto(t) for t in (item.get("tags", []) or [])}
    for tag in tags_filtro:
        if normalizar_texto(tag) in tags_item:
            score += 8

    return score


@app.get("/", response_model=RootResponse)
def root():
    return {"ok": True, "servicio": "API Agenda Cultural"}


@app.get("/eventos", response_model=EventosResponse)
def obtener_eventos(
    sala: Optional[str] = Query(default=None),
    fecha_desde: Optional[date] = Query(default=None),
    fecha_hasta: Optional[date] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None)
):
    eventos = cargar_eventos()

    f_inicio = fecha_desde
    f_fin = fecha_hasta

    if f_inicio and not f_fin:
        f_fin = f_inicio
    if f_fin and not f_inicio:
        f_inicio = f_fin

    filtrados = filtrar_eventos(
        eventos,
        f_inicio,
        f_fin,
        sala=sala,
        tipo_evento=tipo_evento
    )

    return {
        "total": len(filtrados),
        "eventos": filtrados
    }


@app.get("/eventos/fin-de-semana", response_model=EventosRangoResponse)
def eventos_fin_de_semana(
    sala: Optional[str] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None)
):
    hoy = date.today()

    dias_hasta_viernes = (4 - hoy.weekday()) % 7
    viernes = hoy + timedelta(days=dias_hasta_viernes)
    domingo = viernes + timedelta(days=2)

    eventos = cargar_eventos()
    filtrados = filtrar_eventos(
        eventos,
        viernes,
        domingo,
        sala=sala,
        tipo_evento=tipo_evento
    )

    return {
        "desde": viernes.isoformat(),
        "hasta": domingo.isoformat(),
        "total": len(filtrados),
        "eventos": filtrados
    }


@app.get("/eventos/hoy", response_model=EventosDiaResponse)
def eventos_hoy(
    sala: Optional[str] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None)
):
    hoy = date.today()
    eventos = cargar_eventos()
    filtrados = filtrar_eventos(
        eventos,
        hoy,
        hoy,
        sala=sala,
        tipo_evento=tipo_evento
    )

    return {
        "fecha": hoy.isoformat(),
        "total": len(filtrados),
        "eventos": filtrados
    }


@app.get("/eventos/manana", response_model=EventosDiaResponse)
def eventos_manana(
    sala: Optional[str] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None)
):
    manana = date.today() + timedelta(days=1)
    eventos = cargar_eventos()
    filtrados = filtrar_eventos(
        eventos,
        manana,
        manana,
        sala=sala,
        tipo_evento=tipo_evento
    )

    return {
        "fecha": manana.isoformat(),
        "total": len(filtrados),
        "eventos": filtrados
    }


@app.get("/evergreen", response_model=EvergreenResponse)
def obtener_evergreen():
    bloques = cargar_evergreen()

    return {
        "total_bloques": len(bloques),
        "bloques": bloques
    }


@app.get("/evergreen/resumen", response_model=EvergreenResumenResponse)
def obtener_resumen_evergreen():
    bloques = cargar_evergreen()
    resumen, total_items = construir_resumen_evergreen(bloques)

    return {
        "total_bloques": len(bloques),
        "total_items": total_items,
        "bloques": resumen
    }


@app.get("/evergreen/intenciones", response_model=EvergreenIntencionesResponse)
def obtener_intenciones_evergreen():
    bloques = cargar_evergreen()
    intenciones = listar_intenciones_evergreen(bloques)

    return {
        "total": len(intenciones),
        "intenciones": intenciones
    }


@app.get("/evergreen/categorias", response_model=EvergreenCategoriasResponse)
def obtener_categorias_evergreen(
    intencion: Optional[str] = Query(default=None)
):
    bloques = cargar_evergreen()
    categorias = listar_categorias_evergreen(bloques, intencion=intencion)

    return {
        "total": len(categorias),
        "intencion": intencion,
        "categorias": categorias
    }


@app.get("/evergreen/buscar", response_model=EvergreenSearchResponse)
def buscar_evergreen(
    q: Optional[str] = Query(default=None),
    intencion: Optional[str] = Query(default=None),
    categoria: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0)
):
    bloques = cargar_evergreen()

    items = extraer_todos_items_evergreen(
        bloques,
        intencion=intencion,
        categoria=categoria
    )

    filtros_q = extraer_filtros_desde_q(q) if q else None

    if filtros_q:
        items = [
            item for item in items
            if item_cumple_filtros_inteligentes(item, filtros_q)
        ]

    if q:
        q_norm = normalizar_texto(q)
        palabras_q = [p for p in q_norm.split() if len(p) >= 3]

        # Búsqueda flexible: si hay filtros inteligentes, no obligamos a que
        # la frase completa aparezca literal. Si no hay filtros, usamos texto libre.
        if not filtros_q or not any(filtros_q.get(k) for k in ["tipo_plan", "subtipo_plan", "zona", "comunidad", "provincia"]):
            items = [
                item for item in items
                if q_norm in texto_evergreen_busqueda(item)
                or all(p in texto_evergreen_busqueda(item) for p in palabras_q)
            ]

    if q or filtros_q:
        items = sorted(
            items,
            key=lambda item: calcular_score_busqueda_evergreen(item, q=q, filtros=filtros_q),
            reverse=True
        )

    pagina, limit, offset = paginar_items(
        items,
        limit=limit,
        offset=offset,
        max_limit=50
    )

    return {
        "q": q,
        "intencion": intencion,
        "categoria": categoria,
        "total": len(items),
        "total_devuelto": len(pagina),
        "limit": limit,
        "offset": offset,
        "items": pagina
    }


@app.get("/evergreen/random", response_model=EvergreenRandomResponse)
def obtener_evergreen_random(
    intencion: Optional[str] = Query(default=None),
    categoria: Optional[str] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20)
):
    import random

    bloques = cargar_evergreen()
    items = extraer_todos_items_evergreen(
        bloques,
        intencion=intencion,
        categoria=categoria
    )

    seleccion = random.sample(items, min(limit, len(items))) if items else []

    return {
        "intencion": intencion,
        "categoria": categoria,
        "total_disponibles": len(items),
        "total_devuelto": len(seleccion),
        "items": seleccion
    }


@app.get("/evergreen/{intencion}/top", response_model=Union[EvergreenTopResponse, ErrorResponse])
def obtener_top_evergreen_por_intencion(
    intencion: str,
    limit: int = 5,
    categoria: Optional[str] = None
):
    bloques = cargar_evergreen()
    intencion_busqueda = normalizar_intencion_evergreen_alias(intencion) or intencion
    bloque = buscar_bloque_evergreen(bloques, intencion_busqueda)

    if not bloque:
        return {
            "error": "Intención no encontrada",
            "intenciones_disponibles": [
                b.get("intencion") for b in bloques
            ]
        }

    if limit < 1:
        limit = 1

    if limit > 50:
        limit = 50

    items_ordenados = extraer_items_evergreen(bloque, categoria=categoria)

    return {
        "intencion": bloque.get("intencion"),
        "categoria": categoria,
        "limit": limit,
        "total_disponibles": len(items_ordenados),
        "total_devuelto": len(items_ordenados[:limit]),
        "items": items_ordenados[:limit]
    }


@app.get("/evergreen/{intencion}", response_model=Union[EvergreenBloque, ErrorResponse])
def obtener_evergreen_por_intencion(intencion: str):
    bloques = cargar_evergreen()
    intencion_busqueda = normalizar_intencion_evergreen_alias(intencion) or intencion
    bloque = buscar_bloque_evergreen(bloques, intencion_busqueda)

    if not bloque:
        return {
            "error": "Intención no encontrada",
            "intenciones_disponibles": [
                b.get("intencion") for b in bloques
            ]
        }

    return bloque