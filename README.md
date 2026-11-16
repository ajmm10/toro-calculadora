# Visualizador 3D del toro conectado a la calculadora de matrices

Dos servicios que antes vivían por separado, ahora integrados: el visualizador
3D dejó de calcular su propia matriz de transformación y se la pide a la
calculadora de matrices.

```
┌──────────────────────┐   POST /operaciones/    ┌────────────────────────┐
│  modelo-3d (visor)   │  ──   transformacion    ─▶ │ calculadora          │
│  FastAPI + Three.js  │   ◀── M = T·Rz·Ry·Rx·S ──  │  FastAPI             │
│  :8000  /view        │                           │  :8001  /docs        │
└──────────────────────┘                           └────────────────────────┘
```

## Arranque

```bash
docker compose up --build
```

Son dos programas separados, cada uno en su contenedor y en su puerto:

| Servicio (compose) | Carpeta | Puerto | Abrir |
|---|---|---|---|
| `calculadora` | `calculadora_matrices/` | 8001 | <http://localhost:8001> · API en <http://localhost:8001/docs> |
| `modelo-3d` | `modelotoro/` | 8000 | Visor en <http://localhost:8000/view> · API en <http://localhost:8000/docs> |

```bash
docker compose logs -f calculadora modelo-3d
```

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
muestra: `Matriz: calculadora · 5 factores · http://calculadora:8001`.

### 4. La red interna

El visualizador llama a `http://calculadora:8001`, el nombre del servicio en la
red de Docker. No a `localhost`: dentro de un contenedor, `localhost` es el
contenedor mismo. La URL se puede cambiar con la variable `CALCULADORA_URL`, que
es lo que permite correrlo fuera de Docker:

```bash
# terminal 1
cd calculadora_matrices && uvicorn main:app --port 8001

# terminal 2
cd modelotoro && CALCULADORA_URL=http://127.0.0.1:8001 uvicorn main:app --port 8000
```

El `compose` además espera a que la calculadora pase su `healthcheck` antes de
levantar el visualizador (`depends_on: condition: service_healthy`).

## Modelos

El visualizador tiene varios modelos que se eligen con los botones del panel
superior izquierdo: **toro**, **esfera**, **cubo**, **taza**, **taza (nube)** y el
morph **dona→taza** (ver más abajo). Todos reciben la misma
matriz de la calculadora; al cambiar de modelo la transformación se conserva.

- El toro es una malla cuadrada de su superficie (100×100): las caras salen
  del orden de los puntos.
- La esfera y el cubo (30 000 puntos cada uno) son nubes de puntos aleatorios que rellenan el
  volumen (no solo la superficie). No tienen caras, así que se ven solo como
  puntos y el botón de vista queda desactivado.

`GET /modelos` lista los nombres y `GET /model?nombre=esfera` devuelve los
vértices; las mallas incluyen además `grid`.

## Morph dona → taza

El botón **Dona→Taza** muestra un deslizador `t`: en 0 están las coordenadas de la
dona y en 1 las de la taza (`taza_3d_10000_puntos.csv`). Los botones **Taza** y
**Taza (nube)** muestran la taza sola, como malla y como nube de puntos.

**No es** la interpolación recta `P = (1 − t)·D + t·T` de la diapositiva: con
esta taza esa fórmula hace que la superficie se atraviese a sí misma (hasta 762
cruces en t = 0.6). En su lugar hay 42 fotogramas, formas intermedias válidas, y
la **calculadora** interpola entre fotogramas vecinos:

```
f = t·(n − 1),   i = ⌊f⌋,   a = f − i,   P(t) = (1 − a)·F[i] + a·F[i + 1]
```

- Dona → tubo con asa en lazo → taza ajustada a las medidas de la nube: 0 cruces,
  verificados en cada fotograma y en tres puntos entre fotogramas.
- Último tramo, taza ajustada → nube: cada vértice pasa a un punto real del CSV.
  Los puntos están desordenados y rellenan el grosor de la pared, así que aquí
  quedan unos cientos de cruces locales pequeños y la superficie se ve áspera en
  vista sólida. Solo se usan ~4 400 puntos distintos de los 10 000 (algunos se
  repiten).
- Todos los fotogramas tienen los mismos 100 × 100 vértices, así que la malla
  (caras y aristas) es la misma para cualquier `t`.

### Quién hace qué

```
navegador ──{"t": 0.4}──▶ visor /ws/morph ──POST /operaciones/morph──▶ calculadora
          ◀─ vértices ───                 ◀──────── vértices ─────────
```

El visor no interpola: reenvía `t` (máx. 25 por segundo) y copia los vértices
que recibe.

| Endpoint | Servicio | Qué hace |
|---|---|---|
| `POST /operaciones/morph` | calculadora | `{t, resolucion}` → vértices. `t` ∈ [0, 1], `resolucion` ∈ [2, 100] (lado de la malla). Fuera de rango, 422 |
| `POST /figuras` | calculadora | Guarda `{nombre, t, resolucion}`. 201 si la crea; 200 si ya existía igual; 409 si el nombre ya se usó con otros valores o hay 100 figuras |
| `GET /figuras`, `GET /figuras/{id}` | calculadora | Figuras guardadas |
| `WS /ws/morph` | visor | Relevo de `t` hacia la calculadora. Solo acepta orígenes de `ORIGENES_PERMITIDOS` |
| `POST/GET /api/figuras` | visor | Reenvía a `/figuras` de la calculadora |

El nombre de una figura admite letras, números, espacio, punto y guiones, hasta
40 caracteres, y el visor lo muestra con `textContent`.

```bash
curl -s -X POST localhost:8001/operaciones/morph -H 'Content-Type: application/json' \
  -d '{"t":0.5,"resolucion":3}'
curl -s -X POST localhost:8001/figuras -H 'Content-Type: application/json' \
  -d '{"nombre":"mitad","t":0.5}'
```

Los fotogramas se regeneran con (requiere `pip install numpy`; ningún servicio lo usa):

```bash
cd modelotoro
python generar_morph.py     # escribe ../calculadora_matrices/morph_frames.bin
```

`verificar_cruces.py` cuenta los cruces de una malla.

## Pruebas y análisis estático

```bash
pip install -r requirements-dev.txt
pytest          # tests/: calculadora, morph, figuras y relevo del visor
ruff check .    # reglas en pyproject.toml (E, F, B, S, C90)
```

## Comprobar el enlace sin abrir el navegador

```bash
# ¿el visualizador alcanza a la calculadora?
curl -s localhost:8000/api/calculadora

# multiplicar dos matrices por id
curl -s -X POST localhost:8001/matrices -H 'Content-Type: application/json' \
  -d '{"nombre":"A","datos":[[1,2],[3,4]]}'
curl -s -X POST localhost:8001/matrices -H 'Content-Type: application/json' \
  -d '{"nombre":"B","datos":[[5,6],[7,8]]}'
curl -s -X POST 'localhost:8001/operaciones/multiplicar?id1=1&id2=2'
#  -> {"resultado":[[19,22],[43,50]]}

# la cadena que usa el visualizador (aquí, dos identidades y una escala)
curl -s -X POST localhost:8001/operaciones/multiplicar-cadena \
  -H 'Content-Type: application/json' \
  -d '{"matrices":[[[1,0],[0,1]],[[1,0],[0,1]],[[2,0],[0,2]]]}'
#  -> {"resultado":[[2,0],[0,2]],"factores":3}

# la transformación completa del toro (ángulos en grados)
curl -s -X POST localhost:8001/operaciones/transformacion \
  -H 'Content-Type: application/json' \
  -d '{"tx":1,"rz":90,"s":2}'
#  -> {"orden":["T","Rz","Ry","Rx","S"],"factores":{...},"resultado":[[0,-2,0,1],...]}

# dimensiones incompatibles -> 400, no 500
curl -s -X POST localhost:8001/operaciones/multiplicar-cadena \
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
│   ├── models.py                # + MatrixChain, TransformParams, MorphParams, FiguraCreate
│   ├── repository.py            # + FiguraRepository (idempotente por nombre)
│   ├── morph.py                 # interpolación del morph dona → taza
│   ├── morph_frames.bin         # 42 fotogramas dona → taza (generado)
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
    ├── taza_3d_10000_puntos.csv        # taza: nube de 10 000 puntos (destino del morph)
    ├── modelo_taza.csv                 # último fotograma del morph (generado)
    ├── generar_morph.py                # genera los fotogramas y verifica que no se crucen
    ├── generar_taza.py                 # familia paramétrica de tazas que usa el generador
    ├── verificar_cruces.py             # cuenta cruces de la superficie consigo misma
    └── Dockerfile               # sin build-essential
tests/                           # pytest (ver «Pruebas y análisis estático»)
pyproject.toml                   # configuración de Ruff y pytest
```
