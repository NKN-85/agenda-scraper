from datetime import date, datetime
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


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
    return fecha.strftime("%d/%m/%Y")


def es_futura_o_hoy(fecha):
    if not fecha:
        return False
    return fecha >= date.today()


# -------------------------
# CLAVE / DEDUPLICADO
# -------------------------

def clave_evento(titulo, fecha, lugar):
    return (
        limpiar_texto(titulo).lower(),
        fecha,
        limpiar_texto(lugar).lower()
    )


def agregar_evento(eventos, vistos, titulo, fecha_evento, lugar, url_evento, fuente):
    if not titulo or not fecha_evento or not lugar or not url_evento:
        return False

    clave = clave_evento(titulo, fecha_evento, lugar)
    if clave in vistos:
        return False

    vistos.add(clave)

    eventos.append([
        limpiar_texto(titulo),
        fecha_a_str(fecha_evento),
        limpiar_texto(lugar),
        limpiar_texto(url_evento),
        limpiar_texto(fuente),
    ])

    return True

# -------------------------
# CONVERSIÓN DE MESES
# -------------------------

def mes_es_a_numero(mes_txt):
    meses = {
        "ene": 1, "enero": 1,
        "feb": 2, "febrero": 2,
        "mar": 3, "marzo": 3,
        "abr": 4, "abril": 4,
        "may": 5, "mayo": 5,
        "jun": 6, "junio": 6,
        "jul": 7, "julio": 7,
        "ago": 8, "agosto": 8,
        "sep": 9, "septiembre": 9,
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
    except:
        return None


def construir_fecha_actual(dia, mes_txt):
    try:
        hoy = date.today()
        mes = mes_es_a_numero(mes_txt)

        if not mes:
            return None

        anio = hoy.year

        # si el mes ya pasó claramente → siguiente año
        if mes < hoy.month - 1:
            anio += 1

        return date(anio, mes, int(dia))
    except:
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

    # 12-feb-26
    if "-" in fecha_texto:
        partes = fecha_texto.split("-")
        if len(partes) == 3:
            dia = int(partes[0])
            mes = meses.get(partes[1][:3])
            anio = 2000 + int(partes[2])
            if mes:
                return date(anio, mes, dia)

    # 12 FEB 2026
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

    # "20 marzo - 6:00 pm"
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
        except:
            pass

    # "30-abr"
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
            except:
                pass

    return None