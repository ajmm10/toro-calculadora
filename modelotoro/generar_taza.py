"""Familia paramétrica de tazas con asa sobre la malla 100×100 de la dona.

Una taza con asa es una esfera (el cuerpo) con un asa pegada, y eso es un toro.
Se parte en dos cilindros pegados por dos circunferencias de unión:

    cuerpo = esfera sin dos discos (donde se pega el asa)   → filas 0 … NB
    asa    = tubo entre esos dos discos                      → filas NB … N-1

Las filas NB y N-1 (= 0, porque la malla de la dona repite la primera fila al
final) son las uniones; las comparten el cuerpo y el asa.

La malla depende de unos pocos parámetros (ver `Params`) y varía de forma
continua con ellos. `generar_morph.py` recorre esa familia desde una dona hasta
la taza final, y comprueba en cada paso que la superficie no se atraviesa.

Cuerpo. Es una superficie de revolución: base, pared recta, borde y, según
`cavidad`, o una tapa plana (cavidad = 0, "lata") o la boca con pared interior
y piso (cavidad = 1, taza). El perfil tiene dos tramos: el de la base y la
pared, que no cambia, y el de arriba, que se mezcla entre la tapa y la boca.
Las filas del cuerpo van de una unión a la otra con coordenadas bipolares sobre
la esfera: con ζ = (z − zB)/(z − zA), las curvas Re log ζ = cte rodean una u
otra unión y Im log ζ es el ángulo alrededor de cada una. Con las uniones en los
polos, las filas son círculos horizontales (un tubo recto); al llevarlas a la
pared lateral se convierten en las curvas que rodean la unión.

Asa. Un tubo de dos tramos de Hermite (A → W → B) que sale de la unión A en la
dirección de la normal, pasa por un punto W al costado y entra a B. Su sección
en cada extremo es la circunferencia de unión del cuerpo, así que la superficie
queda cerrada y sin costuras.

Es un script de apoyo: el servicio solo lee archivos, no importa este módulo.
"""

import bisect
import cmath
import math
from dataclasses import dataclass, replace

N = 100                    # puntos por dirección, igual que modelo_3d.csv
NB = 64                    # filas del cuerpo: 0 … NB; el asa usa NB … N-1

# Dimensiones del cuerpo; `configurar` las cambia y reconstruye el perfil.
R_EXT, R_INT = 1.25, 1.0   # radio exterior e interior de la pared
Y_BASE, Y_BORDE, Y_PISO = -1.5, 1.5, -0.8
Y_ASA = 0.8                # altura final (±) de las uniones sobre la pared
FILETES = dict(base=0.40, borde_ext=0.12, borde_int=0.10, piso=0.25)


def suave(a: float) -> float:
    a = min(1.0, max(0.0, a))
    return a * a * (3 - 2 * a)


@dataclass(frozen=True)
class Params:
    x0: float = -0.85          # posición del eje del cuerpo en x
    tau: float = 1.0           # 0 = uniones en los polos, 1 = en la pared lateral
    rho_union: float = 0.45    # radio de las circunferencias de unión
    rho_asa: float = 0.30      # radio del tubo en la parte media del asa
    wx: float = 1.75           # cuánto sobresale el asa respecto de la pared (x de W)
    k_union: float = 2.6       # intensidad de la tangente en las uniones
    k_w: float = 2.0           # intensidad de la tangente en W
    cavidad: float = 1.0       # 0 = tapa plana, 1 = boca abierta


# --- Perfil del cuerpo ------------------------------------------------------

def _esquinas(vertices):
    """Polilínea con las esquinas redondeadas con Bézier cuadráticas."""
    def unitario(a, b):
        d = math.dist(a, b)
        return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)

    puntos = []
    for i, (p, c) in enumerate(vertices):
        if c == 0.0:
            puntos.append(p)
            continue
        d1 = unitario(vertices[i - 1][0], p)
        d2 = unitario(p, vertices[i + 1][0])
        a = (p[0] - c * d1[0], p[1] - c * d1[1])
        b = (p[0] + c * d2[0], p[1] + c * d2[1])
        for k in range(13):
            t = k / 12
            puntos.append(((1 - t) ** 2 * a[0] + 2 * t * (1 - t) * p[0] + t * t * b[0],
                           (1 - t) ** 2 * a[1] + 2 * t * (1 - t) * p[1] + t * t * b[1]))
    return puntos


def _peso(p):
    # La malla reparte sus filas por igual en la coordenada del perfil, así que
    # se alarga el perfil donde hace falta más resolución (borde y esquina).
    return (1 + 6 * math.exp(-((p[1] - Y_BORDE) / 0.30) ** 2)
            + 2 * math.exp(-((p[1] - Y_BASE) / 0.45) ** 2))


def _con_arco(puntos):
    acum = [0.0]
    for p0, p1 in zip(puntos, puntos[1:]):
        acum.append(acum[-1] + math.dist(p0, p1) * _peso(p0))
    return puntos, acum


def _en_curva(curva, f):
    puntos, acum = curva
    s = f * acum[-1]
    i = min(max(bisect.bisect_left(acum, s), 1), len(acum) - 1)
    t = (s - acum[i - 1]) / (acum[i] - acum[i - 1])
    p0, p1 = puntos[i - 1], puntos[i]
    return p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])


def _construir():
    """(Re)construye el perfil y todo lo que depende de él."""
    global Y_CORTE, _PARTE1, _P2_BOCA, _P2_TAPA, Q, S_POLO_A, S_POLO_B, S_PARED_A, S_PARED_B
    f = FILETES
    Y_CORTE = Y_BORDE - 0.5 * (Y_BORDE - Y_BASE) / 3     # el tramo 1 llega hasta aquí
    _PARTE1 = _con_arco(_esquinas([((0.0, Y_BASE), 0.0), ((R_EXT, Y_BASE), f["base"]),
                                   ((R_EXT, Y_CORTE), 0.0)]))
    _P2_BOCA = _con_arco(_esquinas([((R_EXT, Y_CORTE), 0.0), ((R_EXT, Y_BORDE), f["borde_ext"]),
                                    ((R_INT, Y_BORDE), f["borde_int"]), ((R_INT, Y_PISO), f["piso"]),
                                    ((0.0, Y_PISO), 0.0)]))
    _P2_TAPA = _con_arco(_esquinas([((R_EXT, Y_CORTE), 0.0), ((R_EXT, Y_BORDE), f["borde_ext"]),
                                    ((0.0, Y_BORDE), 0.0)]))
    # fracción del perfil que ocupa el tramo 1 (fija: se calcula con la boca)
    Q = _PARTE1[1][-1] / (_PARTE1[1][-1] + _P2_BOCA[1][-1])
    S_POLO_A, S_POLO_B = 1 - 2e-3, 2e-3
    S_PARED_A, S_PARED_B = arco_en_pared(+Y_ASA), arco_en_pared(-Y_ASA)


def configurar(r_ext=None, r_int=None, y_base=None, y_borde=None, y_piso=None,
               y_asa=None, filetes=None):
    """Cambia las dimensiones del cuerpo (en las mismas unidades) y reconstruye."""
    global R_EXT, R_INT, Y_BASE, Y_BORDE, Y_PISO, Y_ASA, FILETES
    R_EXT = R_EXT if r_ext is None else r_ext
    R_INT = R_INT if r_int is None else r_int
    Y_BASE = Y_BASE if y_base is None else y_base
    Y_BORDE = Y_BORDE if y_borde is None else y_borde
    Y_PISO = Y_PISO if y_piso is None else y_piso
    Y_ASA = Y_ASA if y_asa is None else y_asa
    FILETES = FILETES if filetes is None else {**FILETES, **filetes}
    _construir()


def perfil(s: float, cavidad: float) -> tuple[float, float]:
    """(r, y) a la fracción s ∈ [0, 1] del perfil, de la base al centro de arriba."""
    if s <= Q:
        return _en_curva(_PARTE1, s / Q)
    f = (s - Q) / (1 - Q)
    tapa, boca = _en_curva(_P2_TAPA, f), _en_curva(_P2_BOCA, f)
    return ((1 - cavidad) * tapa[0] + cavidad * boca[0],
            (1 - cavidad) * tapa[1] + cavidad * boca[1])


def normal(s: float) -> tuple[float, float]:
    """Normal exterior (n_r, n_y) del perfil de la lata (cavidad 0) en s."""
    e = 1e-4
    r0, y0 = perfil(max(s - e, 0.0), 0.0)
    r1, y1 = perfil(min(s + e, 1.0), 0.0)
    d = math.hypot(r1 - r0, y1 - y0)
    return (y1 - y0) / d, -(r1 - r0) / d


def arco_en_pared(y: float) -> float:
    """Fracción del perfil del punto de la pared exterior a la altura y.

    La pared es un tramo recto con solo dos puntos, así que se interpola sobre
    él en lugar de tomar el punto más cercano (que siempre sería un extremo).
    """
    pts, acum = _PARTE1
    for i in range(len(pts) - 1):
        (r0, y0), (r1, y1) = pts[i], pts[i + 1]
        if r0 > R_EXT - 1e-9 and r1 > R_EXT - 1e-9 and min(y0, y1) - 1e-9 <= y <= max(y0, y1) + 1e-9:
            t = (y - y0) / (y1 - y0)
            return Q * (acum[i] + t * (acum[i + 1] - acum[i])) / acum[-1]
    raise ValueError(f"y = {y} no cae sobre la pared recta del perfil")


_construir()


# --- Cuerpo: coordenadas bipolares sobre la esfera --------------------------

def _uniones(p: Params):
    t = suave(p.tau)
    return (S_POLO_A + (S_PARED_A - S_POLO_A) * t,
            S_POLO_B + (S_PARED_B - S_POLO_B) * t)


class Cuerpo:
    def __init__(self, p: Params):
        self.p = p
        sa, sb = _uniones(p)
        self.sa, self.sb = sa, sb
        self.za = math.tan(math.pi * sa / 2)
        self.zb = math.tan(math.pi * sb / 2)
        pico = self._pico()
        self.l_b = self._buscar(-12.0, pico)     # unión de abajo: antes del pico de radio
        self.l_a = self._buscar(12.0, pico)      # unión de arriba: después del pico

    def punto(self, L: float, v: float) -> tuple[float, float, float]:
        zeta = cmath.exp(complex(L, v))
        if abs(zeta - 1) < 1e-9:           # ζ = 1 es el centro del piso (z = ∞)
            zeta = 1 + 1e-9
        z = (zeta * self.za - self.zb) / (zeta - 1)
        phi = cmath.phase(z)
        r, y = perfil(2 * math.atan(abs(z)) / math.pi, self.p.cavidad)
        return self.p.x0 + r * math.cos(phi), y, r * math.sin(phi)

    def anillo(self, L: float):
        return [self.punto(L, 2 * math.pi * j / (N - 1)) for j in range(N)]

    def _radio(self, L: float) -> float:
        pts = self.anillo(L)
        c = centro(pts)
        return sum(math.dist(q, c) for q in pts) / len(pts)

    def _pico(self) -> float:
        """L donde la curva de nivel es más grande (el radio sube y luego baja)."""
        mejor, lmejor = -1.0, 0.0
        for i in range(-60, 61):
            L = i * 0.2
            r = self._radio(L)
            if r > mejor:
                mejor, lmejor = r, L
        return lmejor

    def _buscar(self, lejos: float, pico: float) -> float:
        """L entre `pico` y `lejos` en el que el anillo mide rho_union."""
        cerca = pico                      # radio grande
        for _ in range(50):
            mid = (cerca + lejos) / 2
            if self._radio(mid) > self.p.rho_union:
                cerca = mid
            else:
                lejos = mid
        return (cerca + lejos) / 2


def centro(pts):
    return tuple(sum(q[k] for q in pts) / len(pts) for k in range(3))


# --- Asa: tubo de dos tramos de Hermite entre las uniones -------------------

def _hermite(s, p0, m0, p1, m1):
    h00, h10, h01, h11 = 2*s**3 - 3*s**2 + 1, s**3 - 2*s**2 + s, -2*s**3 + 3*s**2, s**3 - s**2
    d00, d10, d01, d11 = 6*s**2 - 6*s, 3*s**2 - 4*s + 1, -6*s**2 + 6*s, 3*s**2 - 2*s
    c = tuple(h00*p0[k] + h10*m0[k] + h01*p1[k] + h11*m1[k] for k in range(3))
    d = tuple(d00*p0[k] + d10*m0[k] + d01*p1[k] + d11*m1[k] for k in range(3))
    return c, d


class Espina:
    """Curva del centro del asa: A → W → B, con tangente continua en W."""

    def __init__(self, ca, cb, na, nb, p: Params):
        self.ca, self.cb = ca, cb
        k = p.k_union
        self.m0 = (k * na[0], k * na[1], 0.0)
        self.m2 = (-k * nb[0], -k * nb[1], 0.0)           # al entrar a B va contra su normal
        wx = max(ca[0], cb[0]) + p.wx
        self.w = (wx, (ca[1] + cb[1]) / 2, 0.0)
        self.mw = (0.0, -p.k_w, 0.0)

    def en(self, s):
        """Posición, tangente unitaria y normal (plano xy) en s ∈ [0, 1]."""
        if s <= 0.5:
            c, d = _hermite(2 * s, self.ca, self.m0, self.w, self.mw)
        else:
            c, d = _hermite(2 * s - 1, self.w, self.mw, self.cb, self.m2)
        n = math.hypot(d[0], d[1])
        T = (d[0] / n, d[1] / n, 0.0)
        return c, T, (-T[1], T[0], 0.0)


def _en_marco(q, c, T, Nn):
    d = (q[0] - c[0], q[1] - c[1], q[2] - c[2])
    return (d[0]*T[0] + d[1]*T[1], d[0]*Nn[0] + d[1]*Nn[1], d[2])


def _polar(e):
    return math.hypot(e[1], e[2]), math.atan2(e[2], e[1])


@dataclass(frozen=True)
class Tabla:
    """Dónde cae cada vértice del cuerpo, en coordenadas (L, v) de la familia.

    `f[k]` es la fracción de la fila k entre la unión B (0) y la unión A (1), y
    `v[k][j]` el ángulo de la columna j en esa fila. Se calcula una vez (ver
    `tabla_uniforme`) y se reutiliza en todos los fotogramas, de modo que cada
    vértice conserva su identidad durante el morph.
    """
    f: tuple
    v: tuple


def tabla_uniforme(p: Params, mezcla_filas: float = 0.7, mezcla_cols: float = 0.5,
                   nl: int = 320, nv: int = 400) -> Tabla:
    """Reparte los vértices del cuerpo por igual en área.

    Con coordenadas bipolares uniformes casi todos los vértices se amontonan
    alrededor de las uniones del asa. Aquí cada fila cubre la misma área y cada
    fila tiene sus columnas equiespaciadas a lo largo de su longitud.
    """
    cuerpo = Cuerpo(p)
    Ls = [cuerpo.l_b + (cuerpo.l_a - cuerpo.l_b) * i / (nl - 1) for i in range(nl)]
    vs = [2 * math.pi * m / nv for m in range(nv + 1)]
    X = [[cuerpo.punto(L, v) for v in vs] for L in Ls]

    def cruz(a, b):
        return math.sqrt((a[1]*b[2] - a[2]*b[1]) ** 2 + (a[2]*b[0] - a[0]*b[2]) ** 2
                         + (a[0]*b[1] - a[1]*b[0]) ** 2)

    banda = []                                    # área de cada franja entre dos niveles
    for i in range(nl - 1):
        tot = 0.0
        for m in range(nv):
            a = tuple(X[i + 1][m][c] - X[i][m][c] for c in range(3))
            b = tuple(X[i][m + 1][c] - X[i][m][c] for c in range(3))
            tot += cruz(a, b)
        banda.append(tot)
    acum = [0.0]
    for b in banda:
        acum.append(acum[-1] + b)
    f = []
    for k in range(NB + 1):
        objetivo = acum[-1] * k / NB
        i = min(max(bisect.bisect_left(acum, objetivo), 1), nl - 1)
        t = (objetivo - acum[i - 1]) / max(acum[i] - acum[i - 1], 1e-18)
        f_area = ((i - 1) + t) / (nl - 1)
        # a pegarse a las uniones el reparto por área da saltos enormes entre
        # una fila y la siguiente; se mezcla con el reparto uniforme
        f.append((1 - mezcla_filas) * k / NB + mezcla_filas * f_area)

    filas_v = []
    for k in range(NB + 1):
        L = cuerpo.l_b + (cuerpo.l_a - cuerpo.l_b) * f[k]
        pts = [cuerpo.punto(L, v) for v in vs]
        arco = [0.0]
        for a, b in zip(pts, pts[1:]):
            arco.append(arco[-1] + math.dist(a, b))
        fila = []
        for j in range(N):
            objetivo = arco[-1] * j / (N - 1)
            i = min(max(bisect.bisect_left(arco, objetivo), 1), nv)
            t = (objetivo - arco[i - 1]) / max(arco[i] - arco[i - 1], 1e-18)
            v_arco = vs[i - 1] + t * (vs[i] - vs[i - 1])
            fila.append((1 - mezcla_cols) * 2 * math.pi * j / (N - 1) + mezcla_cols * v_arco)
        fila[0], fila[-1] = 0.0, 2 * math.pi
        filas_v.append(tuple(fila))
    return Tabla(tuple(f), tuple(filas_v))


def malla(p: Params, tabla: Tabla | None = None):
    """Malla N×N×3 (lista de filas) de la taza con estos parámetros.

    Sin `tabla`, las filas y columnas del cuerpo van uniformes en (L, v).
    """
    cuerpo = Cuerpo(p)
    filas = []
    for k in range(NB + 1):
        if tabla is None:
            f, vs = k / NB, [2 * math.pi * j / (N - 1) for j in range(N)]
        else:
            f, vs = tabla.f[k], tabla.v[k]
        L = cuerpo.l_b + (cuerpo.l_a - cuerpo.l_b) * f
        filas.append([cuerpo.punto(L, v) for v in vs])
    anillo_b, anillo_a = filas[0], filas[NB]
    ca, cb = centro(anillo_a), centro(anillo_b)
    nra, nya = normal(cuerpo.sa)
    nrb, nyb = normal(cuerpo.sb)
    esp = Espina(ca, cb, (nra, nya), (nrb, nyb), p)

    _, T0, N0 = esp.en(0.0)
    _, T1, N1 = esp.en(1.0)
    ext_a = [_en_marco(q, ca, T0, N0) for q in anillo_a]
    ext_b = [_en_marco(q, cb, T1, N1) for q in anillo_b]
    giro = []
    for ea, eb in zip(ext_a, ext_b):
        d = _polar(eb)[1] - _polar(ea)[1]
        giro.append((d + math.pi) % (2 * math.pi) - math.pi)

    razon = p.rho_asa / ((_polar(ext_a[0])[0] + _polar(ext_b[0])[0]) / 2)
    n = N - NB
    for k in range(1, n):
        s = k / (n - 1)
        c, T, Nn = esp.en(s)
        borde = math.sin(math.pi * s)
        afinar = 1 - (1 - min(razon, 1.0)) * suave(borde / 0.5)
        pegado = 1 - suave(borde / 0.4)
        fila = []
        for j in range(N):
            ra, aa = _polar(ext_a[j])
            rb, _ = _polar(ext_b[j])
            r = ((1 - s) * ra + s * rb) * afinar
            a = aa + s * giro[j]
            t = ((1 - s) * ext_a[j][0] + s * ext_b[j][0]) * pegado
            fila.append((c[0] + t * T[0] + r * math.cos(a) * Nn[0],
                         c[1] + t * T[1] + r * math.cos(a) * Nn[1],
                         c[2] + r * math.sin(a)))
        filas.append(fila)
    assert len(filas) == N, len(filas)
    filas[-1] = list(filas[0])        # la última fila de la malla es la primera
    return filas


# Parámetros de la taza final
TAZA = Params()
