from datetime import date, timedelta
import re
import unicodedata

from helpers.fechas_eventos import es_mejor_info_fecha, info_lista, info_unica
from helpers.parser_fechas import (
    parsear_texto_fecha,
    parsear_patron_semanal,
    extraer_fechas_explicitas,
    contiene_patron_alterno,
    normalizar_texto_fecha,
    MESES,
)


STOPWORDS_TITULO = {
    "el", "la", "los", "las", "de", "del", "y", "en", "a",
    "un", "una", "show", "teatro", "funcion", "función",
    "hora", "horas", "domingo", "domingos", "lunes", "martes",
    "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado",
    "alterno", "alternos",
}


def normalizar_titulo_match(texto):
    if not texto:
        return ""
    t = " ".join(str(texto).split()).strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[,:;.!?()\"'`´]", " ", t)
    t = re.sub(r"[-_/|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokenizar_titulo(texto):
    t = normalizar_titulo_match(texto)
    if not t:
        return []
    return [x for x in t.split() if x and x not in STOPWORDS_TITULO and len(x) >= 2]


def generar_variantes_titulo(titulo):
    base = normalizar_titulo_match(titulo)
    if not base:
        return []

    variantes = {base}
    cola = {base}

    patrones_recorte = [
        r"\s*-\s*tributo musical\b.*$",
        r"\s*-\s*tributo\b.*$",
        r"\s*,\s*el musical\b.*$",
        r"\s+el musical\b.*$",
        r"\s+musical\b.*$",
        r"\s+show\b.*$",
        r"\s+en concierto\b.*$",
        r"\s+tributo\b.*$",
    ]

    while cola:
        actual = cola.pop()
        for patron in patrones_recorte:
            nuevo = re.sub(patron, "", actual).strip()
            nuevo = re.sub(r"\s+", " ", nuevo)
            if nuevo and len(nuevo) >= 4 and nuevo not in variantes:
                variantes.add(nuevo)
                cola.add(nuevo)

    return sorted(variantes, key=len, reverse=True)


def texto_coincide_con_titulo(texto, titulo_evento):
    texto_norm = normalizar_titulo_match(texto)
    if not texto_norm or not titulo_evento:
        return False

    for variante in generar_variantes_titulo(titulo_evento):
        if variante in texto_norm or texto_norm in variante:
            return True

    tokens_titulo = set(tokenizar_titulo(titulo_evento))
    tokens_texto = set(tokenizar_titulo(texto))

    if not tokens_titulo or not tokens_texto:
        return False

    comunes = tokens_titulo & tokens_texto
    if len(comunes) >= 2:
        return True

    ratio = len(comunes) / max(len(tokens_titulo), 1)
    return ratio >= 0.6


def score_titulo(texto, titulo_evento):
    texto_norm = normalizar_titulo_match(texto)
    if not texto_norm or not titulo_evento:
        return 0

    mejor = 0
    for variante in generar_variantes_titulo(titulo_evento):
        if variante == texto_norm:
            mejor = max(mejor, 100)
        elif variante in texto_norm or texto_norm in variante:
            mejor = max(mejor, 80)

    tokens_titulo = set(tokenizar_titulo(titulo_evento))
    tokens_texto = set(tokenizar_titulo(texto))
    if tokens_titulo and tokens_texto:
        comunes = tokens_titulo & tokens_texto
        if comunes:
            ratio = len(comunes) / max(len(tokens_titulo), 1)
            mejor = max(mejor, int(ratio * 70))

    return mejor


def expandir_patron_a_fechas(fecha_inicio, fecha_fin, dias_semana):
    if not fecha_inicio or not fecha_fin or not dias_semana:
        return []

    fechas = []
    cursor = fecha_inicio

    while cursor <= fecha_fin:
        if cursor.weekday() in dias_semana:
            fechas.append(cursor)
        cursor += timedelta(days=1)

    return fechas


def extraer_contexto_mes_anio(textos):
    contextos = []
    mes_actual = None
    anio_actual = None

    patron = re.compile(
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+(20\d{2})"
    )

    for texto in textos:
        t = normalizar_texto_fecha(texto)
        m = patron.search(t)
        if m:
            mes_actual = m.group(1)
            anio_actual = int(m.group(2))
        contextos.append((mes_actual, anio_actual))

    return contextos


def extraer_dias_sueltos_de_linea(texto):
    t = normalizar_texto_fecha(texto)
    t = re.sub(r"\b\d{1,2}:\d{2}\b", " ", t)

    dias = []
    for m in re.finditer(r"\b([0-3]?\d)\b", t):
        n = int(m.group(1))
        if 1 <= n <= 31:
            dias.append(n)

    return dias


def construir_fecha_segura(dia, mes_txt, anio):
    try:
        mes_num = MESES.get(mes_txt.lower())
        if not mes_num:
            return None
        return date(anio, mes_num, dia)
    except Exception:
        return None


def es_linea_ruido_calendario(texto):
    t = normalizar_titulo_match(texto)
    if not t:
        return True

    if re.fullmatch(r"\d{1,2}:\d{2}", t):
        return True

    if re.search(r"\bhora\b", t):
        return True

    if re.fullmatch(r"[0-3]?\d(\s*[|/,-]\s*[0-3]?\d)+", t):
        return True

    if re.search(
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+20\d{2}",
        t,
    ):
        return True

    return False


def extraer_bloques_calendario(textos, fecha_inicio=None, fecha_fin=None):
    bloques = []
    contextos = extraer_contexto_mes_anio(textos)

    i = 0
    while i < len(textos):
        mes, anio = contextos[i]
        if not mes or not anio:
            i += 1
            continue

        fechas = []
        j = i

        while j < len(textos):
            mes_j, anio_j = contextos[j]
            if j > i and mes_j and anio_j and (mes_j != mes or anio_j != anio):
                break

            for dia in extraer_dias_sueltos_de_linea(textos[j]):
                f = construir_fecha_segura(dia, mes, anio)
                if not f:
                    continue
                if fecha_inicio and f < fecha_inicio:
                    continue
                if fecha_fin and f > fecha_fin:
                    continue
                fechas.append(f)

            j += 1

        fechas = sorted(set(fechas))
        if fechas:
            bloques.append(
                {
                    "mes": mes,
                    "anio": anio,
                    "inicio": i,
                    "fin": j - 1,
                    "fechas": fechas,
                }
            )

        i = j

    return bloques


def buscar_titulo_cercano_a_bloque(textos, titulo_evento, bloque):
    mejor_score = 0
    mejor_dist = 10**9
    mejor_idx = None

    for idx, texto in enumerate(textos):
        if es_linea_ruido_calendario(texto):
            continue

        s = score_titulo(texto, titulo_evento)
        if s <= 0:
            continue

        if idx < bloque["inicio"]:
            dist = bloque["inicio"] - idx
        elif idx > bloque["fin"]:
            dist = idx - bloque["fin"]
        else:
            dist = 0

        if s > mejor_score or (s == mejor_score and dist < mejor_dist):
            mejor_score = s
            mejor_dist = dist
            mejor_idx = idx

    return mejor_idx, mejor_score, mejor_dist


def extraer_fechas_relacionadas_con_titulo(textos, titulo_evento, fecha_inicio=None, fecha_fin=None):
    if not textos or not titulo_evento:
        return []

    bloques = extraer_bloques_calendario(
        textos=textos,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    fechas = set()

    for bloque in bloques:
        idx, score, dist = buscar_titulo_cercano_a_bloque(textos, titulo_evento, bloque)

        if idx is None:
            continue

        if score >= 80:
            fechas.update(bloque["fechas"])
            continue

        if score >= 45 and dist <= 6:
            fechas.update(bloque["fechas"])
            continue

    return sorted(fechas)


def extraer_fechas_desde_calendario_global(textos, fecha_inicio=None, fecha_fin=None):
    fechas = set()
    bloques = extraer_bloques_calendario(
        textos=textos,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    for bloque in bloques:
        fechas.update(bloque["fechas"])

    for texto in textos:
        for f in extraer_fechas_explicitas(texto):
            if fecha_inicio and f < fecha_inicio:
                continue
            if fecha_fin and f > fecha_fin:
                continue
            fechas.add(f)

    return sorted(fechas)


def extraer_dia_semana_objetivo(textos):
    texto = " ".join(textos).lower()

    mapa = {
        "lunes": 0,
        "martes": 1,
        "miercoles": 2,
        "miércoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5,
        "sábado": 5,
        "domingo": 6,
    }

    for k, v in mapa.items():
        if k in texto:
            return v

    return None


def filtrar_por_dia_semana(fechas, textos):
    dia = extraer_dia_semana_objetivo(textos)
    if dia is None:
        return sorted(fechas)
    return sorted(f for f in fechas if f.weekday() == dia)


def resolver_info_fecha_de_textos(textos, titulo_evento=None):
    if not textos:
        return None

    textos = [str(t).strip() for t in textos if t and str(t).strip()]
    if not textos:
        return None

    mejor = None
    mejor_limites = None
    mejor_patron = None
    fechas_explicitas = set()
    hay_alternos = False

    for texto in textos:
        if contiene_patron_alterno(texto):
            hay_alternos = True

        info = parsear_texto_fecha(texto)
        if info and es_mejor_info_fecha(info, mejor):
            mejor = info

        if info and info.get("tipo") in {"rango", "hasta", "desde"} and es_mejor_info_fecha(info, mejor_limites):
            mejor_limites = info

        fechas_explicitas.update(extraer_fechas_explicitas(texto))

    fecha_inicio = mejor_limites.get("fecha_inicio") if mejor_limites else None
    fecha_fin = mejor_limites.get("fecha_fin") if mejor_limites else None

    for texto in textos:
        patron = parsear_patron_semanal(
            texto,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        if patron and es_mejor_info_fecha(patron, mejor_patron):
            mejor_patron = patron

    if hay_alternos:
        fechas_titulo = extraer_fechas_relacionadas_con_titulo(
            textos=textos,
            titulo_evento=titulo_evento,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )

        # Si el calendario ya nos da fechas concretas del evento,
        # NO aplicamos alternancia sintética. Solo filtramos por día.
        if fechas_titulo:
            fechas = filtrar_por_dia_semana(fechas_titulo, textos)

            if len(fechas) >= 2:
                return info_lista(fechas, "alternos")
            if len(fechas) == 1:
                return info_unica(fechas[0], "alternos")

        # Fallback global solo si no se pudo asociar por título.
        fechas_globales = extraer_fechas_desde_calendario_global(
            textos=textos,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        fechas_globales = filtrar_por_dia_semana(fechas_globales, textos)

        if len(fechas_globales) >= 2:
            return info_lista(fechas_globales, "alternos")
        if len(fechas_globales) == 1:
            return info_unica(fechas_globales[0], "alternos")

        if mejor_limites:
            return mejor_limites

        return None

    if mejor_patron and fecha_inicio and fecha_fin:
        fechas_patron = expandir_patron_a_fechas(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            dias_semana=mejor_patron.get("dias_semana") or [],
        )

        todas = set(fechas_patron)
        todas.update(fechas_explicitas)

        if todas:
            return info_lista(sorted(todas), "mixto")

    if len(fechas_explicitas) >= 2:
        return info_lista(sorted(fechas_explicitas), "lista")

    if mejor_patron and es_mejor_info_fecha(mejor_patron, mejor):
        return mejor_patron

    if mejor:
        return mejor

    if mejor_limites:
        return mejor_limites

    return None


def resolver_info_fecha_de_bloques(textos_portada=None, textos_ficha=None, titulo_evento=None):
    textos_portada = textos_portada or []
    textos_ficha = textos_ficha or []

    info = resolver_info_fecha_de_textos(textos_ficha, titulo_evento)
    if info:
        return info

    return resolver_info_fecha_de_textos(textos_portada, titulo_evento)


def extraer_limites_de_info(info):
    if not info:
        return None, None
    return info.get("fecha_inicio"), info.get("fecha_fin")