# Visualizador 3D del toro conectado a la calculadora de matrices

Dos servicios que antes vivían por separado, ahora integrados: el visualizador
3D dejó de calcular su propia matriz de transformación y se la pide a la
calculadora de matrices.

```
┌──────────────────────┐   POST /operaciones/    ┌────────────────────────┐
│  visualizador (toro) │  ──   transformacion    ─▶ │ calculadora_matrices │
│  FastAPI + Three.js  │   ◀── M = T·Rz·Ry·Rx·S ──  │  FastAPI             │
│  :8002               │                           │  :8000               │
└──────────────────────┘                           └────────────────────────┘
```

## Arranque

```bash
docker compose up --build
```

- Visualizador 3D — <http://localhost:8002>
- Calculadora de matrices — <http://localhost:8000>
- Documentación de ambas APIs — `/docs` en cada puerto

## Qué se conectó, exactamente

### 1. La calculadora no tenía multiplicación

Tenía `sumar`, `transponer` y `determinante`. La transformación del toro es
`M = T · Rz · Ry · Rx · S`: cuatro productos de matrices 4×4. Sin multiplicación
no había nada que delegar, así que se agregó:

| Archivo | Qué se agregó |
|---|---|
| `services.py` | `multiplicar(m1, m2)` con validación de dimensiones |
| `services.py` | `multiplicar_cadena(matrices)`, producto de una secuencia |
| `models.py` | `MatrixChain`, con validación de cada matriz de la cadena |
| `main.py` | `POST /operaciones/multiplicar?id1=&id2=` |
| `main.py` | `POST /operaciones/multiplicar-cadena` |
| `services.py` | `traslacion`, `rotacion_x/y/z`, `escalado`, `factores_transformacion`, `transformacion` |
| `models.py` | `TransformParams` (tx, ty, tz, rx, ry, rz en grados, s) |
| `main.py` | `POST /operaciones/transformacion`: arma T, Rz, Ry, Rx, S y devuelve factores y producto |
| `main.py` | `GET /health` y `GET /` para servir su interfaz |

Hay dos endpoints de multiplicación a propósito. El de ids sigue el estilo del
resto de la API, donde las operaciones trabajan sobre matrices guardadas. El de
cadena recibe las matrices directamente y **no guarda nada**: el visualizador
compone una matriz nueva cada vez que se mueve un control, y guardar cinco
matrices por cuadro llenaría el repositorio sin límite.

### 2. El visualizador dejó de construir y multiplicar matrices

Antes `main.py` armaba la matriz con NumPy:

```python
return T @ Rz @ Ry @ Rx @ S      # ya no existe
```

Ahora solo manda los parámetros; la calculadora arma los cinco factores
(T, Rz, Ry, Rx, S) y devuelve el producto:

```python
params = {"tx": .., "ty": .., "tz": .., "rx": .., "ry": .., "rz": .., "s": ..}
datos = await componer(params, cliente)   # POST /operaciones/transformacion
M = datos["resultado"]
```

La dependencia es real y se puede comprobar: **no queda ninguna matriz de
transformación ni multiplicación en el visualizador, y `numpy` salió de `requirements.txt`.** Al no
necesitar NumPy, el `Dockerfile` ya no instala `build-essential` y la imagen
construye bastante más rápido.

### 3. Si la calculadora no responde, se nota

El visualizador no tiene respaldo local. Si la calculadora está caída, manda por
el WebSocket:

```json
{"origen": "error", "error": "la calculadora no respondió: ConnectError", "url": "..."}
```

y el panel inferior lo muestra en rojo, conservando la última transformación
válida. Un respaldo silencioso con NumPy habría hecho imposible saber si la
integración funciona: el toro giraría igual con la calculadora apagada.

Por lo mismo, cada respuesta buena viene etiquetada con su origen, y el panel lo
muestra: `Matriz: calculadora · 5 factores · http://calculadora:8000`.

### 4. La red interna

El visualizador llama a `http://calculadora:8000`, el nombre del servicio en la
red de Docker. No a `localhost`: dentro de un contenedor, `localhost` es el
contenedor mismo. La URL se puede cambiar con la variable `CALCULADORA_URL`, que
es lo que permite correrlo fuera de Docker:

```bash
# terminal 1
cd calculadora_matrices && uvicorn main:app --port 8000

# terminal 2
cd modelotoro && CALCULADORA_URL=http://127.0.0.1:8000 uvicorn main:app --port 8002
```

El `compose` además espera a que la calculadora pase su `healthcheck` antes de
levantar el visualizador (`depends_on: condition: service_healthy`).

## Modelos

El visualizador tiene tres modelos que se eligen con los botones del panel
superior izquierdo: **toro**, **esfera** y **cubo**. Los tres reciben la misma
matriz de la calculadora; al cambiar de modelo la transformación se conserva.

- El toro es una malla cuadrada de su superficie (100×100): las caras salen
  del orden de los puntos.
- La esfera y el cubo (30 000 puntos cada uno) son nubes de puntos aleatorios que rellenan el
  volumen (no solo la superficie). No tienen caras, así que se ven solo como
  puntos y el botón de vista queda desactivado.

`GET /modelos` lista los nombres y `GET /model?nombre=esfera` devuelve los
vértices; las mallas incluyen además `grid`.

## Comprobar el enlace sin abrir el navegador

```bash
# ¿el visualizador alcanza a la calculadora?
curl -s localhost:8002/api/calculadora

# multiplicar dos matrices por id
curl -s -X POST localhost:8000/matrices -H 'Content-Type: application/json' \
  -d '{"nombre":"A","datos":[[1,2],[3,4]]}'
curl -s -X POST localhost:8000/matrices -H 'Content-Type: application/json' \
  -d '{"nombre":"B","datos":[[5,6],[7,8]]}'
curl -s -X POST 'localhost:8000/operaciones/multiplicar?id1=1&id2=2'
#  -> {"resultado":[[19,22],[43,50]]}

# la cadena que usa el visualizador (aquí, dos identidades y una escala)
curl -s -X POST localhost:8000/operaciones/multiplicar-cadena \
  -H 'Content-Type: application/json' \
  -d '{"matrices":[[[1,0],[0,1]],[[1,0],[0,1]],[[2,0],[0,2]]]}'
#  -> {"resultado":[[2,0],[0,2]],"factores":3}

# la transformación completa del toro (ángulos en grados)
curl -s -X POST localhost:8000/operaciones/transformacion \
  -H 'Content-Type: application/json' \
  -d '{"tx":1,"rz":90,"s":2}'
#  -> {"orden":["T","Rz","Ry","Rx","S"],"factores":{...},"resultado":[[0,-2,0,1],...]}

# dimensiones incompatibles -> 400, no 500
curl -s -X POST localhost:8000/operaciones/multiplicar-cadena \
  -H 'Content-Type: application/json' \
  -d '{"matrices":[[[1,2,3]],[[1,2],[3,4]]]}'
```

Para ver el fallo controlado: `docker compose stop calculadora` con el
visualizador abierto. El panel pasa a rojo y el toro se queda donde estaba.

## Otros arreglos que iban de paso

**El `Dockerfile` de la calculadora no construía.** Su primera línea era
literalmente la palabra `Dockerfile`, lo que hace fallar el build con
`unknown instruction: DOCKERFILE`.

**`app.js` estaba escrito pero nadie lo cargaba.** El `index.html` anterior traía
su propia escena en línea —una nube de puntos que giraba sola, sin controles— y
`app.js`, que es mucho más completo, se servía en `/app.js` pero ningún
`<script>` lo incluía, y los elementos del DOM que esperaba no existían. Ahora el
`index.html` trae el `importmap`, el panel de controles y los elementos que
`app.js` usa, así que ese código por fin corre.

**Three.js ya no viene de un CDN.** Está en `modelotoro/vendor/`, servido por el
propio contenedor. Depender de `unpkg.com` o `cdnjs.com` contradice la promesa de
estar dockerizado: en una máquina sin internet, o detrás de una red que bloquee
el CDN, la página cargaba en blanco.

**La cámara estaba fuera de escala.** Estaba en `(30, 25, 35)` con una rejilla de
60 unidades, cuando el toro del CSV mide 6 (radio mayor 2, radio menor 1). Se
ajustó a `(6, 5, 7)` con rejilla de 16.

**Se limitó el envío a 25 mensajes por segundo.** Cada mensaje del WebSocket
dispara una petición HTTP a la calculadora; a 60 cuadros por segundo serían 60
productos matriciales por segundo sin ninguna ganancia visual. El render sigue a
60 fps con la última matriz recibida.

## Estructura

```
toro-calculadora/
├── docker-compose.yaml          # los dos servicios en una red interna
├── calculadora_matrices/
│   ├── main.py                  # + multiplicar, multiplicar-cadena, transformacion, health
│   ├── services.py              # + multiplicar, multiplicar_cadena, matrices T/R/S
│   ├── models.py                # + MatrixChain, TransformParams
│   ├── repository.py
│   ├── index.html               # interfaz de la calculadora
│   └── Dockerfile               # corregido
└── modelotoro/
    ├── main.py                  # manda parámetros, la calculadora arma M
    ├── app.js                   # conectado y con el origen de la matriz
    ├── index.html               # importmap + panel de controles
    ├── vendor/                  # three.js servido localmente
    ├── modelo_3d.csv            # toro: 10 000 vértices, malla 100×100
    ├── coordenadas_esfera_volumen.csv  # esfera r=5: 30 000 puntos del volumen
    ├── coordenadas_cubo_volumen.csv    # cubo de lado 10: 30 000 puntos del volumen
    └── Dockerfile               # sin build-essential
```
