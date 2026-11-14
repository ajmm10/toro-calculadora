"""Verificador: cuenta cruces de la superficie consigo misma (arista contra triángulo).

La malla se submuestrea cada `paso` filas/columnas. Las filas/columnas 0 y 99
de la malla son la misma (la malla repite la primera al final), así que se
identifican antes de contar para que la costura no cuente como cruce.
"""
import csv
import numpy as np

from pathlib import Path

R = str(Path(__file__).parent) + "/"
N = 100


def cargar(nombre):
    with open(R + nombre) as f:
        return np.array([[float(r[k]) for k in "xyz"] for r in csv.DictReader(f)]).reshape(N, N, 3)


def topologia(paso):
    """Índices únicos de vértices (toro periódico) y triángulos/aristas."""
    idx = np.arange(0, N - 1, paso)
    m = len(idx)
    ids = np.arange(m * m).reshape(m, m)
    tris, aristas = [], set()
    for i in range(m):
        for j in range(m):
            a, b = ids[i, j], ids[i, (j + 1) % m]
            c, d = ids[(i + 1) % m, j], ids[(i + 1) % m, (j + 1) % m]
            tris += [(a, c, b), (b, c, d)]
            for e in ((a, b), (a, c), (b, c)):
                aristas.add(tuple(sorted(e)))
    return idx, np.array(tris), np.array(sorted(aristas))


def cruces(P, paso=3, detalle=False):
    """P: (N,N,3). Devuelve el número de pares arista-triángulo que se cruzan."""
    idx, tris, aristas = topologia(paso)
    V = P[np.ix_(idx, idx)].reshape(-1, 3)
    A, B = V[tris[:, 0]], V[tris[:, 1]]
    C = V[tris[:, 2]]
    e1, e2 = B - A, C - A
    total, pares = 0, []
    for k in range(0, len(aristas), 150):
        ar = aristas[k:k + 150]
        p0, p1 = V[ar[:, 0]][:, None, :], V[ar[:, 1]][:, None, :]
        d = p1 - p0
        h = np.cross(d, e2[None])
        a = np.einsum('etc,tc->et', h, e1)
        ok = np.abs(a) > 1e-12
        f = np.where(ok, 1.0 / np.where(ok, a, 1), 0)
        s = p0 - A[None]
        u = f * np.einsum('etc,etc->et', s, h)
        q = np.cross(s, e1[None])
        v = f * np.einsum('etc,etc->et', d, q)
        t = f * np.einsum('etc,etc->et', e2[None], q)
        eps = 1e-6
        golpe = ok & (u > eps) & (v > eps) & (u + v < 1 - eps) & (t > eps) & (t < 1 - eps)
        # arista y triángulo que comparten un vértice no cuentan
        comp = ((ar[:, 0][:, None] == tris[:, 0][None]) | (ar[:, 0][:, None] == tris[:, 1][None]) | (ar[:, 0][:, None] == tris[:, 2][None])
                | (ar[:, 1][:, None] == tris[:, 0][None]) | (ar[:, 1][:, None] == tris[:, 1][None]) | (ar[:, 1][:, None] == tris[:, 2][None]))
        golpe &= ~comp
        total += int(golpe.sum())
        if detalle:
            for e, t_ in zip(*np.nonzero(golpe)):
                pares.append((tuple(ar[e]), int(t_)))
    return (total, pares) if detalle else total


if __name__ == "__main__":
    D, T = cargar("modelo_3d.csv"), cargar("modelo_taza.csv")
    print("taza sola:", cruces(T), "· dona sola:", cruces(D))
    for t in [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1]:
        print(f"t={t:.1f}  cruces={cruces((1 - t) * D + t * T)}")
