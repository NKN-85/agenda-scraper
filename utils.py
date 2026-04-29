from datetime import date, datetime
import re
import requests
import time
import random

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# -------------------------
# HTTP ROBUSTO
# -------------------------

def get_url(url, headers=None, timeout=15, intentos=3, session=None, pausa_min=0.8, pausa_max=2.0):
    headers = headers or HEADERS
    ultimo_error = None

    for intento in range(intentos):
        try:
            time.sleep(random.uniform(pausa_min, pausa_max))

            cliente = session or requests
            response = cliente.get(
                url,
                headers=headers,
                timeout=timeout,
                verify=False
            )

            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            ultimo_error = e
            print(f"[HTTP] intento {intento + 1} fallido: {e}")

            if intento < intentos - 1:
                time.sleep(random.uniform(1.5, 3.0))

    raise ultimo_error


# -------------------------
# TEXTO
# -------------------------

def limpiar_texto(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto.strip())


# -------------------------
# FECHAS GENERALES
# -------------------------

def fecha_a_str(fecha):
    if not fecha:
        return ""
    if isinstance(fecha, str):
        try:
            y, m, d = fecha.split("-")
            return f"{d.zfill(2)}/{m.zfill(2)}/{y}"
        except Exception:
            return fecha
    return fecha.strftime("%d/%m/%Y")


def fecha_a_iso(fecha):
    if not fecha:
        return None
    if isinstance(fecha, str):
        # acepta ya ISO o dd/mm/yyyy
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            return fecha
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", fecha):
            d, m, y = fecha.split("/")
            return f"{y}-{m}-{d}"
        return None
    return fecha.isoformat()


def parse_fecha_iso(fecha_str):
    if not fecha_str:
        return None
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except Exception:
        return None


def es_futura_o_hoy(fecha):
    if not fecha:
        return False
    return fecha >= date.today()


# -------------------------
# CLAVE / DEDUPLICADO
# -------------------------

def clave_evento(titulo, lugar, url_evento):
    return (
        limpiar_texto(titulo).lower(),
        limpiar_texto(lugar).lower(),
        limpiar_texto(url_evento).strip().lower()
    )


# -------------------------
# CONVERSIÓN DE MESES
# -------------------------

def mes_es_a_numero(mes_txt):
    if not mes_txt:
        return None

    meses = {
        "ene": 1, "enero": 1,
        "feb": 2, "febrero": 2,
        "mar": 3, "marzo": 3,
        "abr": 4, "abril": 4,
        "may": 5, "mayo": 5,
        "jun": 6, "junio": 6,
        "jul": 7, "julio": 7,
        "ago": 8, "agosto": 8,
        "sep": 9, "septiembre": 9, "set": 9, "setiembre": 9,
        "oct": 10, "octubre": 10,
        "nov": 11, "noviembre": 11,
        "dic": 12, "diciembre": 12,
    }

    return meses.get(mes_txt.lower())


# -------------------------
# CONSTRUCTORES DE FECHA
# -------------------------

def construir_fecha(dia, mes_txt, anio=None):
    try:
        mes = mes_es_a_numero(mes_txt)
        if not mes:
            return None

        if not anio:
            anio = date.today().year

        return date(int(anio), mes, int(dia))
    except Exception:
        return None


def construir_fecha_actual(dia, mes_txt):
    try:
        hoy = date.today()
        mes = mes_es_a_numero(mes_txt)

        if not mes:
            return None

        anio = hoy.year

        if mes < hoy.month - 1:
            anio += 1

        return date(anio, mes, int(dia))
    except Exception:
        return None


# -------------------------
# PARSERS ESPECÍFICOS (LOS QUE YA TENÍAS)
# -------------------------

def convertir_fecha_eslava(fecha_texto):
    return datetime.strptime(fecha_texto, "%d.%m.%Y").date()


def convertir_fecha_but(fecha_texto):
    meses = {
        "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "mayo": 5,
        "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    }

    fecha_texto = fecha_texto.strip().lower()

    if "-" in fecha_texto:
        partes = fecha_texto.split("-")
        if len(partes) == 3:
            dia = int(partes[0])
            mes = meses.get(partes[1][:3])
            anio = 2000 + int(partes[2])
            if mes:
                return date(anio, mes, dia)

    partes = fecha_texto.split()
    if len(partes) == 3:
        dia = int(partes[0])
        mes_txt = partes[1]
        mes = meses.get(mes_txt) or meses.get(mes_txt[:3])
        anio = int(partes[2])
        if mes:
            return date(anio, mes, dia)

    return None


def convertir_fecha_elsol(fecha_texto):
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
    }

    fecha_texto = fecha_texto.strip().lower()
    partes = fecha_texto.split()

    if len(partes) == 3:
        _, dia, mes_txt = partes
        mes = meses.get(mes_txt)
        if mes:
            return date(date.today().year, mes, int(dia))

    return None


def convertir_fecha_vistalegre(fecha_texto):
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        "ene": 1, "feb": 2, "mar": 3, "abr": 4,
        "may": 5, "jun": 6, "jul": 7, "ago": 8,
        "sep": 9, "oct": 10, "nov": 11, "dic": 12
    }

    fecha_texto = fecha_texto.strip().lower()

    partes = fecha_texto.split("-")[0].strip().split()
    if len(partes) >= 2:
        try:
            dia = int(partes[0])
            mes = meses.get(partes[1])
            if mes:
                hoy = date.today()
                anio = hoy.year
                if mes < hoy.month - 1:
                    anio += 1
                return date(anio, mes, dia)
        except Exception:
            pass

    if "-" in fecha_texto:
        partes = fecha_texto.split("-")
        if len(partes) == 2:
            try:
                dia = int(partes[0])
                mes = meses.get(partes[1])
                if mes:
                    hoy = date.today()
                    anio = hoy.year
                    if mes < hoy.month - 1:
                        anio += 1
                    return date(anio, mes, dia)
            except Exception:
                pass

    return None


# -------------------------
# NORMALIZACIÓN DE FECHAS ENRIQUECIDAS
# -------------------------

def _normalizar_dias_semana(dias_semana):
    if not dias_semana:
        return []

    resultado = []
    for d in dias_semana:
        if isinstance(d, int) and 0 <= d <= 6:
            resultado.append(d)

    return sorted(set(resultado))


def _iso_min_no_pasada(fechas_iso):
    """
    Devuelve la primera fecha >= hoy.
    Si todas están en el pasado, devuelve la primera igualmente.
    """
    if not fechas_iso:
        return None

    hoy = date.today()
    fechas_date = []

    for f in fechas_iso:
        fd = parse_fecha_iso(f)
        if fd:
            fechas_date.append(fd)

    if not fechas_date:
        return fechas_iso[0]

    futuras = sorted([f for f in fechas_date if f >= hoy])
    if futuras:
        return futuras[0].isoformat()

    return min(fechas_date).isoformat()


def normalizar_info_fecha(info_fecha=None, fecha_evento=None):
    """
    Estandariza cualquier formato interno a este contrato:

    {
        "tipo_fecha": "unica|lista|rango|hasta|desde|patron",
        "fecha": "YYYY-MM-DD",
        "rango_fechas": bool,
        "fecha_inicio": "YYYY-MM-DD"|None,
        "fecha_fin": "YYYY-MM-DD"|None,
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": ""
    }
    """
    if not info_fecha and fecha_evento:
        iso = fecha_a_iso(fecha_evento)
        if not iso:
            return None

        return {
            "tipo_fecha": "unica",
            "fecha": iso,
            "rango_fechas": False,
            "fecha_inicio": iso,
            "fecha_fin": iso,
            "fechas_funcion": [iso],
            "dias_semana": [],
            "texto_fecha_original": ""
        }

    if not info_fecha:
        return None

    tipo = (info_fecha.get("tipo_fecha") or info_fecha.get("tipo") or "").strip().lower()
    texto_original = limpiar_texto(info_fecha.get("texto_fecha_original", ""))

    # 1) FECHA ÚNICA
    if tipo in {"unica", "simple"}:
        f = info_fecha.get("fecha") or fecha_evento
        iso = fecha_a_iso(f)
        if not iso:
            return None

        return {
            "tipo_fecha": "unica",
            "fecha": iso,
            "rango_fechas": False,
            "fecha_inicio": iso,
            "fecha_fin": iso,
            "fechas_funcion": [iso],
            "dias_semana": [],
            "texto_fecha_original": texto_original
        }

    # 2) LISTA DE FECHAS
    if tipo == "lista":
        fechas_raw = info_fecha.get("fechas") or info_fecha.get("fechas_funcion") or []
        fechas_iso = [fecha_a_iso(f) for f in fechas_raw if fecha_a_iso(f)]
        fechas_iso = sorted(set(fechas_iso))

        if not fechas_iso:
            return None

        fecha_repr = _iso_min_no_pasada(fechas_iso)

        return {
            "tipo_fecha": "lista",
            "fecha": fecha_repr,
            "rango_fechas": False,
            "fecha_inicio": fechas_iso[0],
            "fecha_fin": fechas_iso[-1],
            "fechas_funcion": fechas_iso,
            "dias_semana": [],
            "texto_fecha_original": texto_original
        }

    # 3) RANGO NORMAL
    if tipo == "rango":
        inicio = fecha_a_iso(info_fecha.get("fecha_inicio"))
        fin = fecha_a_iso(info_fecha.get("fecha_fin"))

        if not inicio and not fin:
            return None

        return {
            "tipo_fecha": "rango",
            "fecha": inicio or fin,
            "rango_fechas": True,
            "fecha_inicio": inicio,
            "fecha_fin": fin,
            "fechas_funcion": [],
            "dias_semana": [],
            "texto_fecha_original": texto_original
        }

    # 4) HASTA
    if tipo in {"hasta", "rango_abierto"}:
        inicio = fecha_a_iso(info_fecha.get("fecha_inicio"))
        fin = fecha_a_iso(info_fecha.get("fecha_fin")) or fecha_a_iso(info_fecha.get("fecha"))

        if not fin and not inicio:
            return None

        return {
            "tipo_fecha": "hasta",
            "fecha": inicio or fin,
            "rango_fechas": True,
            "fecha_inicio": inicio,
            "fecha_fin": fin,
            "fechas_funcion": [],
            "dias_semana": [],
            "texto_fecha_original": texto_original
        }

    # 5) DESDE
    if tipo == "desde":
        inicio = fecha_a_iso(info_fecha.get("fecha_inicio")) or fecha_a_iso(info_fecha.get("fecha"))

        if not inicio:
            return None

        return {
            "tipo_fecha": "desde",
            "fecha": inicio,
            "rango_fechas": True,
            "fecha_inicio": inicio,
            "fecha_fin": None,
            "fechas_funcion": [],
            "dias_semana": [],
            "texto_fecha_original": texto_original
        }

    # 6) PATRÓN SEMANAL
    if tipo == "patron":
        inicio = fecha_a_iso(info_fecha.get("fecha_inicio"))
        fin = fecha_a_iso(info_fecha.get("fecha_fin"))
        dias_semana = _normalizar_dias_semana(info_fecha.get("dias_semana", []))

        if not fin and not inicio:
            return None

        return {
            "tipo_fecha": "patron",
            "fecha": inicio or fin,
            "rango_fechas": True,
            "fecha_inicio": inicio,
            "fecha_fin": fin,
            "fechas_funcion": [],
            "dias_semana": dias_semana,
            "texto_fecha_original": texto_original
        }

    # 7) FALLBACK PARA ESTRUCTURAS YA SEMIRICAS
    fechas_funcion = [fecha_a_iso(f) for f in (info_fecha.get("fechas_funcion") or []) if fecha_a_iso(f)]
    fechas_funcion = sorted(set(fechas_funcion))
    inicio = fecha_a_iso(info_fecha.get("fecha_inicio"))
    fin = fecha_a_iso(info_fecha.get("fecha_fin"))
    dias_semana = _normalizar_dias_semana(info_fecha.get("dias_semana", []))
    rango_fechas = bool(info_fecha.get("rango_fechas"))

    if dias_semana and (inicio or fin):
        return {
            "tipo_fecha": "patron",
            "fecha": inicio or fin,
            "rango_fechas": True,
            "fecha_inicio": inicio,
            "fecha_fin": fin,
            "fechas_funcion": [],
            "dias_semana": dias_semana,
            "texto_fecha_original": texto_original
        }

    if fechas_funcion:
        fecha_repr = _iso_min_no_pasada(fechas_funcion)
        return {
            "tipo_fecha": "lista",
            "fecha": fecha_repr,
            "rango_fechas": False,
            "fecha_inicio": inicio or fechas_funcion[0],
            "fecha_fin": fin or fechas_funcion[-1],
            "fechas_funcion": fechas_funcion,
            "dias_semana": [],
            "texto_fecha_original": texto_original
        }

    if rango_fechas or inicio or fin:
        return {
            "tipo_fecha": "rango",
            "fecha": fecha_a_iso(info_fecha.get("fecha")) or inicio or fin,
            "rango_fechas": True,
            "fecha_inicio": inicio,
            "fecha_fin": fin,
            "fechas_funcion": [],
            "dias_semana": [],
            "texto_fecha_original": texto_original
        }

    fecha_simple = fecha_a_iso(info_fecha.get("fecha")) or fecha_a_iso(fecha_evento)
    if fecha_simple:
        return {
            "tipo_fecha": "unica",
            "fecha": fecha_simple,
            "rango_fechas": False,
            "fecha_inicio": fecha_simple,
            "fecha_fin": fecha_simple,
            "fechas_funcion": [fecha_simple],
            "dias_semana": [],
            "texto_fecha_original": texto_original
        }

    return None


# -------------------------
# FILTRO CONSERVADOR DE VIGENCIA
# -------------------------

def _datos_fecha_siguen_vigentes(datos_fecha):
    """
    Filtro conservador para no romper scrapers existentes.

    SOLO descarta cuando está claro que el evento ya terminó.
    Si faltan datos o son ambiguos, mantiene el evento.
    """
    if not datos_fecha:
        return False

    hoy = date.today()
    tipo = (datos_fecha.get("tipo_fecha") or "").strip().lower()

    # 1) Fecha única
    if tipo == "unica":
        fecha = parse_fecha_iso(datos_fecha.get("fecha"))
        if not fecha:
            return True
        return fecha >= hoy

    # 2) Lista de fechas
    if tipo == "lista":
        fechas = [
            parse_fecha_iso(f)
            for f in (datos_fecha.get("fechas_funcion") or [])
        ]
        fechas = [f for f in fechas if f]

        if not fechas:
            return True

        return any(f >= hoy for f in fechas)

    # 3) Rango / hasta / patrón
    if tipo in {"rango", "hasta", "patron"}:
        fecha_fin = parse_fecha_iso(datos_fecha.get("fecha_fin"))

        # si no tenemos fin, no arriesgamos
        if not fecha_fin:
            return True

        return fecha_fin >= hoy

    # 4) Desde
    if tipo == "desde":
        return True

    # 5) Fallback conservador
    fecha_fin = parse_fecha_iso(datos_fecha.get("fecha_fin"))
    if fecha_fin:
        return fecha_fin >= hoy

    fecha = parse_fecha_iso(datos_fecha.get("fecha"))
    if fecha:
        return fecha >= hoy

    return True


# -------------------------
# AGREGAR EVENTO ENRIQUECIDO
# -------------------------

def agregar_evento(eventos, vistos, titulo, fecha_evento, lugar, url_evento, fuente, info_fecha=None):
    if not titulo or not lugar or not url_evento:
        return False

    clave = clave_evento(titulo, lugar, url_evento)
    if clave in vistos:
        return False

    datos_fecha = normalizar_info_fecha(info_fecha=info_fecha, fecha_evento=fecha_evento)
    if not datos_fecha:
        return False

    if not datos_fecha.get("fecha") and not datos_fecha.get("fecha_fin"):
        return False

    # filtro defensivo global: evita históricos ya terminados
    if not _datos_fecha_siguen_vigentes(datos_fecha):
        return False

    vistos.add(clave)

    eventos.append({
        "titulo": limpiar_texto(titulo),
        "fecha": datos_fecha.get("fecha"),
        "lugar": limpiar_texto(lugar),
        "url_evento": limpiar_texto(url_evento),
        "fuente": limpiar_texto(fuente),
        "tipo_fecha": datos_fecha.get("tipo_fecha"),
        "rango_fechas": datos_fecha.get("rango_fechas", False),
        "fecha_inicio": datos_fecha.get("fecha_inicio"),
        "fecha_fin": datos_fecha.get("fecha_fin"),
        "fechas_funcion": datos_fecha.get("fechas_funcion", []),
        "dias_semana": datos_fecha.get("dias_semana", []),
        "texto_fecha_original": datos_fecha.get("texto_fecha_original", ""),
    })

    return True