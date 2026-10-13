# models.py
from pydantic import BaseModel, field_validator


def _validar_rectangular(m: list[list[float]], etiqueta: str) -> None:
    if not m:
        raise ValueError(f"{etiqueta} está vacía")
    largos = {len(fila) for fila in m}
    if len(largos) != 1:
        raise ValueError(f"{etiqueta}: todas las filas deben tener el mismo largo")
    if largos == {0}:
        raise ValueError(f"{etiqueta}: las filas no pueden estar vacías")


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
