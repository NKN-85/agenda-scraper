from fastapi import FastAPI, Response
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
    version="2.4.0",
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
    "condeduque madrid": ["condeduque madrid", "condeduque", "contemporanea condeduque"],
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


def filtrar_eventos(eventos, fecha_inicio=None, fecha_fin=None, sala=None, solo_activos=True):
    resultado = []

    for evento in eventos:
        if solo_activos and evento.get("estado") not in {"activo", "nuevo"}:
            continue

        if not coincide_sala(evento, sala):
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

    categoria_norm = normalizar_texto(categoria) if categoria else None
    items = []

    for categoria_data in bloque.get("categorias", []) or []:
        nombre_categoria = categoria_data.get("categoria", "")

        if categoria_norm and normalizar_texto(nombre_categoria) != categoria_norm:
            continue

        for item in categoria_data.get("items", []) or []:
            items.append(item)

    return sorted(
        items,
        key=lambda x: x.get("score_editorial", 0),
        reverse=True
    )


@app.get("/", response_model=RootResponse)
def root():
    return {"ok": True, "servicio": "API Agenda Cultural"}


@app.get("/eventos", response_model=EventosResponse)
def obtener_eventos(
    sala: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None
):
    eventos = cargar_eventos()

    f_inicio = parse_fecha_iso(fecha_desde) if fecha_desde else None
    f_fin = parse_fecha_iso(fecha_hasta) if fecha_hasta else None

    if f_inicio and not f_fin:
        f_fin = f_inicio
    if f_fin and not f_inicio:
        f_inicio = f_fin

    filtrados = filtrar_eventos(eventos, f_inicio, f_fin, sala=sala)

    return {
        "total": len(filtrados),
        "eventos": filtrados
    }


@app.get("/eventos/fin-de-semana", response_model=EventosRangoResponse)
def eventos_fin_de_semana(sala: Optional[str] = None):
    hoy = date.today()

    dias_hasta_viernes = (4 - hoy.weekday()) % 7
    viernes = hoy + timedelta(days=dias_hasta_viernes)
    domingo = viernes + timedelta(days=2)

    eventos = cargar_eventos()
    filtrados = filtrar_eventos(eventos, viernes, domingo, sala=sala)

    return {
        "desde": viernes.isoformat(),
        "hasta": domingo.isoformat(),
        "total": len(filtrados),
        "eventos": filtrados
    }


@app.get("/eventos/hoy", response_model=EventosDiaResponse)
def eventos_hoy(sala: Optional[str] = None):
    hoy = date.today()
    eventos = cargar_eventos()
    filtrados = filtrar_eventos(eventos, hoy, hoy, sala=sala)

    return {
        "fecha": hoy.isoformat(),
        "total": len(filtrados),
        "eventos": filtrados
    }


@app.get("/eventos/manana", response_model=EventosDiaResponse)
def eventos_manana(sala: Optional[str] = None):
    manana = date.today() + timedelta(days=1)
    eventos = cargar_eventos()
    filtrados = filtrar_eventos(eventos, manana, manana, sala=sala)

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


@app.get("/evergreen/{intencion}/top", response_model=Union[EvergreenTopResponse, ErrorResponse])
def obtener_top_evergreen_por_intencion(
    intencion: str,
    limit: int = 5,
    categoria: Optional[str] = None
):
    bloques = cargar_evergreen()
    bloque = buscar_bloque_evergreen(bloques, intencion)

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
    bloque = buscar_bloque_evergreen(bloques, intencion)

    if not bloque:
        return {
            "error": "Intención no encontrada",
            "intenciones_disponibles": [
                b.get("intencion") for b in bloques
            ]
        }

    return bloque