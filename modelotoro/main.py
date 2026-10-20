"""Visualizador 3D: toro, esfera y cubo.

Este servicio NO construye ni multiplica matrices. Le manda a la calculadora
de matrices los parámetros de la transformación (traslación, rotaciones y
escala) y ella arma los cinco factores —T, Rz, Ry, Rx, S— y devuelve el
producto M = T · Rz · Ry · Rx · S.

La decisión es deliberada y verificable: no hay ninguna matriz de
transformación ni multiplicación en este archivo, ni se importa numpy. Si la calculadora no responde,
el visualizador no inventa la matriz por su cuenta: reporta el error y conserva
la última transformación válida. Un respaldo silencioso haría imposible saber
si la integración está funcionando.
"""

import csv
import math
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Visualizador 3D — modelos conectados a la calculadora")

# index.html y app.js se sirven desde este mismo origen, y la llamada a la
# calculadora es servidor a servidor (httpx), donde CORS no interviene. Solo
# se admiten los orígenes de la lista blanca, separados por comas en
# ORIGENES_PERMITIDOS. La misma lista valida el Origin del WebSocket.
ORIGENES_PERMITIDOS = [
    o.strip().rstrip("/")
    for o in os.getenv(
        "ORIGENES_PERMITIDOS", "http://localhost:8010,http://localhost:8012"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

# 'unsafe-inline' sigue en script-src y style-src porque el importmap de
# Three.js y los estilos están en línea en index.html. Endurecerlo exige
# moverlos a archivos externos o usar nonces.
CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
    "form-action 'self'"
)
CABECERAS_SEGURIDAD = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
# /docs y /redoc cargan Swagger UI y ReDoc desde cdn.jsdelivr.net; con la CSP
# de arriba se quedarían en blanco. Reciben el resto de cabeceras, pero no la CSP.
RUTAS_SIN_CSP = {"/docs", "/docs/oauth2-redirect", "/redoc"}


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    if request.url.path not in RUTAS_SIN_CSP:
        respuesta.headers["Content-Security-Policy"] = CSP
    respuesta.headers.update(CABECERAS_SEGURIDAD)
    return respuesta

# Three.js servido desde el propio contenedor, no desde un CDN: el proyecto
# tiene que poder levantarse en una máquina sin internet, que es justamente lo
# que promete estar dockerizado.
app.mount("/vendor", StaticFiles(directory=BASE_DIR / "vendor"), name="vendor")

# Dentro de docker compose, "calculadora" es el nombre del servicio en la red
# interna. Fuera de Docker se sobreescribe con http://localhost:8000.
CALCULADORA_URL = os.getenv("CALCULADORA_URL", "http://calculadora:8000").rstrip("/")
ENDPOINT_TRANSFORMACION = f"{CALCULADORA_URL}/operaciones/transformacion"


def cargar_puntos(path: Path) -> list[list[float]]:
    """Lee el CSV (x, y, z) y devuelve la lista de vértices.

    Los encabezados pueden venir en mayúsculas o minúsculas: el del toro usa
    x,y,z y los de la esfera y el cubo X,Y,Z.
    """
    with path.open(newline="") as f:
        filas = ({k.strip().lower(): v for k, v in r.items()} for r in csv.DictReader(f))
        return [[float(r["x"]), float(r["y"]), float(r["z"])] for r in filas]


def cargar_modelo(archivo: str, nube: bool = False) -> dict:
    """Vértices del modelo y, si es una malla, cómo unirlos.

    El toro es una malla cuadrada de su superficie (100 x 100) y el navegador
    reconstruye las caras con `grid`. La esfera y el cubo son nubes de puntos
    aleatorios que rellenan el volumen: no tienen orden ni caras, así que se
    dibujan solo como puntos.
    """
    puntos = cargar_puntos(BASE_DIR / archivo)
    modelo = {"count": len(puntos), "points": puntos}
    if nube:
        return modelo
    grid = math.isqrt(len(puntos))
    if grid * grid != len(puntos):
        raise ValueError(f"{archivo}: {len(puntos)} puntos no forman una malla cuadrada")
    modelo["grid"] = grid
    return modelo


MODELOS = {
    "toro": cargar_modelo("modelo_3d.csv"),
    "esfera": cargar_modelo("coordenadas_esfera_volumen.csv", nube=True),
    "cubo": cargar_modelo("coordenadas_cubo_volumen.csv", nube=True),
}

# Parámetros que entiende la calculadora y su valor neutro (la identidad).
PARAMETROS = {"tx": 0.0, "ty": 0.0, "tz": 0.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 1.0}


async def componer(params: dict, cliente: httpx.AsyncClient) -> dict:
    """Pide a la calculadora la matriz de transformación para estos parámetros.

    Devuelve la respuesta completa: el orden, los factores y el resultado.
    """
    respuesta = await cliente.post(ENDPOINT_TRANSFORMACION, json=params)
    respuesta.raise_for_status()
    return respuesta.json()


def a_columnas(m: list[list[float]]) -> list[float]:
    """Aplana en orden column-major, que es lo que espera Matrix4.fromArray."""
    return [m[fila][col] for col in range(4) for fila in range(4)]


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(BASE_DIR / "app.js", media_type="text/javascript")


@app.get("/modelos")
def modelos():
    """Nombres de los modelos disponibles."""
    return list(MODELOS)


@app.get("/model")
def model(nombre: str = "toro"):
    """Vértices del modelo y, en las mallas, su tamaño (`grid`) para unirlos."""
    if nombre not in MODELOS:
        raise HTTPException(404, f"modelo desconocido: {nombre}. Opciones: {', '.join(MODELOS)}")
    return MODELOS[nombre]


@app.get("/api/modelo-csv")
def modelo_csv(nombre: str = "toro"):
    """Formato alterno: total de puntos y lista de vértices."""
    m = model(nombre)
    return {"total_puntos": m["count"], "vertices": m["points"]}


@app.get("/api/calculadora")
async def estado_calculadora():
    """Comprueba desde el navegador que el enlace con la calculadora existe."""
    async with httpx.AsyncClient(timeout=3.0) as cliente:
        try:
            r = await cliente.get(f"{CALCULADORA_URL}/health")
            r.raise_for_status()
            return {"url": CALCULADORA_URL, "alcanzable": True, "respuesta": r.json()}
        except httpx.HTTPError as e:
            return {"url": CALCULADORA_URL, "alcanzable": False, "detalle": str(e)}


@app.websocket("/ws/transform")
async def ws_transform(websocket: WebSocket):
    await websocket.accept()

    async with httpx.AsyncClient(timeout=5.0) as cliente:
        try:
            while True:
                p = await websocket.receive_json()

                params = {k: float(p.get(k, v)) for k, v in PARAMETROS.items()}

                try:
                    datos = await componer(params, cliente)
                except httpx.HTTPError as e:
                    await websocket.send_json({
                        "origen": "error",
                        "error": f"la calculadora no respondió: {e.__class__.__name__}",
                        "url": ENDPOINT_TRANSFORMACION,
                    })
                    continue

                M = datos["resultado"]
                await websocket.send_json({
                    "origen": "calculadora",
                    "url": CALCULADORA_URL,
                    "factores": len(datos["factores"]),
                    "matrix": a_columnas(M),
                    "rows": [[round(v, 4) for v in fila] for fila in M],
                })
        except WebSocketDisconnect:
            pass
