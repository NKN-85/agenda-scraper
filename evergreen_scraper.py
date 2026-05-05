import requests
from bs4 import BeautifulSoup
import json
import hashlib
from collections import defaultdict
from urllib.parse import urljoin, urldefrag
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
    "miradores": "naturaleza"
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
    "informacion turistica"
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
    url = urljoin(base_url, url)
    url, _ = urldefrag(url)
    return url.rstrip("/")


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


def obtener_descripcion(soup):
    meta = soup.select_one('meta[name="description"]')
    if meta and meta.get("content"):
        return meta["content"].strip()

    p = soup.select_one("p")
    if p:
        return p.get_text(" ", strip=True)

    return ""


def obtener_titulo_real(soup, fallback):
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


def scrape_categoria(source):
    url = source["url"]
    categoria = source["categoria"]
    fuente = source.get("fuente", "desconocida")
    max_enlaces = source.get("max_enlaces", 120)

    print(f"🔎 Scrapeando {categoria} ({fuente})...")

    try:
        response = requests.get(url, headers=HEADERS, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        candidatos = []
        vistos = set()

        for a in soup.select("a[href]"):
            href = a.get("href")
            titulo = a.get_text(" ", strip=True)

            if not href or not titulo:
                continue

            url_completa = limpiar_url(href, url)

            if url_completa in vistos:
                continue

            if not es_url_valida(url_completa, categoria):
                continue

            if not es_titulo_valido(titulo):
                continue

            vistos.add(url_completa)
            candidatos.append((titulo, url_completa))

        # Añade semillas internas obligatorias para categorías donde esmadrid
        # a veces cambia el HTML de las cards o deja anchors con poco texto.
        # No abre dominios externos y no sustituye al scraping: solo garantiza
        # fichas evergreen clave que sabemos que pertenecen a esta categoría.
        for titulo_semilla, url_semilla in SEMILLAS_OBLIGATORIAS.get(categoria, []):
            url_semilla = limpiar_url(url_semilla, url)
            if url_semilla in vistos:
                continue
            if not es_url_valida(url_semilla, categoria):
                continue
            vistos.add(url_semilla)
            candidatos.append((titulo_semilla, url_semilla))

        candidatos = candidatos[:max_enlaces]

        items = []

        for idx, (titulo, url_item) in enumerate(candidatos, start=1):
            print(f"   [{categoria}] propuesta {idx}/{len(candidatos)}: {titulo}")

            try:
                ficha = requests.get(url_item, headers=HEADERS, timeout=10)
                ficha.raise_for_status()
                ficha_soup = BeautifulSoup(ficha.text, "html.parser")

                titulo_real = obtener_titulo_real(ficha_soup, titulo)
                descripcion = obtener_descripcion(ficha_soup)

            except Exception:
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
                "intencion": mapear_intencion(categoria),
                "tipo_contenido": "individual",
                "pagina_padre": url,
                "descripcion": descripcion
            }

            item["score_editorial"] = score_editorial(item)

            if item["score_editorial"] < 35:
                continue

            items.append(item)

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
    orden_intenciones = ["viaje", "cultura", "ocio", "naturaleza", "barrios", "otros"]

    orden_categorias = {
        "viaje": ["trenes_turisticos", "excursiones"],
        "cultura": ["rutas_madrid", "tradicion_cultura"],
        "ocio": ["planes_madrid"],
        "naturaleza": ["parques_jardines", "miradores"],
        "barrios": ["barrios"],
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