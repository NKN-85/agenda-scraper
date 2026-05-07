import requests
from bs4 import BeautifulSoup
import json
import hashlib
import html
import time
from collections import defaultdict
from urllib.parse import urljoin, urldefrag, urlparse, urlsplit, urlunsplit
from datetime import datetime

BASE_URL = "https://www.esmadrid.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MES_ACTUAL = datetime.now().month



TEMPORADAS = {
    "navidad": {
        "keywords": [
            "navidad",
            "reyes magos",
            "paje real",
            "cabalgata",
            "ano nuevo",
            "año nuevo",
            "campanadas",
            "uvas de año nuevo",
            "uvas de ano nuevo"
        ],
        "meses_validos": [11, 12, 1]
    },
    "invierno": {
        "keywords": [
            "cosas hacer invierno",
            "cosas que hacer en invierno",
            "invierno en madrid"
        ],
        "meses_validos": [12, 1, 2]
    },
    "verano": {
        "keywords": [
            "cosas hacer verano",
            "cosas que hacer en verano",
            "verano en madrid",
            "abanicos para el verano"
        ],
        "meses_validos": [6, 7, 8, 9]
    },
    "agosto": {
        "keywords": [
            "fiestas de agosto",
            "san cayetano",
            "virgen de la paloma"
        ],
        "meses_validos": [7, 8]
    },
    "otono": {
        "keywords": [
            "cosas hacer otoño",
            "cosas hacer otono",
            "cosas que hacer en otoño",
            "cosas que hacer en otono",
            "otoño en madrid",
            "otono en madrid"
        ],
        "meses_validos": [9, 10, 11]
    },
    "primavera": {
        "keywords": [
            "cosas hacer primavera",
            "cosas que hacer en primavera",
            "primavera en madrid"
        ],
        "meses_validos": [3, 4, 5, 6]
    }
}

SEMILLAS_OBLIGATORIAS = {
    "trenes_turisticos": [
        ("Tren de Cervantes", "https://www.esmadrid.com/tren-cervantes"),
        ("El Tren de Felipe II", "https://www.esmadrid.com/tren-felipe-ii-el-escorial"),
        ("El Tren de Arganda", "https://www.esmadrid.com/tren-arganda"),
        ("El Tren de la Fresa", "https://www.esmadrid.com/tren-fresa")
    ]
}

def esta_fuera_de_temporada(item):
    """
    Devuelve True si el item es claramente estacional y el mes actual
    no encaja con su ventana natural.

    Se usa solo para evergreen_output.json. El master conserva todos
    los contenidos para no perder inventario.

    Importante: evita falsos positivos como "San Lorenzo de El Escorial"
    o "Tren de Felipe II", que contienen palabras que también aparecen en
    fiestas de agosto pero no son contenidos estacionales.
    """
    titulo = item.get("titulo", "")
    descripcion = item.get("descripcion", "")
    url = item.get("url", "")
    texto = f"{titulo} {descripcion} {url}".lower()

    # Excepciones evergreen: no ocultar lugares/trenes permanentes por contener
    # palabras como "San Lorenzo" en un topónimo.
    if "san lorenzo de el escorial" in texto:
        return False

    for regla in TEMPORADAS.values():
        if any(keyword in texto for keyword in regla["keywords"]):
            return MES_ACTUAL not in regla["meses_validos"]

    return False

INTENCION_MAP = {
    "excursiones": "viaje",
    "trenes_turisticos": "viaje",
    "rutas_madrid": "cultura",
    "tradicion_cultura": "cultura",
    "barrios": "barrios",
    "planes_madrid": "ocio",
    "parques_jardines": "naturaleza",
    "miradores": "naturaleza",
    "edificios_historicos": "cultura",
    "arqueologia_clm": "cultura",
    "rutas_historicas_clm": "cultura",
    "castillos_clm": "cultura"
}

URLS_INDICE = {
    "https://www.esmadrid.com/barrios-de-madrid",
    "https://www.esmadrid.com/planes-madrid",
    "https://www.esmadrid.com/rutas-excursiones-madrid",
    "https://www.esmadrid.com/excursiones-madrid",
    "https://www.esmadrid.com/trenes-turisticos",
    "https://www.esmadrid.com/rutas-madrid",
    "https://www.esmadrid.com/tradicion-cultura-madrid",
    "https://www.esmadrid.com/parques-jardines-madrid",
    "https://www.esmadrid.com/miradores-madrid"
}

TITULOS_RUIDO = {
    "sus barrios",
    "planes madrid",
    "rutas y excursiones",
    "excursiones desde madrid",
    "trenes turísticos",
    "rutas por madrid",
    "parques y jardines",
    "miradores de madrid",
    "inicio de sesión",
    "buscador",
    "contacto",
    "bases legales",
    "política de cookies",
    "condiciones generales"
}

KEYWORDS_EXCLUIR = [
    "city card",
    "madrid city card",
    "madrid útil",
    "madrid util",
    "cómo llegar",
    "como llegar",
    "moverse por madrid",
    "cercanías",
    "cercanias",
    "tren madrid",
    "transporte",
    "tarjeta turística",
    "tarjeta turistica",
    "accesible",
    "mapas y guías",
    "mapas y guias",
    "atención al visitante",
    "atencion al visitante",
    "dónde dormir",
    "donde dormir",
    "información turística",
    "informacion turistica",
    "crea tu itinerario"
]

URLS_EXCLUIR = [
    "madrid-city-card",
    "madrid-util",
    "madrid-accesible",
    "tren-madrid",
    "tren-cercanias-madrid",
    "mapas-y-guias",
    "atencion-visitante",
    "donde-dormir",
    "bus-expres",
    "consignas",
    "aeropuerto-adolfo"
]

PATRONES_VALIDOS = {
    "excursiones": [
        "/excursion-",
        "/buitrago-lozoya",
        "/chinchon",
        "/colmenar-oreja",
        "/granja-san-ildefonso",
        "/hayedo-montejo",
        "/manzanares-real",
        "/navalcarnero",
        "/nuevo-baztan",
        "/patones",
        "/rascafria",
        "/san-martin-valdeiglesias",
        "/torrelaguna",
        "/villarejo-salvanes",
        "/enoturismo-madrid",
        "/informacion-turistica/puy-du-fou",
        "/informacion-turistica/bosque-encantado"
    ],
    "trenes_turisticos": [
        "/tren-cervantes",
        "/tren-felipe",
        "/tren-arganda",
        "/tren-fresa",
        "/tren-medieval",
        "/tren-zorrilla",
        "/agenda/tren-"
    ],
    "rutas_madrid": [
        "/madrid-antonio-palacios",
        "/madrid-benito-perez-galdos",
        "/madrid-cervantes",
        "/madrid-de-almodovar",
        "/madrid-ernest-hemingway",
        "/madrid-futbolero",
        "/madrid-musulman",
        "/madrid-sibaritas",
        "/madrid-extravagante",
        "/el-madrid-",
        "/casa-papel-madrid",
        "/estatuas-madrid",
        "/estatuas-mujeres-madrid",
        "/que-hacer-en-el-rastro"
    ],
    "tradicion_cultura": [
        "/historia-de-madrid",
        "/gastronomia-madrid",
        "/folclore-madrid",
        "/zarzuela-madrid",
        "/reposteria-tradicional",
        "/comercios-centenarios",
        "/meninas-madrid",
        "/fiestas-",
        "/agenda/fiestas-",
        "/san-isidro",
        "/agenda/san-isidro",
        "/abanicos-madrid",
        "/navidad-madrid"
    ],
    "barrios": [
        "/barrios-de-madrid/"
    ],
    "planes_madrid": [
        "/planes-",
        "/madrid-lluvia",
        "/madrid-subterraneo",
        "/madrid-sibaritas",
        "/madrid-extravagante",
        "/cosas-",
        "/a-gusto-de-toda-la-familia",
        "/que-hacer-"
    ],
    "parques_jardines": [
        "/informacion-turistica/parque-",
        "/informacion-turistica/jardin",
        "/informacion-turistica/jardines",
        "/informacion-turistica/quinta",
        "/informacion-turistica/campo-del-moro",
        "/informacion-turistica/casa-de-campo",
        "/informacion-turistica/madrid-rio",
        "/informacion-turistica/real-jardin-botanico",
        "/jardines-manzanares",
        "/informacion-turistica/finca-vista-alegre",
        "/informacion-turistica/huerta-salud"
    ],
    "miradores": [
        "/mirador",
        "/faro-de-moncloa",
        "/circulo-de-bellas-artes",
        "/templo-de-debod",
        "/teleferico-madrid",
        "/lago-de-la-casa-de-campo",
        "/cerro-tio-pio",
        "/silo-hortaleza",
        "/monumento-alfonso"
    ]
}


def generar_id(url):
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def mapear_intencion(categoria):
    return INTENCION_MAP.get(categoria, "otros")


def limpiar_url(url, base_url):
    url = html.unescape(url)
    url = urljoin(base_url, url)
    url, _ = urldefrag(url)

    partes = urlsplit(url)

    netloc = partes.netloc.lower()
    path = partes.path.rstrip("/") or "/"

    return urlunsplit((
        partes.scheme,
        netloc,
        path,
        partes.query,
        ""
    ))


def cargar_sources():
    with open("evergreen_sources.json", "r", encoding="utf-8") as f:
        return json.load(f)


def es_url_valida(url, categoria):
    if not url.startswith(BASE_URL):
        return False

    if url in URLS_INDICE:
        return False

    if any(x in url for x in URLS_EXCLUIR):
        return False

    patrones = PATRONES_VALIDOS.get(categoria, [])
    return any(patron in url for patron in patrones)


def es_titulo_valido(titulo):
    t = " ".join(titulo.lower().split())

    if len(t) < 3:
        return False

    if t in TITULOS_RUIDO:
        return False

    if any(k in t for k in KEYWORDS_EXCLUIR):
        return False

    if "dfp tag" in t:
        return False

    if t.startswith("http"):
        return False

    return True


def obtener_descripcion(soup, source=None):
    source = source or {}
    selector = source.get("selector_descripcion")

    if selector:
        nodo = soup.select_one(selector)
        if nodo:
            if nodo.name == "meta" and nodo.get("content"):
                return nodo["content"].strip()
            texto = nodo.get_text(" ", strip=True)
            if texto:
                return texto

    meta = soup.select_one('meta[name="description"]')
    if meta and meta.get("content"):
        return meta["content"].strip()

    p = soup.select_one("p")
    if p:
        return p.get_text(" ", strip=True)

    return ""


def obtener_titulo_real(soup, fallback, source=None):
    source = source or {}
    selector = source.get("selector_titulo")

    if selector:
        nodo = soup.select_one(selector)
        if nodo:
            texto = nodo.get_text(" ", strip=True)
            if texto:
                return texto

    h1 = soup.select_one("h1")
    if h1:
        texto = h1.get_text(" ", strip=True)
        if texto:
            return texto

    title = soup.select_one("title")
    if title:
        texto = title.get_text(" ", strip=True)
        texto = texto.replace("| Turismo Madrid", "").strip()
        if texto:
            return texto

    return fallback


def boost_mes_actual(texto):
    texto = texto.lower()

    meses = {
        1: ["enero", "reyes", "navidad", "invierno"],
        2: ["febrero", "san valentín", "san valentin", "invierno"],
        3: ["marzo", "primavera"],
        4: ["abril", "semana santa", "primavera"],
        5: ["mayo", "san isidro", "dos de mayo", "2 de mayo", "primavera"],
        6: ["junio", "verano"],
        7: ["julio", "verano"],
        8: ["agosto", "verano", "fiestas de agosto", "la paloma", "san cayetano", "san lorenzo"],
        9: ["septiembre", "otoño"],
        10: ["octubre", "otoño"],
        11: ["noviembre", "otoño"],
        12: ["diciembre", "navidad", "reyes", "invierno"]
    }

    score = 0

    for palabra in meses.get(MES_ACTUAL, []):
        if palabra in texto:
            score += 18

    if "2026" in texto:
        score += 8

    if "2025" in texto and MES_ACTUAL >= 5:
        score -= 10

    return score


def score_editorial(item):
    score = 50
    titulo = item["titulo"].lower()
    descripcion = item.get("descripcion", "").lower()
    categoria = item["categoria"]
    url = item["url"].lower()
    texto = f"{titulo} {descripcion} {url}"

    if categoria == "trenes_turisticos":
        score += 18

    if categoria == "excursiones":
        score += 15

    if categoria in ["rutas_madrid", "tradicion_cultura"]:
        score += 10

    if categoria in ["parques_jardines", "miradores"]:
        score += 8

    if any(x in texto for x in ["patrimonio", "historia", "histórico", "historico", "cultural", "monumental"]):
        score += 8

    if any(x in texto for x in ["ruta", "paseo", "descubre", "visita", "viaja", "excursión", "excursion"]):
        score += 6

    if any(x in texto for x in ["familia", "niños", "ninos", "romántico", "romantico", "secreto", "atardecer"]):
        score += 4

    if any(x in texto for x in ["fiestas", "san isidro", "festival", "agenda", "programación", "programacion"]):
        score += 20

    if categoria == "trenes_turisticos" and "/agenda/tren-" in url:
        score -= 8

    if any(x in texto for x in KEYWORDS_EXCLUIR):
        score -= 40

    score += boost_mes_actual(texto)

    return min(max(score, 0), 100)



def construir_url_pagina(url, numero_pagina, page_param="page"):
    from urllib.parse import parse_qsl, urlencode

    partes = urlsplit(url)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    query[page_param] = str(numero_pagina)
    nueva_query = urlencode(query, doseq=True)

    return urlunsplit((
        partes.scheme,
        partes.netloc,
        partes.path,
        nueva_query,
        partes.fragment
    ))


def obtener_urls_indice(source):
    url = source["url"]
    paginas = int(source.get("paginas", 1) or 1)
    page_start = int(source.get("page_start", 0) or 0)
    page_param = source.get("page_param", "page")
    page_step = int(source.get("page_step", 1) or 1)

    if paginas <= 1:
        return [url]

    urls = []

    for i in range(paginas):
        numero_pagina = page_start + (i * page_step)

        if page_param == "pagination" and numero_pagina <= 0:
            if i == 0:
                urls.append(url)
            continue

        urls.append(construir_url_pagina(url, numero_pagina, page_param))

    return list(dict.fromkeys(urls))


def obtener_dominios_permitidos(source):
    dominios = source.get("dominios_permitidos")
    if dominios:
        return set(dominios)

    parsed = urlparse(source["url"])
    return {parsed.netloc.lower()}


def es_url_valida_source(url, source):
    categoria = source["categoria"]
    parsed = urlparse(url)

    if parsed.netloc.lower() not in obtener_dominios_permitidos(source):
        return False

    if url in URLS_INDICE:
        return False

    excluir_urls = list(URLS_EXCLUIR)
    excluir_urls.extend(source.get("excluir_urls", []) or [])

    if any(x in url for x in excluir_urls):
        return False

    patrones = source.get("patrones_validos") or PATRONES_VALIDOS.get(categoria, [])

    if not patrones:
        return True

    return any(patron in url for patron in patrones)


def obtener_filtro_listado_href(source):
    filtro = (
        source.get("filtro_listado_href")
        or source.get("filtro_card_href")
        or source.get("filtro_taxonomia_href")
    )

    if filtro:
        return filtro

    filtro_texto = (source.get("filtro_ficha_texto") or "").strip().lower()

    if filtro_texto == "edificios y monumentos":
        return "/taxonomy/term/7173"

    return None


def obtener_filtro_listado_texto(source):
    return (
        source.get("filtro_listado_texto")
        or source.get("filtro_card_texto")
        or source.get("filtro_ficha_texto")
    )


def nodo_contiene_href(nodo, href_parcial):
    if not href_parcial:
        return True

    for a in nodo.select("a[href]"):
        href = html.unescape(a.get("href", ""))
        if href_parcial in href:
            return True

    return False


def nodo_contiene_texto(nodo, texto):
    if not texto:
        return True

    texto_nodo = nodo.get_text(" ", strip=True).lower()
    return texto.lower() in texto_nodo


def anchor_cumple_filtro_listado(anchor, source):
    filtro_href = obtener_filtro_listado_href(source)
    filtro_texto = obtener_filtro_listado_texto(source)

    if not filtro_href and not filtro_texto:
        return True

    max_ancestros = int(source.get("max_ancestros_card", 8) or 8)

    nodo = anchor

    for _ in range(max_ancestros + 1):
        if not nodo or getattr(nodo, "name", None) in {"html", "body"}:
            break

        if nodo_contiene_href(nodo, filtro_href) and nodo_contiene_texto(nodo, filtro_texto):
            return True

        nodo = nodo.parent

    return False


def ficha_cumple_filtro(ficha_soup, source):
    filtro_selector = source.get("filtro_ficha_selector")
    filtro_href = source.get("filtro_ficha_href")
    filtro_texto = source.get("filtro_ficha_texto")

    if filtro_selector:
        nodos = ficha_soup.select(filtro_selector)
        if not nodos:
            return False

        if filtro_texto:
            return any(nodo_contiene_texto(nodo, filtro_texto) for nodo in nodos)

        return True

    if filtro_href:
        return nodo_contiene_href(ficha_soup, filtro_href)

    if filtro_texto:
        texto = ficha_soup.get_text(" ", strip=True).lower()
        return filtro_texto.lower() in texto

    return True



def normalizar_href_taxonomia(href):
    href = html.unescape(href or "")
    href, _ = urldefrag(href)
    return href.rstrip("/")


def soup_tiene_taxonomia_exacta(soup, taxonomia_href):
    if not taxonomia_href:
        return True

    taxonomia_href = normalizar_href_taxonomia(taxonomia_href)

    for a in soup.select("div.field-item a[href], a[href]"):
        href = normalizar_href_taxonomia(a.get("href", ""))

        if href == taxonomia_href:
            return True

        if href.startswith("http"):
            parsed = urlparse(href)
            href_path = parsed.path.rstrip("/")
            if href_path == taxonomia_href:
                return True

    return False



def obtener_tipo_principal_ficha(ficha_soup):
    selectors = [
        ".field-name-field-tipo",
        ".field--name-field-tipo",
        ".field-name-field-type",
        ".field--name-field-type"
    ]

    for selector in selectors:
        bloque = ficha_soup.select_one(selector)
        if not bloque:
            continue

        enlaces = [
            a.get_text(" ", strip=True)
            for a in bloque.select("a")
            if a.get_text(" ", strip=True)
        ]

        if enlaces:
            return enlaces[0]

        textos = [
            texto.strip()
            for texto in bloque.stripped_strings
            if texto.strip()
        ]

        textos_limpios = [
            texto
            for texto in textos
            if texto.lower() not in {"tipo", "tipo:"}
        ]

        if textos_limpios:
            return textos_limpios[0]

    for bloque in ficha_soup.select(".field, .field-item, .field__item"):
        texto_bloque = bloque.get_text(" ", strip=True).lower()
        if "tipo" not in texto_bloque:
            continue

        for a in bloque.select("a"):
            texto = a.get_text(" ", strip=True)
            if texto:
                return texto

    lineas = [
        linea.strip()
        for linea in ficha_soup.get_text("\n", strip=True).splitlines()
        if linea.strip()
    ]

    inicio = 0
    for i, linea in enumerate(lineas):
        if linea.lower() in {"datos de interés", "datos de interes"}:
            inicio = i
            break

    fin = len(lineas)
    cortes = {
        "cerca",
        "te interesara",
        "te interesará",
        "descubre el barrio",
        "productos oficiales",
        "publicidad"
    }

    for i in range(inicio + 1, len(lineas)):
        if lineas[i].strip().lower() in cortes:
            fin = i
            break

    bloque = lineas[inicio:fin]

    for i, linea in enumerate(bloque):
        if linea.strip().lower() in {"tipo", "tipo:"}:
            for siguiente in bloque[i + 1:]:
                valor = siguiente.strip()
                if valor:
                    return valor

    return ""


def ficha_cumple_tipo_principal(ficha_soup, tipo_esperado):
    if not tipo_esperado:
        return True

    tipo_real = obtener_tipo_principal_ficha(ficha_soup)

    if not tipo_real:
        return False

    return tipo_real.strip().lower() == tipo_esperado.strip().lower()

def ficha_cumple_filtro_estricto(ficha_soup, source):
    tipo_esperado = source.get("filtro_ficha_tipo_texto")

    if tipo_esperado:
        return ficha_cumple_tipo_principal(ficha_soup, tipo_esperado)

    taxonomia_href = source.get("filtro_ficha_taxonomia_href")

    if taxonomia_href:
        return soup_tiene_taxonomia_exacta(ficha_soup, taxonomia_href)


    filtro_selector = source.get("filtro_ficha_selector")
    filtro_href = source.get("filtro_ficha_href")
    filtro_texto = source.get("filtro_ficha_texto")

    if filtro_selector:
        nodos = ficha_soup.select(filtro_selector)
        if not nodos:
            return False

        if filtro_href:
            return any(nodo_contiene_href(nodo, filtro_href) for nodo in nodos)

        if filtro_texto:
            return any(nodo_contiene_texto(nodo, filtro_texto) for nodo in nodos)

        return True

    if filtro_href:
        return nodo_contiene_href(ficha_soup, filtro_href)

    if filtro_texto:
        texto = ficha_soup.get_text(" ", strip=True).lower()
        return filtro_texto.lower() in texto

    return True


def source_exige_filtro_ficha(source):
    return any([
        source.get("filtro_ficha_tipo_texto"),
        source.get("filtro_ficha_taxonomia_href"),
        source.get("filtro_ficha_selector"),
        source.get("filtro_ficha_href"),
        source.get("filtro_ficha_texto")
    ])


def normalizar_simple(texto):
    return " ".join((texto or "").strip().lower().split())


def bloque_resultado_cumple_tipo(anchor, tipo_esperado):
    if not tipo_esperado:
        return True

    tipo_esperado_norm = normalizar_simple(tipo_esperado)

    nodo = anchor

    for _ in range(10):
        if not nodo or getattr(nodo, "name", None) in {"html", "body"}:
            break

        texto = nodo.get_text("\n", strip=True)
        lineas = [
            linea.strip()
            for linea in texto.splitlines()
            if linea.strip()
        ]

        for i, linea in enumerate(lineas):
            if normalizar_simple(linea) in {"tipo", "tipo:"}:
                ventana = lineas[i + 1:i + 4]
                tipos = [
                    normalizar_simple(valor)
                    for valor in ventana
                    if normalizar_simple(valor)
                ]

                if tipo_esperado_norm in tipos:
                    return True

                if tipos:
                    return False

        nodo = nodo.parent

    return False


def anchor_cumple_filtro_listado_estricto(anchor, source):
    tipo_esperado = source.get("filtro_listado_tipo_texto")

    if tipo_esperado:
        return bloque_resultado_cumple_tipo(anchor, tipo_esperado)

    return anchor_cumple_filtro_listado(anchor, source)

def scrape_categoria(source):
    url = source["url"]
    categoria = source["categoria"]
    fuente = source.get("fuente", "desconocida")
    max_enlaces = int(source.get("max_enlaces", 120) or 120)
    max_fichas = int(source.get("max_fichas", max_enlaces) or max_enlaces)
    timeout_indice = source.get("timeout", 12)
    timeout_ficha = source.get("timeout_ficha", 10)
    selector_links = source.get("selector_links", "a[href]")
    score_minimo = int(source.get("score_minimo", 35) or 35)

    print(f"🔎 Scrapeando {categoria} ({fuente})...")

    try:
        candidatos = []
        vistos = set()
        urls_indice = obtener_urls_indice(source)

        for num_pagina, url_indice in enumerate(urls_indice, start=1):
            print(f"   📄 Página índice {num_pagina}/{len(urls_indice)}")

            response = requests.get(url_indice, headers=HEADERS, timeout=timeout_indice)

            if response.status_code == 429:
                espera = source.get("sleep_429_indice_segundos", 15)
                print(f"⏳ 429 en índice, esperando {espera}s y saltando página...")
                time.sleep(espera)
                continue

            response.raise_for_status()

            sleep_indice = source.get("sleep_indice_segundos", 0)
            if sleep_indice:
                time.sleep(sleep_indice)

            soup = BeautifulSoup(response.text, "html.parser")

            for a in soup.select(selector_links):
                href = a.get("href")
                titulo = a.get_text(" ", strip=True)

                if not href or not titulo:
                    continue

                url_completa = limpiar_url(href, url_indice)

                if url_completa in vistos:
                    continue

                if not es_url_valida_source(url_completa, source):
                    continue

                if not es_titulo_valido(titulo):
                    continue

                if not anchor_cumple_filtro_listado_estricto(a, source):
                    continue

                vistos.add(url_completa)
                candidatos.append((titulo, url_completa))

                if len(candidatos) >= max_enlaces:
                    break

            if len(candidatos) >= max_enlaces:
                break

        for titulo_semilla, url_semilla in SEMILLAS_OBLIGATORIAS.get(categoria, []):
            url_semilla = limpiar_url(url_semilla, url)

            if url_semilla in vistos:
                continue

            if not es_url_valida_source(url_semilla, source):
                continue

            vistos.add(url_semilla)
            candidatos.append((titulo_semilla, url_semilla))

        candidatos = candidatos[:max_enlaces]

        items = []

        for idx, (titulo, url_item) in enumerate(candidatos[:max_fichas], start=1):
            print(f"   [{categoria}] candidato {idx}/{len(candidatos[:max_fichas])}: {titulo}")

            try:
                ficha = requests.get(url_item, headers=HEADERS, timeout=timeout_ficha)

                if ficha.status_code == 429:
                    espera = source.get("sleep_429_ficha_segundos", 8)
                    print(f"⏳ 429 en ficha, esperando {espera}s y saltando: {url_item}")
                    time.sleep(espera)
                    continue

                ficha.raise_for_status()

                sleep_ficha = source.get("sleep_segundos", 0)
                if sleep_ficha:
                    time.sleep(sleep_ficha)

                ficha_soup = BeautifulSoup(ficha.text, "html.parser")

                if source_exige_filtro_ficha(source):
                    if not ficha_cumple_filtro_estricto(ficha_soup, source):
                        continue

                titulo_real = obtener_titulo_real(ficha_soup, titulo, source)
                descripcion = obtener_descripcion(ficha_soup, source)

            except Exception:
                if source_exige_filtro_ficha(source):
                    continue

                titulo_real = titulo
                descripcion = ""

            if not es_titulo_valido(titulo_real):
                continue

            item = {
                "id": generar_id(url_item),
                "titulo": titulo_real,
                "url": url_item,
                "fuente": fuente,
                "categoria": categoria,
                "intencion": source.get("intencion") or mapear_intencion(categoria),
                "tipo_contenido": "individual",
                "pagina_padre": url,
                "descripcion": descripcion
            }

            item["score_editorial"] = score_editorial(item)

            if item["score_editorial"] < score_minimo:
                continue

            items.append(item)
            print(f"      ✅ aceptado: {item['titulo']}")

        print(f"   → {len(items)} items")
        return items

    except KeyboardInterrupt:
        raise

    except Exception as e:
        print(f"❌ Error en {categoria}: {e}")
        return []


def deduplicar(items):
    por_url = {}

    for item in items:
        url = item["url"]

        if url not in por_url:
            por_url[url] = item
            continue

        if item["score_editorial"] > por_url[url]["score_editorial"]:
            por_url[url] = item

    return list(por_url.values())


def generar_dataset():
    sources = cargar_sources()
    resultados = []

    for source in sources:
        resultados.extend(scrape_categoria(source))

    resultados = deduplicar(resultados)
    resultados = sorted(resultados, key=lambda x: x["score_editorial"], reverse=True)

    print(f"\n✅ TOTAL SCRAPEADO LIMPIO: {len(resultados)} items")
    return resultados


def guardar_master(items):
    with open("evergreen_master.json", "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

    print(f"💾 Guardado evergreen_master.json ({len(items)} items)")


def agrupar_y_rankear(items):
    """
    Genera una vista agrupada del master para consumir desde frontend/API.

    No hace selección editorial ni recorta resultados. Mantiene todos los items,
    pero los organiza por intención y, dentro de cada intención, por categoría.
    """
    orden_intenciones = [
        "viaje",
        "rutas",
        "castillos",
        "yacimientos",
        "monumentos",
        "naturaleza",
        "ocio",
        "barrios",
        "cultura",
        "otros"
    ]

    orden_categorias = {
        "viaje": ["excursiones", "trenes_turisticos", "imprescindibles_extremadura"],
        "rutas": ["rutas_madrid", "rutas_historicas_clm"],
        "castillos": ["castillos_clm"],
        "yacimientos": ["arqueologia_clm"],
        "monumentos": ["edificios_historicos"],
        "naturaleza": ["parques_jardines", "miradores"],
        "ocio": ["planes_madrid"],
        "barrios": ["barrios"],
        "cultura": ["tradicion_cultura"],
        "otros": ["otros"]
    }

    grupos = defaultdict(lambda: defaultdict(list))

    items_output = []
    items_ocultos_temporada = []

    for item in items:
        if esta_fuera_de_temporada(item):
            items_ocultos_temporada.append(item)
            continue

        items_output.append(item)

        intencion = item.get("intencion", "otros")
        categoria = item.get("categoria", "otros")
        grupos[intencion][categoria].append(item)

    if items_ocultos_temporada:
        print(f"🗓️ Ocultados del output por estar fuera de temporada: {len(items_ocultos_temporada)}")
        for item in items_ocultos_temporada:
            print(f"   - {item.get('titulo')} ({item.get('categoria')})")

    resultado = []

    intenciones_presentes = [i for i in orden_intenciones if i in grupos]
    intenciones_extra = sorted(i for i in grupos.keys() if i not in orden_intenciones)

    for intencion in intenciones_presentes + intenciones_extra:
        categorias_dict = grupos[intencion]

        categorias_ordenadas = [
            c for c in orden_categorias.get(intencion, [])
            if c in categorias_dict
        ]
        categorias_extra = sorted(
            c for c in categorias_dict.keys()
            if c not in categorias_ordenadas
        )

        categorias_output = []
        total_intencion = 0

        for categoria in categorias_ordenadas + categorias_extra:
            items_categoria = sorted(
                categorias_dict[categoria],
                key=lambda x: x.get("score_editorial", 0),
                reverse=True
            )

            total_intencion += len(items_categoria)

            categorias_output.append({
                "categoria": categoria,
                "total_items": len(items_categoria),
                "items": items_categoria
            })

        resultado.append({
            "intencion": intencion,
            "total_items": total_intencion,
            "categorias": categorias_output
        })

    return resultado


def guardar_output(data):
    with open("evergreen_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("📁 Guardado evergreen_output.json")


if __name__ == "__main__":
    try:
        print("🚀 Generando dataset...\n")

        items = generar_dataset()

        if not items:
            print("❌ No se han obtenido datos")
            exit()

        guardar_master(items)

        print("\n⚙️ Procesando ranking...\n")

        bloques = agrupar_y_rankear(items)

        print(f"\n✅ Bloques generados: {len(bloques)}")

        for bloque in bloques:
            print(f"\n🔹 {bloque['intencion']} ({bloque['total_items']} items)")
            for categoria in bloque["categorias"]:
                print(f"   📂 {categoria['categoria']} ({categoria['total_items']} items)")
                for item in categoria["items"][:5]:
                    print(f"      - {item['titulo']} ({item['score_editorial']})")
                if categoria["total_items"] > 5:
                    print(f"      ... +{categoria['total_items'] - 5} más")

        guardar_output(bloques)

        print("\n🏁 FIN")

    except KeyboardInterrupt:
        print("\n[STOP] Interrumpido por el usuario.")