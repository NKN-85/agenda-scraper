from fastapi import FastAPI, Response
import json
import unicodedata
from datetime import date, timedelta, datetime

app = FastAPI(
    title="API Agenda Cultural",
    description="API local para consultar eventos de agenda cultural",
    version="2.0.0"
)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


def cargar_eventos():
    with open("eventos_master.json", encoding="utf-8") as f:
        return json.load(f)


def normalizar_texto(texto):
    if not texto:
        return ""

    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


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

    # 1) patrón semanal
    if dias_semana:
        return expandir_patron_en_rango(evento, fecha_inicio, fecha_fin)

    # 2) lista de fechas
    if fechas:
        for f in fechas:
            fecha = parse_fecha_iso(f)
            if fecha and fecha_inicio <= fecha <= fecha_fin:
                return True
        return False

    # 3) rango
    if tipo_fecha == "rango":
        return bool(inicio and fin and not (fin < fecha_inicio or inicio > fecha_fin))

    # 4) hasta
    if tipo_fecha == "hasta":
        return bool(fin and fin >= fecha_inicio)

    # 5) desde
    if tipo_fecha == "desde":
        return bool(inicio and inicio <= fecha_fin)

    # 6) fecha única
    if fecha_simple:
        return fecha_inicio <= fecha_simple <= fecha_fin

    # 7) fallback estructural por si faltó tipo_fecha
    if inicio and fin:
        return not (fin < fecha_inicio or inicio > fecha_fin)

    if fin and not inicio:
        return fin >= fecha_inicio

    if inicio and not fin:
        return inicio <= fecha_fin

    return False


def obtener_nombre_sala_canonico(sala_usuario):
    s = normalizar_texto(sala_usuario)

    alias = {
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
        "auditorio nacional": "auditorio nacional",
        "auditorio nacional de musica": "auditorio nacional",
        "auditorionacional": "auditorio nacional",

        "aranjuez": "teatro real carlos iii de aranjuez",
        "teatro aranjuez": "teatro real carlos iii de aranjuez",

        "matadero": "matadero madrid",
        "matadero madrid": "matadero madrid",

        "vistalegre": "palacio vistalegre",
        "palacio vistalegre": "palacio vistalegre",
        "vistalegre arena": "palacio vistalegre",
    }

    return alias.get(s)


def coincide_sala(evento, sala):
    if not sala:
        return True

    sala_norm = normalizar_texto(sala)
    lugar_norm = normalizar_texto(evento.get("lugar", ""))
    fuente_norm = normalizar_texto(evento.get("fuente", ""))
    url_norm = normalizar_texto(evento.get("url_evento", ""))

    sala_canonica = obtener_nombre_sala_canonico(sala)

    if sala_canonica:
        if sala_canonica in lugar_norm:
            return True
        if sala_canonica in fuente_norm:
            return True
        if sala_canonica in url_norm:
            return True

        variantes = {
            "movistar arena": [
                "movistar arena",
                "movistararena",
                "wizink center",
                "wi zink",
            ],
            "auditorio nacional": [
                "auditorio nacional",
                "auditorio nacional de musica",
                "auditorionacional",
                "inaem",
                "sala sinfonica",
                "sala de camara",
                "sala satelite",
            ],
            "palacio vistalegre": [
                "palacio vistalegre",
                "vistalegre",
            ],
            "sala la riviera": [
                "sala la riviera",
                "la riviera",
                "riviera",
            ],
            "sala el sol": [
                "sala el sol",
                "el sol",
                "salaelsol",
            ],
            "pequeno teatro gran via": [
                "pequeno teatro gran via",
                "pequeno gran via",
                "pequeño teatro gran via",
                "pequeño gran via",
                "pequenogranvia",
            ],
        }

        for variante in variantes.get(sala_canonica, []):
            variante_norm = normalizar_texto(variante)
            if variante_norm in lugar_norm or variante_norm in fuente_norm or variante_norm in url_norm:
                return True

        return False

    return sala_norm in lugar_norm or sala_norm in fuente_norm or sala_norm in url_norm


def filtrar_eventos(eventos, fecha_inicio=None, fecha_fin=None, sala=None):
    resultado = []

    for evento in eventos:
        if not coincide_sala(evento, sala):
            continue

        if fecha_inicio and fecha_fin:
            if not coincide_fechas(evento, fecha_inicio, fecha_fin):
                continue

        resultado.append(evento)

    return resultado


@app.get("/eventos")
def obtener_eventos(
    sala: str = None,
    fecha_desde: str = None,
    fecha_hasta: str = None
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


@app.get("/eventos/fin-de-semana")
def eventos_fin_de_semana(sala: str = None):
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


@app.get("/eventos/hoy")
def eventos_hoy(sala: str = None):
    hoy = date.today()
    eventos = cargar_eventos()
    filtrados = filtrar_eventos(eventos, hoy, hoy, sala=sala)

    return {
        "fecha": hoy.isoformat(),
        "total": len(filtrados),
        "eventos": filtrados
    }


@app.get("/eventos/manana")
def eventos_manana(sala: str = None):
    manana = date.today() + timedelta(days=1)
    eventos = cargar_eventos()
    filtrados = filtrar_eventos(eventos, manana, manana, sala=sala)

    return {
        "fecha": manana.isoformat(),
        "total": len(filtrados),
        "eventos": filtrados
    }