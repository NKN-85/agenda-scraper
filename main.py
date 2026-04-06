import csv
import json
import urllib3
from datetime import datetime

from eslava import sacar_eslava
from but import sacar_but
from elsol import sacar_elsol
from vistalegre import sacar_vistalegre
from granvia import sacar_granvia
from alcazar import sacar_alcazar
from maravillas import sacar_maravillas
from figaro import sacar_figaro
from pequenogranvia import sacar_pequenogranvia
from capitol import sacar_capitol
from aranjuez import sacar_aranjuez
from matadero import sacar_matadero
from canal import sacar_canal
from riviera import sacar_riviera
from berlin import sacar_berlin
from movistararena import sacar_movistararena
from auditorio import sacar_auditorio

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def guardar_csv(eventos, nombre_archivo="eventos.csv"):
    with open(nombre_archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["TITULO EVENTO", "FECHA", "LUGAR", "URL EVENTO", "FUENTE"])

        for fila in eventos:
            writer.writerow(fila)


def guardar_json(eventos, nombre_archivo="eventos.json"):
    eventos_json = []

    for fila in eventos:
        if len(fila) < 5:
            continue

        titulo, fecha, lugar, url_evento, fuente = fila

        # Validación mínima de fecha esperada en formato dd/mm/yyyy
        if not fecha or "/" not in fecha:
            continue

        partes = fecha.split("/")
        if len(partes) != 3:
            continue

        dia, mes, anio = partes

        # Validación extra por si entra algo raro
        if not (dia.isdigit() and mes.isdigit() and anio.isdigit()):
            continue

        fecha_iso = f"{anio}-{mes.zfill(2)}-{dia.zfill(2)}"

        eventos_json.append({
            "titulo": titulo,
            "fecha": fecha_iso,
            "lugar": lugar,
            "url_evento": url_evento,
            "fuente": fuente
        })

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        json.dump(eventos_json, f, ensure_ascii=False, indent=2)


def clave_orden_fecha(fila):
    if len(fila) < 2:
        return datetime.max

    fecha = fila[1]

    try:
        return datetime.strptime(fecha, "%d/%m/%Y")
    except Exception:
        return datetime.max


def main():
    todos_los_eventos = []

    fuentes = [
        sacar_eslava,
        sacar_but,
        sacar_elsol,
        sacar_vistalegre,
        sacar_granvia,
        sacar_alcazar,
        sacar_maravillas,
        sacar_figaro,
        sacar_pequenogranvia,
        sacar_capitol,
        sacar_aranjuez,
        sacar_matadero,
        sacar_canal,
        sacar_riviera,
        sacar_berlin,
        sacar_movistararena,
        sacar_auditorio,
    ]

    for funcion in fuentes:
        try:
            eventos = funcion()
            todos_los_eventos.extend(eventos)
            print(f"[OK] {funcion.__name__}: {len(eventos)} eventos")
        except Exception as e:
            print(f"[ERROR] {funcion.__name__}: {e}")

    # Ordenar por fecha antes de guardar
    todos_los_eventos.sort(key=clave_orden_fecha)

    guardar_csv(todos_los_eventos)
    guardar_json(todos_los_eventos)

    print("[OK] Archivo eventos.csv generado correctamente")
    print("[OK] Archivo eventos.json generado correctamente")
    print(f"[OK] Total eventos guardados: {len(todos_los_eventos)}")


if __name__ == "__main__":
    main()