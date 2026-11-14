"""Morph dona → taza: vértices de la forma intermedia para un t dado.

La dona y la taza comparten la misma malla de 100 × 100 sobre el dominio
(u, v) del toro. La interpolación recta P = (1 − t)·D + t·T hace que la
superficie se atraviese a sí misma (hasta 762 cruces en t = 0.6), así que
el morph es una secuencia de fotogramas válidos (generados y verificados
offline por modelotoro/generar_morph.py) y aquí se interpola solo entre
fotogramas vecinos:

    f = t · (n − 1),   i = ⌊f⌋,   a = f − i
    P(t) = (1 − a) · F[i] + a · F[i + 1]

El primer fotograma es la dona (t = 0) y el último la taza (t = 1). Como
todos los fotogramas tienen los mismos vértices, la malla es la misma para
cualquier t: lo único que cambia son las posiciones.

`resolucion` toma una submalla de resolucion × resolucion de la malla
completa, con las filas y columnas de los extremos incluidas: en la malla
del toro el último índice coincide con el primero (u y v dan la vuelta
completa), así que la submalla sigue cerrada.
"""

import sys
from array import array
from pathlib import Path

ARCHIVO_FOTOGRAMAS = Path(__file__).parent / "morph_frames.bin"
GRID_COMPLETA = 100
VERTICES = GRID_COMPLETA * GRID_COMPLETA
FLOATS_POR_FOTOGRAMA = VERTICES * 3

RESOLUCION_MIN = 2
RESOLUCION_MAX = GRID_COMPLETA


def _cargar(path: Path) -> array:
    datos = array("f")
    datos.frombytes(path.read_bytes())
    if sys.byteorder != "little":  # el archivo es float32 little-endian
        datos.byteswap()
    if len(datos) % FLOATS_POR_FOTOGRAMA:
        raise RuntimeError(f"{path.name} no contiene un número entero de fotogramas")
    if len(datos) // FLOATS_POR_FOTOGRAMA < 2:
        raise RuntimeError(f"{path.name} necesita al menos dos fotogramas (dona y taza)")
    return datos


_FOTOGRAMAS = _cargar(ARCHIVO_FOTOGRAMAS)
FOTOGRAMAS = len(_FOTOGRAMAS) // FLOATS_POR_FOTOGRAMA


def indices_submalla(resolucion: int) -> list[int]:
    """Índices de fila (o columna) de la malla completa que forman la submalla."""
    if not RESOLUCION_MIN <= resolucion <= RESOLUCION_MAX:
        raise ValueError(
            f"resolucion debe estar entre {RESOLUCION_MIN} y {RESOLUCION_MAX}"
        )
    paso = (GRID_COMPLETA - 1) / (resolucion - 1)
    return [round(k * paso) for k in range(resolucion)]


def vertices(t: float, resolucion: int = GRID_COMPLETA) -> list[list[float]]:
    """Vértices (x, y, z) de la forma intermedia en t, en una malla resolucion²."""
    if not 0.0 <= t <= 1.0:
        raise ValueError("t debe estar entre 0 (dona) y 1 (taza)")
    filas = indices_submalla(resolucion)

    f = t * (FOTOGRAMAS - 1)
    i = min(int(f), FOTOGRAMAS - 2)   # en t = 1 se usa el último tramo con a = 1
    a = f - i
    base0 = i * FLOATS_POR_FOTOGRAMA
    base1 = base0 + FLOATS_POR_FOTOGRAMA
    F = _FOTOGRAMAS

    puntos = []
    for fila in filas:
        for col in filas:
            k = (fila * GRID_COMPLETA + col) * 3
            puntos.append([
                (1 - a) * F[base0 + k + c] + a * F[base1 + k + c] for c in range(3)
            ])
    return puntos
