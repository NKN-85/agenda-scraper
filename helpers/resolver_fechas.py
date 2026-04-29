from datetime import date, timedelta
import re
import unicodedata

from helpers.fechas_eventos import es_mejor_info_fecha, info_lista, info_unica, info_rango, info_hasta, info_desde, info_patron
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

MAPA_DIAS_LOCAL = {
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


def es_linea_exclusion_funciones(texto):
    t = normalizar_texto_fecha(texto)
    patrones = [
        r"\bno\s+hay\s+funcion(?:es)?\b",
        r"\bsin\s+funcion(?:es)?\b",
        r"\bexcepto\b",
        r"\bmenos\b",
    ]
    return any(re.search(p, t) for p in patrones)


def extraer_fechas_de_lineas_funciones(textos):
    fechas = set()

    for texto in textos:
        t = normalizar_texto_fecha(texto)

        if es_linea_exclusion_funciones(t):
            continue

        if "funciones:" in t or "funcion:" in t:
            for f in extraer_fechas_explicitas(texto):
                fechas.add(f)

    return sorted(fechas)


def extraer_fechas_exclusion(textos, anio_defecto=None):
    fechas = set()
    contextos = extraer_contexto_mes_anio(textos)

    for idx, texto in enumerate(textos):
        t = normalizar_texto_fecha(texto)
        if not es_linea_exclusion_funciones(t):
            continue

        mes_ctx, anio_ctx = contextos[idx]
        anio = anio_ctx or anio_defecto
        if not anio:
            continue

        for f in extraer_fechas_explicitas(texto):
            fechas.add(f)

        m = re.search(
            r"(?:no\s+hay\s+funcion(?:es)?|sin\s+funcion(?:es)?)(?::)?\s*(.+)",
            t
        )
        if not m:
            continue

        resto = m.group(1)

        if mes_ctx:
            for dia in extraer_dias_sueltos_de_linea(resto):
                f = construir_fecha_segura(dia, mes_ctx, anio)
                if f:
                    fechas.add(f)

    return sorted(fechas)


def expandir_rango_dias_local(dia_inicio, dia_fin):
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

    return [MAPA_DIAS_LOCAL[n] for n in nombres]


def extraer_patron_resiliente(texto, fecha_inicio=None, fecha_fin=None):
    """
    Refuerzo específico para GruposMedia:
    detecta todos los días de una línea con horarios del estilo:
    - De miércoles a viernes: 20:00 h. Sábados: 18:00 h. Domingos: 18:00 h.
    - Viernes y sábados: 19:00 h. Domingos: 17:00 h.
    """
    t = normalizar_texto_fecha(texto)
    dias = set()

    # Rangos: de martes a jueves
    for m in re.finditer(
        r"de\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)",
        t,
    ):
        dias.update(expandir_rango_dias_local(m.group(1), m.group(2)))

    # Pares: viernes y sabados / miercoles y jueves
    for m in re.finditer(
        r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+y\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b",
        t,
    ):
        for g in m.groups():
            g_norm = normalizar_texto_fecha(g)
            if g_norm in MAPA_DIAS_LOCAL:
                dias.add(MAPA_DIAS_LOCAL[g_norm])

    # Días sueltos seguidos de ":" o de referencia horaria
    for nombre, idx in MAPA_DIAS_LOCAL.items():
        if re.search(rf"\b{re.escape(nombre)}\b\s*:", t):
            dias.add(idx)

    # Si hay horas, barrido amplio de días en la línea
    if re.search(r"\d{{1,2}}(?::|\.)\d{{2}}", t):
        for nombre, idx in MAPA_DIAS_LOCAL.items():
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


def extraer_limites_flexibles(textos):
    """
    Refuerzo para formatos de GruposMedia que a veces no captura parser_fechas:
    - Del 1 julio al 26 de julio de 2026
    - Del 20 de agosto al 27 de septiembre de 2026
    - Hasta el 28 de junio de 2026
    """
    for texto in textos:
        t = normalizar_texto_fecha(texto)

        # Hasta el 28 de junio de 2026
        m = re.search(
            r"hasta\s+el\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
            t,
        )
        if m:
            fin = construir_fecha_segura(int(m.group(1)), m.group(2), int(m.group(3)))
            if fin:
                return info_hasta(fin, texto)

        # Desde el 10 de abril de 2026
        m = re.search(
            r"desde\s+el\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
            t,
        )
        if m:
            inicio = construir_fecha_segura(int(m.group(1)), m.group(2), int(m.group(3)))
            if inicio:
                return info_desde(inicio, texto)

        # Del 20 de agosto al 27 de septiembre de 2026
        m = re.search(
            r"del\s+(\d{1,2})\s+de\s+([a-z]+)\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
            t,
        )
        if m:
            inicio = construir_fecha_segura(int(m.group(1)), m.group(2), int(m.group(5)))
            fin = construir_fecha_segura(int(m.group(3)), m.group(4), int(m.group(5)))
            if inicio and fin:
                return info_rango(inicio, fin, texto)

        # Del 1 julio al 26 de julio de 2026
        m = re.search(
            r"del\s+(\d{1,2})\s+([a-z]+)\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
            t,
        )
        if m:
            inicio = construir_fecha_segura(int(m.group(1)), m.group(2), int(m.group(5)))
            fin = construir_fecha_segura(int(m.group(3)), m.group(4), int(m.group(5)))
            if inicio and fin:
                return info_rango(inicio, fin, texto)

        # Del 15 al 27 de mayo de 2026
        m = re.search(
            r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
            t,
        )
        if m:
            inicio = construir_fecha_segura(int(m.group(1)), m.group(3), int(m.group(4)))
            fin = construir_fecha_segura(int(m.group(2)), m.group(3), int(m.group(4)))
            if inicio and fin:
                return info_rango(inicio, fin, texto)

    return None


def fusionar_patrones(patrones, fecha_inicio=None, fecha_fin=None):
    if not patrones:
        return None

    dias = set()
    textos_originales = []

    for patron in patrones:
        dias.update(patron.get("dias_semana") or [])
        if patron.get("texto_fecha_original"):
            textos_originales.append(str(patron.get("texto_fecha_original")))

    if not dias:
        return None

    return info_patron(
        dias_semana=sorted(dias),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        texto_original=" | ".join(textos_originales) if textos_originales else None,
    )


def resolver_info_fecha_de_textos(textos, titulo_evento=None):
    if not textos:
        return None

    textos = [str(t).strip() for t in textos if t and str(t).strip()]
    if not textos:
        return None

    mejor = None
    mejor_limites = None
    fechas_explicitas = set()
    hay_alternos = False
    patrones_detectados = []

    fechas_linea_funciones = extraer_fechas_de_lineas_funciones(textos)
    if fechas_linea_funciones:
        if len(fechas_linea_funciones) >= 2:
            return info_lista(fechas_linea_funciones, "funciones")
        return info_unica(fechas_linea_funciones[0], "funciones")

    for texto in textos:
        if contiene_patron_alterno(texto):
            hay_alternos = True

        info = parsear_texto_fecha(texto)
        if info and es_mejor_info_fecha(info, mejor):
            mejor = info

        if info and info.get("tipo") in {"rango", "hasta", "desde"} and es_mejor_info_fecha(info, mejor_limites):
            mejor_limites = info

        if es_linea_exclusion_funciones(texto):
            continue

        fechas_explicitas.update(extraer_fechas_explicitas(texto))

    # Fallback de límites para formatos de GruposMedia que no siempre coge parser_fechas
    if not mejor_limites:
        mejor_limites = extraer_limites_flexibles(textos)

    fecha_inicio = mejor_limites.get("fecha_inicio") if mejor_limites else None
    fecha_fin = mejor_limites.get("fecha_fin") if mejor_limites else None

    for texto in textos:
        patron = parsear_patron_semanal(
            texto,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        if patron:
            patrones_detectados.append(patron)

        patron_refuerzo = extraer_patron_resiliente(
            texto,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        if patron_refuerzo:
            patrones_detectados.append(patron_refuerzo)

    mejor_patron = fusionar_patrones(
        patrones_detectados,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    if hay_alternos:
        fechas_titulo = extraer_fechas_relacionadas_con_titulo(
            textos=textos,
            titulo_evento=titulo_evento,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )

        if fechas_titulo:
            fechas = filtrar_por_dia_semana(fechas_titulo, textos)

            if len(fechas) >= 2:
                return info_lista(fechas, "alternos")
            if len(fechas) == 1:
                return info_unica(fechas[0], "alternos")

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

    if mejor_patron and not fecha_inicio and fecha_fin:
        fecha_inicio_sintetica = date.today()

        fechas_patron = expandir_patron_a_fechas(
            fecha_inicio=fecha_inicio_sintetica,
            fecha_fin=fecha_fin,
            dias_semana=mejor_patron.get("dias_semana") or [],
        )

        fechas_exclusion = set(
            extraer_fechas_exclusion(
                textos=textos,
                anio_defecto=fecha_fin.year if fecha_fin else None,
            )
        )

        fechas_finales = sorted(f for f in fechas_patron if f not in fechas_exclusion)

        if len(fechas_finales) >= 2:
            return info_lista(fechas_finales, "patron_hasta")
        if len(fechas_finales) == 1:
            return info_unica(fechas_finales[0], "patron_hasta")

    if len(fechas_explicitas) >= 2:
        return info_lista(sorted(fechas_explicitas), "lista")

    if mejor_limites and mejor_limites.get("tipo") == "hasta":
        if mejor_patron:
            fecha_inicio_sintetica = date.today()
            fechas_patron = expandir_patron_a_fechas(
                fecha_inicio=fecha_inicio_sintetica,
                fecha_fin=fecha_fin,
                dias_semana=mejor_patron.get("dias_semana") or [],
            )
            fechas_exclusion = set(
                extraer_fechas_exclusion(
                    textos=textos,
                    anio_defecto=fecha_fin.year if fecha_fin else None,
                )
            )
            fechas_finales = sorted(f for f in fechas_patron if f not in fechas_exclusion)

            if len(fechas_finales) >= 2:
                return info_lista(fechas_finales, "patron_hasta")
            if len(fechas_finales) == 1:
                return info_unica(fechas_finales[0], "patron_hasta")

        return mejor_limites

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