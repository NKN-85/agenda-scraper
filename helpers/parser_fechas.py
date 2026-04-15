import re
import unicodedata
from datetime import date

from helpers.fechas_eventos import (
    info_unica,
    info_lista,
    info_rango,
    info_hasta,
    info_desde,
    info_patron,
)


MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


MAPA_DIAS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "sabados": 5,
    "sábados": 5,
    "domingo": 6,
    "domingos": 6,
}


def normalizar_texto_fecha(texto):
    if not texto:
        return ""

    texto = " ".join(str(texto).split()).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def construir_fecha(dia, mes_txt, anio):
    mes = MESES.get(normalizar_texto_fecha(mes_txt))
    if not mes:
        return None

    try:
        return date(int(anio), mes, int(dia))
    except Exception:
        return None


def expandir_rango_dias(dia_inicio, dia_fin):
    orden = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

    d1 = normalizar_texto_fecha(dia_inicio)
    d2 = normalizar_texto_fecha(dia_fin)

    if d1 not in orden or d2 not in orden:
        return []

    i1 = orden.index(d1)
    i2 = orden.index(d2)

    if i1 <= i2:
        nombres = orden[i1:i2 + 1]
    else:
        nombres = orden[i1:] + orden[:i2 + 1]

    return [MAPA_DIAS[n] for n in nombres]


def inferir_anio_del_texto(texto):
    t = normalizar_texto_fecha(texto)
    anios = re.findall(r"\b(20\d{2})\b", t)
    if not anios:
        return None
    return int(anios[-1])


def contiene_patron_alterno(texto):
    t = normalizar_texto_fecha(texto)
    patrones = [
        r"\balternos?\b",
        r"\bsemanas?\s+alternas?\b",
        r"\bcada\s+dos\s+semanas\b",
        r"\bcada\s+2\s+semanas\b",
        r"\bquincenal(?:es)?\b",
    ]
    return any(re.search(p, t) for p in patrones)


def extraer_fechas_explicitas(texto):
    """
    Extrae TODAS las fechas explicitas que pueda encontrar en un mismo texto.
    """
    t = normalizar_texto_fecha(texto)
    fechas = set()
    anio_inferido = inferir_anio_del_texto(t)

    # 21 de abril, 19 de mayo, 13 de octubre y 21 de diciembre de 2026
    for m in re.finditer(
        r"((?:\d{1,2}\s+de\s+[a-z]+)"
        r"(?:\s*,\s*\d{1,2}\s+de\s+[a-z]+)*"
        r"(?:\s+y\s+\d{1,2}\s+de\s+[a-z]+))\s+de\s+(\d{4})",
        t
    ):
        bloque = m.group(1)
        anio = int(m.group(2))
        partes = re.findall(r"(\d{1,2})\s+de\s+([a-z]+)", bloque)
        for dia, mes_txt in partes:
            f = construir_fecha(dia, mes_txt, anio)
            if f:
                fechas.add(f)

    # 10, 11 y 12 de mayo de 2026
    for m in re.finditer(
        r"(\d{1,2})\s*,\s*(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?",
        t
    ):
        anio = int(m.group(5)) if m.group(5) else anio_inferido
        if not anio:
            continue
        for dia in (m.group(1), m.group(2), m.group(3)):
            f = construir_fecha(dia, m.group(4), anio)
            if f:
                fechas.add(f)

    # 28 y 29 de marzo [de 2026]
    for m in re.finditer(
        r"(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?",
        t
    ):
        anio = int(m.group(4)) if m.group(4) else anio_inferido
        if not anio:
            continue
        for dia in (m.group(1), m.group(2)):
            f = construir_fecha(dia, m.group(3), anio)
            if f:
                fechas.add(f)

    # días 20, 21 y 22 de marzo de 2026
    for m in re.finditer(
        r"dias?\s+(\d{1,2})\s*,\s*(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?",
        t
    ):
        anio = int(m.group(5)) if m.group(5) else anio_inferido
        if not anio:
            continue
        for dia in (m.group(1), m.group(2), m.group(3)):
            f = construir_fecha(dia, m.group(4), anio)
            if f:
                fechas.add(f)

    # días 20 y 21 de marzo de 2026
    for m in re.finditer(
        r"dias?\s+(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?",
        t
    ):
        anio = int(m.group(4)) if m.group(4) else anio_inferido
        if not anio:
            continue
        for dia in (m.group(1), m.group(2)):
            f = construir_fecha(dia, m.group(3), anio)
            if f:
                fechas.add(f)

    # Fecha única con día de semana o simple
    for m in re.finditer(
        r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
        t
    ):
        f = construir_fecha(m.group(1), m.group(2), m.group(3))
        if f:
            fechas.add(f)

    for m in re.finditer(
        r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
        t
    ):
        f = construir_fecha(m.group(1), m.group(2), m.group(3))
        if f:
            fechas.add(f)

    return sorted(fechas)


def parsear_fecha_unica(texto):
    fechas = extraer_fechas_explicitas(texto)
    if len(fechas) == 1:
        return info_unica(fechas[0], texto)
    return None


def parsear_lista_fechas(texto):
    fechas = extraer_fechas_explicitas(texto)
    if len(fechas) >= 2:
        return info_lista(fechas, texto)
    return None


def parsear_rango(texto):
    t = normalizar_texto_fecha(texto)

    # Del 15 de agosto de 2025 al 28 de junio de 2026
    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
        t
    )
    if m:
        inicio = construir_fecha(m.group(1), m.group(2), m.group(3))
        fin = construir_fecha(m.group(4), m.group(5), m.group(6))
        return info_rango(inicio, fin, texto)

    # Del 20 de agosto al 27 de septiembre de 2026
    m = re.search(
        r"del\s+(\d{1,2})\s+de\s+([a-z]+)\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
        t
    )
    if m:
        inicio = construir_fecha(m.group(1), m.group(2), m.group(5))
        fin = construir_fecha(m.group(3), m.group(4), m.group(5))
        return info_rango(inicio, fin, texto)

    # Del 15 al 27 de mayo de 2026
    m = re.search(
        r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
        t
    )
    if m:
        inicio = construir_fecha(m.group(1), m.group(3), m.group(4))
        fin = construir_fecha(m.group(2), m.group(3), m.group(4))
        return info_rango(inicio, fin, texto)

    return None


def parsear_hasta(texto):
    t = normalizar_texto_fecha(texto)

    m = re.search(
        r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
        t
    )
    if m:
        fin = construir_fecha(m.group(1), m.group(2), m.group(3))
        return info_hasta(fin, texto)

    return None


def parsear_desde(texto):
    t = normalizar_texto_fecha(texto)

    m = re.search(
        r"desde\s+el\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
        t
    )
    if m:
        inicio = construir_fecha(m.group(1), m.group(2), m.group(3))
        return info_desde(inicio, texto)

    return None


def parsear_patron_semanal(texto, fecha_inicio=None, fecha_fin=None):
    t = normalizar_texto_fecha(texto)
    dias = set()

    # Caso: "de miercoles a viernes"
    for m in re.finditer(
        r"de\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t
    ):
        dias.update(expandir_rango_dias(m.group(1), m.group(2)))

    # Casos contextuales legitimos aunque haya fechas en la misma linea
    patrones_contextuales = [
        r"\blos\s+(lunes|martes|miercoles|jueves|viernes|sabados|domingos)\b",
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+del\b",
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+y\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b",
    ]

    for patron in patrones_contextuales:
        for m in re.finditer(patron, t):
            grupos = [g for g in m.groups() if g]
            for g in grupos:
                g_norm = normalizar_texto_fecha(g)
                if g_norm in MAPA_DIAS:
                    dias.add(MAPA_DIAS[g_norm])

    # Fallback conservador: dias sueltos solo si no parece fecha unica
    if not dias:
        tiene_fecha_concreta = bool(
            re.search(r"\b\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{4}\b", t)
        )
        if not tiene_fecha_concreta:
            for nombre, idx in MAPA_DIAS.items():
                if re.search(rf"\b{re.escape(nombre)}\b", t):
                    dias.add(idx)

    if not dias:
        return None

    return info_patron(
        dias_semana=sorted(dias),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        texto_original=texto,
    )


def parsear_texto_fecha(texto):
    """
    Intenta interpretar un único texto sin contexto externo.
    Prioridad:
    lista > rango > hasta > desde > unica
    El patrón semanal se resuelve mejor cuando ya se conocen límites.
    """
    if not texto or not str(texto).strip():
        return None

    for parser in (
        parsear_lista_fechas,
        parsear_rango,
        parsear_hasta,
        parsear_desde,
        parsear_fecha_unica,
    ):
        info = parser(texto)
        if info:
            return info

    return None