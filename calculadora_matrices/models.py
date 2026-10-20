# models.py
from pydantic import BaseModel, field_validator

# services.multiplicar es O(n³) en Python puro y los endpoints no tienen
# autenticación: sin tope, una sola petición con matrices grandes ocupa el
# servicio indefinidamente.
MAX_DIMENSION = 50
MAX_MATRICES_EN_CADENA = 10


def _validar_rectangular(m: list[list[float]], etiqueta: str) -> None:
    if not m:
        raise ValueError(f"{etiqueta} está vacía")
    if len(m) > MAX_DIMENSION:
        raise ValueError(
            f"{etiqueta}: tiene {len(m)} filas; el máximo es {MAX_DIMENSION}"
        )
    largos = {len(fila) for fila in m}
    if len(largos) != 1:
        raise ValueError(f"{etiqueta}: todas las filas deben tener el mismo largo")
    if largos == {0}:
        raise ValueError(f"{etiqueta}: las filas no pueden estar vacías")
    columnas = largos.pop()
    if columnas > MAX_DIMENSION:
        raise ValueError(
            f"{etiqueta}: tiene {columnas} columnas; el máximo es {MAX_DIMENSION}"
        )


class MatrixCreate(BaseModel):
    nombre: str
    datos: list[list[float]]

    @field_validator("datos")
    @classmethod
    def filas_parejas(cls, v):
        _validar_rectangular(v, "datos")
        return v


class MatrixOut(MatrixCreate):
    id: int


class MatrixChain(BaseModel):
    """Entrada de /operaciones/multiplicar-cadena.

    A diferencia del resto de operaciones, esta no trabaja con matrices
    guardadas por id: recibe las matrices directamente. El visualizador 3D
    compone una matriz nueva cada vez que se mueve un control, y guardarlas
    todas en el repositorio lo llenaría sin límite.
    """

    matrices: list[list[list[float]]]

    @field_validator("matrices")
    @classmethod
    def cadena_valida(cls, v):
        if not v:
            raise ValueError("se requiere al menos una matriz")
        if len(v) > MAX_MATRICES_EN_CADENA:
            raise ValueError(
                f"la cadena tiene {len(v)} matrices; el máximo es {MAX_MATRICES_EN_CADENA}"
            )
        for i, m in enumerate(v):
            _validar_rectangular(m, f"la matriz en la posición {i}")
        return v



class TransformParams(BaseModel):
    """Entrada de /operaciones/transformacion.

    Traslación (tx, ty, tz), rotaciones en grados (rx, ry, rz) y escala
    uniforme s. Lo que falte toma el valor de la identidad.
    """

    tx: float = 0.0
    ty: float = 0.0
    tz: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    s: float = 1.0
