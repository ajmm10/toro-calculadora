# services.py
import math

def sumar(m1: list[list[float]], m2: list[list[float]]) -> list[list[float]]:
    if len(m1) != len(m2) or len(m1[0]) != len(m2[0]):
        raise ValueError("las matrices deben tener la misma dimensión")
    return [
        [a + b for a, b in zip(fila1, fila2)]
        for fila1, fila2 in zip(m1, m2)
    ]


def transponer(m: list[list[float]]) -> list[list[float]]:
    return [list(fila) for fila in zip(*m)]


def multiplicar(m1: list[list[float]], m2: list[list[float]]) -> list[list[float]]:
    """Producto matricial m1 · m2.

    Se agregó para que el visualizador 3D pueda componer su matriz de
    transformación aquí en lugar de calcularla por su cuenta: la cadena
    M = T · Rz · Ry · Rx · S son cuatro multiplicaciones de matrices 4x4.
    """
    if not m1 or not m2:
        raise ValueError("las matrices no pueden estar vacías")

    columnas_m1 = len(m1[0])
    filas_m2 = len(m2)

    if columnas_m1 != filas_m2:
        raise ValueError(
            f"dimensiones incompatibles: {len(m1)}x{columnas_m1} por "
            f"{filas_m2}x{len(m2[0])}. Las columnas de la primera deben "
            "coincidir con las filas de la segunda."
        )

    columnas_m2 = len(m2[0])
    return [
        [
            sum(m1[i][k] * m2[k][j] for k in range(columnas_m1))
            for j in range(columnas_m2)
        ]
        for i in range(len(m1))
    ]


def multiplicar_cadena(matrices: list[list[list[float]]]) -> list[list[float]]:
    """Producto de una secuencia de matrices, de izquierda a derecha.

    El producto matricial es asociativo, así que plegar por la izquierda da el
    mismo resultado que cualquier otro agrupamiento. Con una sola matriz
    devuelve esa matriz.
    """
    if not matrices:
        raise ValueError("se requiere al menos una matriz")

    resultado = matrices[0]
    for siguiente in matrices[1:]:
        resultado = multiplicar(resultado, siguiente)
    return resultado


def determinante(m: list[list[float]]) -> float:
    n = len(m)
    if any(len(fila) != n for fila in m):
        raise ValueError("la matriz debe ser cuadrada para calcular el determinante")

    # eliminación gaussiana con pivoteo parcial, sobre una copia
    mat = [fila[:] for fila in m]
    det = 1.0
    for i in range(n):
        pivote = max(range(i, n), key=lambda fila: abs(mat[fila][i]))
        if abs(mat[pivote][i]) < 1e-12:
            return 0.0
        if pivote != i:
            mat[i], mat[pivote] = mat[pivote], mat[i]
            det *= -1
        det *= mat[i][i]
        for j in range(i + 1, n):
            factor = mat[j][i] / mat[i][i]
            for k in range(i, n):
                mat[j][k] -= factor * mat[i][k]
    return det


# --- Transformaciones 3D en coordenadas homogéneas (matrices 4x4) ---

def traslacion(tx: float, ty: float, tz: float) -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, float(tx)],
        [0.0, 1.0, 0.0, float(ty)],
        [0.0, 0.0, 1.0, float(tz)],
        [0.0, 0.0, 0.0, 1.0],
    ]


def rotacion_x(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, math.cos(a), -math.sin(a), 0.0],
        [0.0, math.sin(a), math.cos(a), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def rotacion_y(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [math.cos(a), 0.0, math.sin(a), 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [-math.sin(a), 0.0, math.cos(a), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def rotacion_z(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [math.cos(a), -math.sin(a), 0.0, 0.0],
        [math.sin(a), math.cos(a), 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def escalado(s: float) -> list[list[float]]:
    return [
        [float(s), 0.0, 0.0, 0.0],
        [0.0, float(s), 0.0, 0.0],
        [0.0, 0.0, float(s), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def factores_transformacion(
    tx=0.0, ty=0.0, tz=0.0, rx=0.0, ry=0.0, rz=0.0, s=1.0
) -> dict[str, list[list[float]]]:
    """Los cinco factores de M = T · Rz · Ry · Rx · S, en ese orden.

    Los ángulos llegan en grados.
    """
    return {
        "T": traslacion(tx, ty, tz),
        "Rz": rotacion_z(rz),
        "Ry": rotacion_y(ry),
        "Rx": rotacion_x(rx),
        "S": escalado(s),
    }


def transformacion(**params) -> dict:
    """Arma los factores y los multiplica: M = T · Rz · Ry · Rx · S."""
    factores = factores_transformacion(**params)
    return {
        "orden": list(factores),
        "factores": factores,
        "resultado": multiplicar_cadena(list(factores.values())),
    }
