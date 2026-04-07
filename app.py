from fastapi import FastAPI
import json
from datetime import date, timedelta, datetime

app = FastAPI(
    title="API Agenda Cultural",
    description="API local para consultar eventos de agenda cultural",
    version="1.5.0"
)


def cargar_eventos():
    with open("eventos_master.json", encoding="utf-8") as f:
        return json.load(f)


def parse_fecha(fecha_str):
    if not fecha_str:
        return None
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except Exception:
        return None


def coincide_sala(evento, sala):
    if not sala:
        return True

    sala_txt = sala.strip().lower()
    lugar = evento.get("lugar", "").lower()
    fuente = evento.get("fuente", "").lower()

    return sala_txt in lugar or sala_txt in fuente


def coincide_tag(evento, tag):
    if not tag:
        return True

    tag_txt = tag.strip().lower()
    tags = evento.get("tags", [])

    return any(tag_txt == t.lower() for t in tags)


def coincide_busqueda(evento, q):
    if not q:
        return True

    palabras = [p.strip().lower() for p in q.split() if p.strip()]
    if not palabras:
        return True

    texto = " ".join([
        evento.get("titulo", ""),
        evento.get("lugar", ""),
        evento.get("tipo_evento", ""),
        " ".join(evento.get("tags", []))
    ]).lower()

    return all(p in texto for p in palabras)


def coincide_fechas(evento, fecha_desde=None, fecha_hasta=None):
    if not fecha_desde and not fecha_hasta:
        return True

    fd = parse_fecha(fecha_desde) if fecha_desde else None
    fh = parse_fecha(fecha_hasta) if fecha_hasta else None

    # Caso 1: lista explícita de fechas
    fechas_funcion = evento.get("fechas_funcion", [])
    if fechas_funcion:
        fechas = [parse_fecha(f) for f in fechas_funcion]
        fechas = [f for f in fechas if f]

        for f in fechas:
            if fd and f < fd:
                continue
            if fh and f > fh:
                continue
            return True
        return False

    # Caso 2: rango
    if evento.get("rango_fechas"):
        inicio = parse_fecha(evento.get("fecha_inicio"))
        fin = parse_fecha(evento.get("fecha_fin"))

        if not inicio or not fin:
            return False

        # solape entre [inicio, fin] y [fd, fh]
        if fd and fin < fd:
            return False
        if fh and inicio > fh:
            return False
        return True

    # Caso 3: fecha simple
    f = parse_fecha(evento.get("fecha"))
    if not f:
        return False

    if fd and f < fd:
        return False
    if fh and f > fh:
        return False

    return True


@app.get("/")
def home():
    return {
        "mensaje": "API agenda funcionando",
        "endpoints": [
            "/eventos",
            "/eventos/fin-de-semana"
        ]
    }


@app.get("/eventos")
def obtener_eventos(
    fecha_desde: str = None,
    fecha_hasta: str = None,
    sala: str = None,
    tipo_evento: str = None,
    tag: str = None,
    estado: str = None,
    q: str = None
):
    eventos = cargar_eventos()
    resultado = []

    for evento in eventos:
        if not coincide_fechas(evento, fecha_desde, fecha_hasta):
            continue

        if not coincide_sala(evento, sala):
            continue

        if tipo_evento and evento.get("tipo_evento", "").lower() != tipo_evento.lower():
            continue

        if not coincide_tag(evento, tag):
            continue

        if not coincide_busqueda(evento, q):
            continue

        if estado and evento.get("estado", "").lower() != estado.lower():
            continue

        resultado.append(evento)

    return {
        "total": len(resultado),
        "filtros": {
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "sala": sala,
            "tipo_evento": tipo_evento,
            "tag": tag,
            "estado": estado,
            "q": q
        },
        "eventos": resultado
    }


@app.get("/eventos/fin-de-semana")
def obtener_eventos_fin_de_semana(
    sala: str = None,
    tipo_evento: str = None,
    tag: str = None,
    estado: str = None,
    q: str = None
):
    hoy = date.today()

    # viernes + sábado + domingo
    dias_hasta_viernes = (4 - hoy.weekday()) % 7
    viernes = hoy + timedelta(days=dias_hasta_viernes)
    domingo = viernes + timedelta(days=2)

    fecha_desde = viernes.isoformat()
    fecha_hasta = domingo.isoformat()

    eventos = cargar_eventos()
    resultado = []

    for evento in eventos:
        if not coincide_fechas(evento, fecha_desde, fecha_hasta):
            continue

        if not coincide_sala(evento, sala):
            continue

        if tipo_evento and evento.get("tipo_evento", "").lower() != tipo_evento.lower():
            continue

        if not coincide_tag(evento, tag):
            continue

        if not coincide_busqueda(evento, q):
            continue

        if estado and evento.get("estado", "").lower() != estado.lower():
            continue

        resultado.append(evento)

    return {
        "total": len(resultado),
        "filtros": {
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "sala": sala,
            "tipo_evento": tipo_evento,
            "tag": tag,
            "estado": estado,
            "q": q
        },
        "eventos": resultado
    }