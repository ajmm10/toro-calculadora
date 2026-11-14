"""Genera morph_frames.bin y modelo_taza.csv: el morph dona → taza sin cruces.

La taza de destino es la nube de puntos `taza_3d_10000_puntos.csv`. Esos puntos
vienen sin orden, así que no se pueden interpolar uno a uno con la dona ni
formar una superficie por sí solos. Se resuelve en tres pasos:

  1. Se ajusta una taza paramétrica (ver `generar_taza.py`) a las medidas de la
     nube: radio, altura, grosor de la pared, piso y asa.
  2. Se recorre un camino de formas intermedias válidas, de la dona a esa
     taza, que se guardan como fotogramas (el visualizador interpola entre
     fotogramas vecinos). Interpolar la dona hacia la taza en línea recta
     haría que la superficie se atravesara a sí misma; este camino no.

        a. dona → tubo con asa en lazo (mismas filas y mismo ángulo de sección
           en cada vértice, así que basta con interpolar en línea recta)
        b. tubo con asa en lazo → taza: el asa se desliza desde los polos hasta
           la pared, la unión se achica, el asa se afina y se abre la boca

  3. En el último fotograma cada vértice de la malla pasa a un punto real de la
     nube: el más cercano que siga libre y, si no lo hay a poca distancia, el
     más cercano aunque ya esté en uso. Así t = 1 son las coordenadas de la taza
     (un subconjunto de sus puntos, con algunos repetidos) y la malla sigue
     siendo la de la dona.

Cada fotograma y varios puntos entre fotogramas se verifican con
`verificar_cruces.py`. Si algo de los pasos 1 y 2 se cruza, el script se detiene
sin escribir nada. El último tramo (taza ajustada → nube) no puede garantizarse:
los puntos de la nube no están alineados con la malla, así que se informa cuántos
cruces locales hay.

Requiere numpy (solo este script; el servicio no lo usa):

    python generar_morph.py
"""

import csv
import math
import sys
from pathlib import Path

import numpy as np

import generar_taza as g
from verificar_cruces import cruces

AQUI = Path(__file__).parent
NUBE_CSV = AQUI / "taza_3d_10000_puntos.csv"
TRAMO_DONA = 10          # intervalos del tramo a (dona → tubo)
TRAMO_TAZA = 30          # y del tramo b (tubo → taza)

# Medidas de la nube (unidades de la nube). R_INT, PISO y el asa se midieron a
# partir de la nube: pared entre 3.8 y 4.2, piso de 0.5, asa de radio ≈ 0.7.
R_EXT_NUBE, R_INT_NUBE, PISO_NUBE = 4.2, 3.8, 0.5
ASA = dict(y_asa=0.68, rho_union=0.20, rho_asa=0.23, wx=0.60, k_union=1.0, k_w=2.0)

# Estado de partida del tramo b: el cuerpo es un tubo y el asa sale por los polos
POLOS = g.Params(x0=-2.0, tau=0.0, rho_union=1.1, rho_asa=0.5,
                 wx=4.5, k_union=8.0, k_w=4.0, cavidad=0.0)
# En qué parte del tramo b (de 0 a 1) cambia cada parámetro
VENTANAS = {"rho_union": (0.0, 0.5), "rho_asa": (0.0, 0.6), "tau": (0.25, 0.85),
            "x0": (0.2, 1.0), "wx": (0.25, 0.85), "k_union": (0.25, 0.85),
            "k_w": (0.25, 0.85), "cavidad": (0.85, 1.0)}


def cargar_nube() -> np.ndarray:
    with NUBE_CSV.open() as f:
        filas = list(csv.reader(f))[1:]
    return np.array([[float(v) for v in fila[:3]] for fila in filas])


def a_visualizador(nube: np.ndarray) -> np.ndarray:
    """Pone la nube con y hacia arriba y centrada, como la ve el visualizador."""
    zc = (nube[:, 2].min() + nube[:, 2].max()) / 2
    cuerpo = nube[(nube[:, 2] > 3) & (nube[:, 2] < 7) & (nube[:, 0] < 3.0)]
    A = np.c_[2 * cuerpo[:, 0], 2 * cuerpo[:, 1], np.ones(len(cuerpo))]
    cx, cy, _ = np.linalg.lstsq(A, (cuerpo[:, :2] ** 2).sum(1), rcond=None)[0]
    return np.c_[nube[:, 0] - cx, nube[:, 2] - zc, -(nube[:, 1] - cy)]


def configurar_taza(nube_v: np.ndarray) -> tuple[float, g.Params]:
    """Ajusta la taza paramétrica a la nube. Devuelve la escala y los parámetros finales."""
    escala = R_EXT_NUBE / 1.25                      # la taza paramétrica trabaja con R = 1.25
    alto = nube_v[:, 1].max() - nube_v[:, 1].min()
    media = alto / 2 / escala
    g.configurar(r_ext=1.25, r_int=R_INT_NUBE / escala,
                 y_base=-media, y_borde=media, y_piso=-media + PISO_NUBE / escala,
                 y_asa=ASA["y_asa"],
                 filetes=dict(base=0.30 / escala, borde_ext=0.15 / escala,
                              borde_int=0.15 / escala, piso=0.30 / escala))
    final = g.replace(g.TAZA, x0=0.0, rho_union=ASA["rho_union"], rho_asa=ASA["rho_asa"],
                      wx=ASA["wx"], k_union=ASA["k_union"], k_w=ASA["k_w"])
    return escala, final


def params(m: float, final: g.Params) -> g.Params:
    d = {}
    for nombre, (a, b) in VENTANAS.items():
        w = g.suave((m - a) / (b - a))
        d[nombre] = getattr(POLOS, nombre) + (getattr(final, nombre) - getattr(POLOS, nombre)) * w
    return g.Params(**d)


def dona_alineada(tubo: np.ndarray) -> np.ndarray:
    """Dona (R = 2, r = 1) con un vértice por cada vértice del tubo: el que tiene
    su mismo ángulo de sección y su misma posición a lo largo del lazo."""
    n = tubo.shape[0]
    centros = tubo.mean(axis=1)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(centros, axis=0), axis=1))])
    s /= s[-1]
    medio = centros[:-1].mean(axis=0)
    u0 = math.pi + 2 * math.pi * s[g.NB // 2]      # el cuerpo queda en el lado izquierdo
    dona = np.zeros_like(tubo)
    for k in range(n):
        a = centros[k - 1] if k > 0 else centros[n - 2]
        b = centros[k + 1] if k < n - 1 else centros[1]
        T = b - a
        T[2] = 0
        T /= np.linalg.norm(T)
        normal = np.array([-T[1], T[0], 0.0])
        if np.dot(centros[k] - medio, normal) < 0:     # que apunte hacia afuera del lazo
            normal = -normal
        u = u0 - 2 * math.pi * s[k]                    # el lazo va en sentido horario
        d = tubo[k] - centros[k]
        v = np.arctan2(d[:, 2], d @ normal)
        dona[k, :, 0] = (2 + np.cos(v)) * math.cos(u)
        dona[k, :, 1] = (2 + np.cos(v)) * math.sin(u)
        dona[k, :, 2] = np.sin(v)
    return dona


def vecinos(A: np.ndarray, B: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Para cada punto de A, los índices y distancias de sus k más cercanos en B."""
    idx = np.empty((len(A), k), dtype=np.int64)
    dist = np.empty((len(A), k))
    for i in range(0, len(A), 400):
        d = np.sqrt(((A[i:i + 400, None, :] - B[None]) ** 2).sum(-1))
        p = np.argpartition(d, k, axis=1)[:, :k]
        pd = np.take_along_axis(d, p, axis=1)
        o = np.argsort(pd, axis=1)
        idx[i:i + 400] = np.take_along_axis(p, o, axis=1)
        dist[i:i + 400] = np.take_along_axis(pd, o, axis=1)
    return idx, dist


def asignar_nube(plantilla: np.ndarray, nube: np.ndarray, radio: float = 0.45) -> np.ndarray:
    """Lleva cada vértice de la malla a un punto de la nube.

    Los vértices únicos son las filas y columnas 0 … N-2 (la última fila y la
    última columna repiten la primera). Primero se reparten los puntos de uno en
    uno, de menor a mayor distancia, solo entre vértices y puntos que estén a
    menos de `radio`. A los vértices que quedan sin punto (donde la malla es más
    densa que la nube, como en el asa) se les da el más cercano aunque otro
    vértice ya lo use: un vértice nunca viaja lejos, a costa de repetir algunos
    puntos y no usar otros.
    """
    n = g.N - 1
    unicos = plantilla[:n, :n].reshape(-1, 3)
    idx, dist = vecinos(unicos, nube, 12)
    asignado = np.full(len(unicos), -1, dtype=np.int64)
    usados = np.zeros(len(nube), dtype=bool)
    for e in np.argsort(dist, axis=None):                     # pares de menor a mayor distancia
        v, c = divmod(int(e), idx.shape[1])
        if dist[v, c] > radio:
            break
        p = idx[v, c]
        if asignado[v] < 0 and not usados[p]:
            asignado[v], usados[p] = p, True
    libres = asignado < 0
    asignado[libres] = idx[libres, 0]                         # el más cercano, repetido o no

    salida = np.zeros_like(plantilla)
    salida[:n, :n] = nube[asignado].reshape(n, n, 3)
    salida[:n, n] = salida[:n, 0]                             # última columna = primera
    salida[n] = salida[0]                                     # última fila = primera
    return salida


def main() -> None:
    nube = a_visualizador(cargar_nube())
    escala, final = configurar_taza(nube)
    tabla = g.tabla_uniforme(final)
    print(f"escala {escala:.3f}; tubo con asa en lazo y taza…", flush=True)

    tubo = np.array(g.malla(params(0.0, final), tabla))
    dona = dona_alineada(tubo)
    claves = [(1 - t) * dona + t * tubo for t in np.linspace(0, 1, TRAMO_DONA + 1)]
    for i in range(1, TRAMO_TAZA + 1):
        m = i / TRAMO_TAZA
        s = 1 + (escala - 1) * g.suave(m)                      # la taza crece hasta su tamaño
        claves.append(s * np.array(g.malla(params(m, final), tabla)))

    print(f"{len(claves)} fotogramas; verificando cruces…", flush=True)
    malos = []
    for i, f in enumerate(claves):
        if not np.isfinite(f).all() or cruces(f):
            malos.append((i, "fotograma"))
        if i + 1 < len(claves):
            for t in (0.25, 0.5, 0.75):
                if cruces((1 - t) * f + t * claves[i + 1]):
                    malos.append((i, f"entre {i} y {i + 1}, t={t}"))
    if malos:
        sys.exit(f"HAY CRUCES, no se escribe nada: {malos}")

    print("asignando los puntos de la nube…", flush=True)
    taza = asignar_nube(claves[-1], nube)
    mov = np.linalg.norm((taza - claves[-1]).reshape(-1, 3), axis=1)
    cruces_final = cruces(taza)
    cruces_ultimo = [cruces((1 - t) * claves[-1] + t * taza) for t in (0.25, 0.5, 0.75)]
    claves.append(taza)

    datos = np.stack(claves).astype("<f4")
    (AQUI / "morph_frames.bin").write_bytes(datos.tobytes())
    with (AQUI / "modelo_taza.csv").open("w", newline="") as f:
        f.write("x,y,z\n")
        for x, y, z in taza.reshape(-1, 3):
            f.write(f"{float(x)!r},{float(y)!r},{float(z)!r}\n")
    distintos = len(np.unique(taza.reshape(-1, 3).round(9), axis=0))
    print(f"morph_frames.bin: {datos.shape[0]} fotogramas × {datos.shape[1] * datos.shape[2]} vértices "
          f"({datos.nbytes / 1e6:.1f} MB)\n"
          f"  fotogramas de la dona a la taza ajustada: 0 cruces\n"
          f"  último tramo (taza ajustada → nube): cruces en t=.25/.5/.75 = {cruces_ultimo}, "
          f"en la nube = {cruces_final}\n"
          f"  los vértices se mueven {mov.mean():.2f} en promedio (máx {mov.max():.2f}); "
          f"puntos distintos de la nube usados: {distintos} de {len(nube)}")


if __name__ == "__main__":
    main()
