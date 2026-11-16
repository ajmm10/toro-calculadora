"""POST /operaciones/morph: la matemática del morph dona → taza.

Cada prueba compara contra los fotogramas o los CSV, no contra la propia
implementación: si se invierte el peso de la interpolación, se toma el
fotograma equivocado o se pierde un vértice, alguna falla.
"""

import csv
import math
from array import array
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
FOTOGRAMAS_BIN = RAIZ / "calculadora_matrices" / "morph_frames.bin"
TAZA_CSV = RAIZ / "modelotoro" / "modelo_taza.csv"
N = 100 * 100


def fotograma(i: int) -> list[list[float]]:
    datos = array("f")
    datos.frombytes(FOTOGRAMAS_BIN.read_bytes())
    plano = datos[i * N * 3:(i + 1) * N * 3]
    return [list(plano[k:k + 3]) for k in range(0, len(plano), 3)]


def total_fotogramas() -> int:
    return FOTOGRAMAS_BIN.stat().st_size // (N * 3 * 4)


def distancia_max(a, b) -> float:
    assert len(a) == len(b)
    return max(abs(x - y) for p, q in zip(a, b, strict=True) for x, y in zip(p, q, strict=True))


def morph(cliente, t, resolucion=100):
    r = cliente.post("/operaciones/morph", json={"t": t, "resolucion": resolucion})
    assert r.status_code == 200, r.text
    return r.json()


def test_t0_es_el_primer_fotograma(cliente):
    assert distancia_max(morph(cliente, 0)["vertices"], fotograma(0)) < 1e-6


def test_t1_es_la_taza(cliente):
    with TAZA_CSV.open() as f:
        taza = [[float(r["x"]), float(r["y"]), float(r["z"])] for r in csv.DictReader(f)]
    assert distancia_max(morph(cliente, 1)["vertices"], taza) < 1e-5


def test_t_intermedio_interpola_entre_fotogramas_vecinos(cliente):
    n = total_fotogramas()
    # t que cae a un cuarto del camino entre los fotogramas 10 y 11
    t = (10 + 0.25) / (n - 1)
    esperado = [
        [0.75 * a + 0.25 * b for a, b in zip(p, q, strict=True)]
        for p, q in zip(fotograma(10), fotograma(11), strict=True)
    ]
    assert distancia_max(morph(cliente, t)["vertices"], esperado) < 1e-5


@pytest.mark.parametrize("t", [0, 0.013, 0.5, 0.987, 1])
@pytest.mark.parametrize("resolucion", [2, 37, 100])
def test_misma_cantidad_de_vertices_para_cualquier_t(cliente, t, resolucion):
    datos = morph(cliente, t, resolucion)
    assert datos["count"] == resolucion ** 2
    assert len(datos["vertices"]) == resolucion ** 2


def test_el_morph_es_continuo(cliente):
    # Con interpolación lineal entre vecinos, un paso h de t mueve cada vértice
    # a lo más h·(n−1) veces el mayor salto entre dos fotogramas seguidos.
    # Un salto de fotograma, un peso invertido o un índice mal calculado lo rompen.
    n = total_fotogramas()
    salto = max(distancia_max(fotograma(i), fotograma(i + 1)) for i in range(n - 1))
    h = 1e-3
    for t in (0.1, 0.48, 0.9, 1 - h):
        a = morph(cliente, t)["vertices"]
        b = morph(cliente, t + h)["vertices"]
        assert distancia_max(a, b) <= h * (n - 1) * salto + 1e-6


def test_submalla_conserva_las_esquinas(cliente):
    completa = morph(cliente, 0.3)["vertices"]
    esquinas = morph(cliente, 0.3, resolucion=2)["vertices"]
    esperado = [completa[0], completa[99], completa[9900], completa[9999]]
    assert distancia_max(esquinas, esperado) < 1e-9


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"t": -0.01},
        {"t": 1.01},
        {"t": "nan"},
        {"t": "inf"},
        {"t": 0.5, "resolucion": 1},
        {"t": 0.5, "resolucion": 101},
        {"t": 0.5, "resolucion": 10**9},
        {},
    ],
)
def test_entradas_fuera_de_rango_dan_422(cliente, cuerpo):
    assert cliente.post("/operaciones/morph", json=cuerpo).status_code == 422


def test_openapi_documenta_los_rangos(cliente):
    esquema = cliente.get("/openapi.json").json()["components"]["schemas"]["MorphParams"]
    t, res = esquema["properties"]["t"], esquema["properties"]["resolucion"]
    assert (t["minimum"], t["maximum"]) == (0, 1)
    assert (res["minimum"], res["maximum"]) == (2, 100)


def test_no_hay_nan_en_ningun_fotograma(cliente):
    for t in (0, 0.25, 0.5, 0.75, 1):
        assert all(math.isfinite(c) for v in morph(cliente, t, 20)["vertices"] for c in v)
