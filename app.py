from fastapi import FastAPI
import json
from datetime import date, timedelta

app = FastAPI(
    title="API Agenda Cultural",
    description="API local para consultar eventos de agenda cultural",
    version="1.0.0"
)


def cargar_eventos():
    with open("eventos.json", encoding="utf-8") as f:
        return json.load(f)


def coincide_sala(evento, sala):
    if not sala:
        return True

    sala_txt = sala.strip().lower()
    lugar = evento.get("lugar", "").lower()
    fuente = evento.get("fuente", "").lower()

    return sala_txt in lugar or sala_txt in fuente


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
    sala: str = None
):
    eventos = cargar_eventos()
    resultado = []

    for evento in eventos:
        fecha = evento.get("fecha", "")

        if fecha_desde and fecha < fecha_desde:
            continue

        if fecha_hasta and fecha > fecha_hasta:
            continue

        if not coincide_sala(evento, sala):
            continue

        resultado.append(evento)

    return {
        "total": len(resultado),
        "filtros": {
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "sala": sala
        },
        "eventos": resultado
    }


@app.get("/eventos/fin-de-semana")
def obtener_eventos_fin_de_semana(sala: str = None):
    hoy = date.today()

    # sábado = 5, domingo = 6
    dias_hasta_sabado = (5 - hoy.weekday()) % 7
    sabado = hoy + timedelta(days=dias_hasta_sabado)
    domingo = sabado + timedelta(days=1)

    fecha_desde = sabado.isoformat()
    fecha_hasta = domingo.isoformat()

    eventos = cargar_eventos()
    resultado = []

    for evento in eventos:
        fecha = evento.get("fecha", "")

        if fecha < fecha_desde or fecha > fecha_hasta:
            continue

        if not coincide_sala(evento, sala):
            continue

        resultado.append(evento)

    return {
        "total": len(resultado),
        "filtros": {
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "sala": sala
        },
        "eventos": resultado
    }