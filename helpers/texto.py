import re


def normalizar_texto(texto):
    texto = texto.strip().lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto