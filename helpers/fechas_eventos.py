from datetime import date


PRIORIDAD_TIPO_FECHA = {
    "lista": 6,
    "patron": 5,
    "rango": 4,
    "hasta": 3,
    "desde": 2,
    "unica": 1,
}


def info_unica(fecha, texto_original=None):
    if not fecha:
        return None

    return {
        "tipo": "unica",
        "fecha": fecha,
        "fecha_inicio": fecha,
        "fecha_fin": fecha,
        "fechas_funcion": [fecha],
        "dias_semana": [],
        "texto_fecha_original": texto_original,
    }


def info_lista(fechas, texto_original=None):
    fechas = sorted([f for f in (fechas or []) if f])
    if not fechas:
        return None

    return {
        "tipo": "lista",
        "fecha": fechas[0],
        "fecha_inicio": fechas[0],
        "fecha_fin": fechas[-1],
        "fechas_funcion": fechas,
        "dias_semana": [],
        "texto_fecha_original": texto_original,
    }


def info_rango(fecha_inicio, fecha_fin, texto_original=None):
    if not fecha_inicio or not fecha_fin:
        return None

    return {
        "tipo": "rango",
        "fecha": fecha_inicio,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": texto_original,
    }


def info_hasta(fecha_fin, texto_original=None):
    if not fecha_fin:
        return None

    return {
        "tipo": "hasta",
        "fecha": fecha_fin,
        "fecha_inicio": None,
        "fecha_fin": fecha_fin,
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": texto_original,
    }


def info_desde(fecha_inicio, texto_original=None):
    if not fecha_inicio:
        return None

    return {
        "tipo": "desde",
        "fecha": fecha_inicio,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": None,
        "fechas_funcion": [],
        "dias_semana": [],
        "texto_fecha_original": texto_original,
    }


def info_patron(dias_semana, fecha_inicio=None, fecha_fin=None, texto_original=None):
    dias = sorted(set(dias_semana or []))
    if not dias:
        return None

    return {
        "tipo": "patron",
        "fecha": fecha_inicio or fecha_fin,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "fechas_funcion": [],
        "dias_semana": dias,
        "texto_fecha_original": texto_original,
    }


def prioridad_tipo_fecha(tipo):
    return PRIORIDAD_TIPO_FECHA.get(tipo, 0)


def es_mejor_info_fecha(nueva, actual):
    if nueva and not actual:
        return True

    if not nueva:
        return False

    p_nueva = prioridad_tipo_fecha(nueva.get("tipo"))
    p_actual = prioridad_tipo_fecha(actual.get("tipo")) if actual else 0

    if p_nueva > p_actual:
        return True

    if p_nueva < p_actual:
        return False

    # desempate: preferimos la que tenga más límites definidos
    score_nueva = int(bool(nueva.get("fecha_inicio"))) + int(bool(nueva.get("fecha_fin")))
    score_actual = 0
    if actual:
        score_actual = int(bool(actual.get("fecha_inicio"))) + int(bool(actual.get("fecha_fin")))

    if score_nueva != score_actual:
        return score_nueva >= score_actual

    # siguiente desempate: más fechas explícitas
    n_fechas_nueva = len(nueva.get("fechas_funcion") or [])
    n_fechas_actual = len(actual.get("fechas_funcion") or []) if actual else 0

    return n_fechas_nueva >= n_fechas_actual


def fecha_representativa(info_fecha):
    if not info_fecha:
        return None

    if info_fecha.get("fecha"):
        return info_fecha["fecha"]

    if info_fecha.get("fecha_inicio"):
        return info_fecha["fecha_inicio"]

    if info_fecha.get("fecha_fin"):
        return info_fecha["fecha_fin"]

    return None


def info_fecha_sigue_vigente(info_fecha, hoy=None):
    if not info_fecha:
        return False

    hoy = hoy or date.today()
    tipo = info_fecha.get("tipo")

    if tipo == "lista":
        fechas = info_fecha.get("fechas_funcion") or []
        return any(f >= hoy for f in fechas)

    if tipo == "unica":
        fecha = info_fecha.get("fecha")
        return bool(fecha and fecha >= hoy)

    if tipo == "rango":
        fecha_fin = info_fecha.get("fecha_fin")
        return bool(fecha_fin and fecha_fin >= hoy)

    if tipo == "hasta":
        fecha_fin = info_fecha.get("fecha_fin")
        return bool(fecha_fin and fecha_fin >= hoy)

    if tipo == "desde":
        fecha_inicio = info_fecha.get("fecha_inicio") or info_fecha.get("fecha")
        return bool(fecha_inicio)

    if tipo == "patron":
        fecha_fin = info_fecha.get("fecha_fin")
        if fecha_fin and fecha_fin < hoy:
            return False
        return True

    return False