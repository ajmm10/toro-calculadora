# main.py
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from models import MatrixChain, MatrixCreate, TransformParams
from repository import MatrixRepository
import services

app = FastAPI(title="Calculadora de Matrices")

BASE_DIR = Path(__file__).parent

# Sin esto, el navegador bloquea las peticiones que hace index.html
# (abierto como archivo local) hacia esta API por política CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = MatrixRepository()


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/health")
def health():
    """Comprobación de vida. El visualizador 3D la consulta para saber si
    puede delegar el cálculo de su matriz de transformación."""
    return {"estado": "ok", "servicio": "calculadora-matrices"}


@app.post("/matrices")
def crear_matriz(payload: MatrixCreate):
    return repo.crear(payload.model_dump())


@app.get("/matrices")
def listar_matrices():
    return repo.listar()


@app.get("/matrices/{id}")
def obtener_matriz(id: int):
    matriz = repo.obtener(id)
    if not matriz:
        raise HTTPException(404, "matriz no encontrada")
    return matriz


@app.post("/operaciones/sumar")
def sumar_matrices(id1: int, id2: int):
    m1, m2 = repo.obtener(id1), repo.obtener(id2)
    if not m1 or not m2:
        raise HTTPException(404, "matriz no encontrada")
    try:
        return {"resultado": services.sumar(m1["datos"], m2["datos"])}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/operaciones/multiplicar")
def multiplicar_matrices(id1: int, id2: int):
    """Producto de dos matrices guardadas, por id."""
    m1, m2 = repo.obtener(id1), repo.obtener(id2)
    if not m1 or not m2:
        raise HTTPException(404, "matriz no encontrada")
    try:
        return {"resultado": services.multiplicar(m1["datos"], m2["datos"])}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/operaciones/multiplicar-cadena")
def multiplicar_cadena(payload: MatrixChain):
    """Producto de una secuencia de matrices enviadas directamente.

    Es la operación que consume el visualizador 3D: le manda los cinco
    factores de su transformación (T, Rz, Ry, Rx, S) y recibe la matriz
    compuesta. No guarda nada en el repositorio.
    """
    try:
        return {
            "resultado": services.multiplicar_cadena(payload.matrices),
            "factores": len(payload.matrices),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/operaciones/transformacion")
def transformacion(payload: TransformParams):
    """Matriz de transformación 3D a partir de sus parámetros.

    La calculadora arma los cinco factores (T, Rz, Ry, Rx, S) y devuelve
    tanto los factores como su producto M = T · Rz · Ry · Rx · S. Es la
    operación que consume el visualizador 3D. No guarda nada en el
    repositorio.
    """
    return services.transformacion(**payload.model_dump())


@app.post("/operaciones/transponer")
def transponer_matriz(id: int):
    m = repo.obtener(id)
    if not m:
        raise HTTPException(404, "matriz no encontrada")
    return {"resultado": services.transponer(m["datos"])}


@app.post("/operaciones/determinante")
def determinante_matriz(id: int):
    m = repo.obtener(id)
    if not m:
        raise HTTPException(404, "matriz no encontrada")
    try:
        return {"resultado": services.determinante(m["datos"])}
    except ValueError as e:
        raise HTTPException(400, str(e))
