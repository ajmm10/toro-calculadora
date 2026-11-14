import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ---------------------------------------------------------------------------
// Escena
// La cámara, la rejilla y los ejes se ajustan al tamaño de cada modelo al
// cargarlo (ver encuadrar): el toro mide 6 unidades, la esfera y el cubo 10.
// ---------------------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e1117);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 200);
camera.position.set(6, 5, 7);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.AmbientLight(0xffffff, 0.5));
const light = new THREE.DirectionalLight(0xffffff, 1.2);
light.position.set(6, 10, 6);
scene.add(light);
let grid = null;
let axes = null;

const API = window.location.origin;
const WS_URL = API.replace(/^http/, 'ws') + '/ws/transform';

// El grupo recibe la matriz que compone la calculadora de matrices.
// Sin matrixAutoUpdate = false, Three.js la sobreescribiría en cada cuadro.
const model = new THREE.Group();
model.matrixAutoUpdate = false;
scene.add(model);

// ---------------------------------------------------------------------------
// Modelo: vértices del CSV y caras.
// El toro es una malla cuadrada y sus caras salen del orden de los puntos; la
// esfera y el cubo son nubes de puntos que rellenan el volumen, sin caras.
// ---------------------------------------------------------------------------
function carasDeMalla(n) {
    const indices = [];
    for (let i = 0; i < n - 1; i++) {
        for (let j = 0; j < n - 1; j++) {
            const a = i * n + j, b = a + 1, c = a + n, d = c + 1;
            indices.push(a, c, b, b, c, d);
        }
    }
    return indices;
}

// Aristas de la malla para el alambre. Comparte los vértices de la superficie
// (mismo atributo `position`), así sigue la deformación durante el morph en
// lugar de quedarse con una copia de los puntos del toro.
function aristasDeMalla(n) {
    const indices = [];
    for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
            const a = i * n + j;
            if (j < n - 1) indices.push(a, a + 1);
            if (i < n - 1) indices.push(a, a + n);
            if (i < n - 1 && j < n - 1) indices.push(a + 1, a + n);
        }
    }
    return indices;
}

// Coloca cámara, rejilla y ejes según el radio del modelo
function encuadrar(radio) {
    if (grid) scene.remove(grid);
    if (axes) scene.remove(axes);
    const lado = Math.max(16, Math.ceil(radio * 4 / 2) * 2);
    grid = new THREE.GridHelper(lado, lado, 0x30363d, 0x21262d);
    axes = new THREE.AxesHelper(radio * 1.4);
    scene.add(grid, axes);

    camera.position.set(6, 5, 7).normalize().multiplyScalar(radio * 3);
    controls.target.set(0, 0, 0);
    controls.update();
}

let parts = null;

async function pedirModelo(nombre) {
    const res = await fetch(`${API}/model?nombre=${encodeURIComponent(nombre)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    return data;
}

// "morph" no es un modelo del servidor: es la dona deformándose hacia la taza.
// Este archivo NO interpola nada. El deslizador manda t por el WebSocket
// /ws/morph, el backend se lo pasa a la calculadora (POST /operaciones/morph)
// y lo que vuelve son los vértices ya calculados. La malla (caras y aristas)
// es la del toro para cualquier t, así que solo cambian las posiciones.
let morphActivo = false;
let tPendiente = null;     // último t pedido que aún no se ha enviado

function aplicarVertices(vertices) {
    if (!morphActivo || !parts) return;
    const pos = parts.dots.geometry.attributes.position;
    if (vertices.length !== pos.array.length) return;   // llegó tarde, de otro modelo
    pos.array.set(vertices);
    pos.needsUpdate = true;
    if (parts.solid) parts.solid.geometry.computeVertexNormals();
}

function pedirT(t) {
    tPendiente = t;
}

async function loadModel(nombre) {
    const esMorph = nombre === 'morph';
    morphActivo = false;
    // El morph arranca con la malla de la dona; la taza solo se pide para
    // encuadrar la cámara, porque es bastante más grande.
    const data = await pedirModelo(esMorph ? 'toro' : nombre);
    const flat = new Float32Array(data.points.flat());
    const total = flat.length / 3;
    document.getElementById('morph-panel').hidden = !esMorph;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(flat, 3));
    geometry.computeBoundingSphere();
    let radio = geometry.boundingSphere.radius;
    if (esMorph) {
        const taza = await pedirModelo('taza');
        for (const [x, y, z] of taza.points) radio = Math.max(radio, Math.hypot(x, y, z));
    }

    // Una nube de volumen no tiene caras: solo existe la vista de puntos. La
    // separación entre puntos de un volumen va como 1/∛n, y el tamaño también.
    const nube = !data.grid;
    const dots = new THREE.Points(geometry, new THREE.PointsMaterial({
        color: 0xffa657, size: nube ? radio * 0.3 / Math.cbrt(total) : radio * 0.02,
    }));
    let solid = null, wire = null;
    if (!nube) {
        geometry.setIndex(carasDeMalla(data.grid));
        geometry.computeVertexNormals();
        solid = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
            color: 0x58a6ff, metalness: 0.2, roughness: 0.45, side: THREE.DoubleSide,
        }));
        const lineas = new THREE.BufferGeometry();
        lineas.setAttribute('position', geometry.getAttribute('position'));
        lineas.setIndex(aristasDeMalla(data.grid));
        wire = new THREE.LineSegments(
            lineas,
            new THREE.LineBasicMaterial({ color: 0x79c0ff, transparent: true, opacity: 0.3 }),
        );
    }

    // Los puntos con la altura en z (data.z_arriba) se enderezan al "arriba" del
    // visualizador, que es y, y se centran en el origen. Se hace en los objetos
    // y no en el grupo `model`, que es el que recibe la matriz de la calculadora.
    if (data.z_arriba) {
        geometry.computeBoundingBox();
        const c = geometry.boundingBox.getCenter(new THREE.Vector3());
        for (const objeto of [solid, wire, dots].filter(Boolean)) {
            objeto.rotation.x = -Math.PI / 2;          // (x, y, z) → (x, z, −y)
            objeto.position.set(-c.x, -c.z, c.y);      // centro ya girado, con signo cambiado
        }
    }

    // Se cambia el contenido del grupo, no el grupo: la matriz de la
    // calculadora sigue aplicada al modelo nuevo.
    for (const hijo of [...model.children]) {
        model.remove(hijo);
        hijo.geometry.dispose();
        hijo.material.dispose();
    }
    model.add(...[solid, wire, dots].filter(Boolean));
    parts = { solid, wire, dots, nube };
    encuadrar(radio);

    if (esMorph) {
        morphActivo = true;
        pedirT(parseFloat(document.getElementById('t').value));
    }

    const forma = nube ? 'nube de puntos del volumen' : `malla ${data.grid}×${data.grid}`;
    document.getElementById('titulo').textContent = `Visualizador 3D — ${esMorph ? 'dona → taza' : nombre}`;
    document.getElementById('info').textContent = `${total} vértices · ${forma}`;
}

const botonesModelo = [...document.querySelectorAll('button[data-modelo]')];
async function elegirModelo(nombre) {
    botonesModelo.forEach(b => b.classList.toggle('on', b.dataset.modelo === nombre));
    try {
        await loadModel(nombre);
        // La taza y el morph se leen mal como nube de puntos: abren en sólido.
        if (nombre === 'taza' || nombre === 'morph') modeIdx = modes.findIndex(m => m[0] === 'sólido');
        else if (nombre === 'toro') modeIdx = 0;
        applyMode();
    } catch (e) {
        document.getElementById('info').innerHTML = `<b class="bad">No se pudo cargar ${nombre}</b>: ${e.message}`;
    }
}
botonesModelo.forEach(b => b.addEventListener('click', () => elegirModelo(b.dataset.modelo)));

// ---------------------------------------------------------------------------
// Modos de vista
// Se arranca en "puntos": lo que se ve son los vértices tal cual vienen del CSV.
// ---------------------------------------------------------------------------
const modes = [
    ['puntos', { solid: false, wire: false, dots: true }],
    ['sólido', { solid: true, wire: false, dots: false }],
    ['malla', { solid: true, wire: true, dots: false }],
    ['alambre', { solid: false, wire: true, dots: false }],
];
let modeIdx = 0;
function applyMode() {
    if (!parts) return;
    const boton = document.getElementById('mode');
    boton.disabled = parts.nube;
    if (parts.nube) {
        boton.textContent = 'Vista: puntos';
        return;
    }
    const [name, vis] = modes[modeIdx];
    for (const k in vis) parts[k].visible = vis[k];
    boton.textContent = `Vista: ${name}`;
}
// Control del morph: el deslizador y la animación de ida y vuelta
const tSlider = document.getElementById('t');
const tOut = document.getElementById('t-out');
tSlider.addEventListener('input', () => {
    tOut.textContent = parseFloat(tSlider.value).toFixed(2);
    pedirT(parseFloat(tSlider.value));
});
let animandoMorph = false;
document.getElementById('morph-anim').onclick = (e) => {
    animandoMorph = !animandoMorph;
    e.target.classList.toggle('on', animandoMorph);
};
// Figuras guardadas: un t con nombre. Las guarda la calculadora; el visor solo
// las reenvía. El nombre se pinta con textContent, nunca como HTML.
const figuraNombre = document.getElementById('figura-nombre');
const figuraInput = document.getElementById('figura-input');
const figuraLista = document.getElementById('figura-lista');
const figuraEstado = document.getElementById('figura-estado');
let figuras = [];

function ponerT(t) {
    tSlider.value = t;
    tOut.textContent = parseFloat(tSlider.value).toFixed(2);
    pedirT(parseFloat(tSlider.value));
}

async function cargarFiguras() {
    const res = await fetch(`${API}/api/figuras`);
    if (!res.ok) return;
    figuras = await res.json();
    figuraLista.replaceChildren(new Option('Figuras guardadas…', ''));
    for (const f of figuras) figuraLista.add(new Option(`${f.nombre} (t = ${f.t.toFixed(2)})`, f.id));
}

document.getElementById('figura-guardar').onclick = async () => {
    const nombre = figuraInput.value.trim();
    if (!nombre) return;
    const res = await fetch(`${API}/api/figuras`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre, t: parseFloat(tSlider.value), resolucion: 100 }),
    });
    const data = await res.json();
    if (!res.ok) {
        const detalle = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join('; ') : data.detail;
        figuraEstado.className = 'bad';
        figuraEstado.textContent = `No se guardó: ${detalle}`;
        return;
    }
    figuraNombre.textContent = data.nombre;
    figuraEstado.className = 'dim';
    figuraEstado.textContent = res.status === 201 ? 'Guardada.' : 'Ya estaba guardada.';
    await cargarFiguras();
};

figuraLista.onchange = () => {
    const f = figuras.find(x => String(x.id) === figuraLista.value);
    if (!f) return;
    figuraNombre.textContent = f.nombre;
    ponerT(f.t);
};

// Mover el deslizador deja de ser la figura guardada
tSlider.addEventListener('input', () => { figuraNombre.textContent = 'sin nombre'; });

// ?modelo=morph&t=0.7 abre el morph ya en ese punto
const tInicial = parseFloat(new URLSearchParams(location.search).get('t'));
if (!Number.isNaN(tInicial)) {
    tSlider.value = tInicial;
    tOut.textContent = parseFloat(tSlider.value).toFixed(2);
}
// ?modelo=esfera abre directamente otro modelo
await elegirModelo(new URLSearchParams(location.search).get('modelo') ?? 'toro');
cargarFiguras();
document.getElementById('mode').onclick = () => { modeIdx = (modeIdx + 1) % modes.length; applyMode(); };

// ---------------------------------------------------------------------------
// Controles
// ---------------------------------------------------------------------------
const sliders = [...document.querySelectorAll('input[data-k]')];
const params = {};
function readSliders() {
    for (const s of sliders) {
        params[s.dataset.k] = parseFloat(s.value);
        s.nextElementSibling.textContent = parseFloat(s.value).toFixed(s.dataset.k === 's' ? 2 : 1);
    }
}
readSliders();
let dirty = true;
sliders.forEach(s => s.addEventListener('input', () => { readSliders(); dirty = true; }));

let auto = false;
document.getElementById('auto').onclick = (e) => {
    auto = !auto;
    e.target.classList.toggle('on', auto);
    e.target.textContent = auto ? 'Detener giro' : 'Giro automático';
};
document.getElementById('reset').onclick = () => {
    for (const s of sliders) s.value = s.dataset.k === 's' ? 1 : 0;
    readSliders(); dirty = true;
};

// ---------------------------------------------------------------------------
// WebSocket con el backend del visualizador.
// El backend NO arma ni multiplica matrices: manda los parámetros a la
// calculadora, que construye los cinco factores y devuelve el producto. Por
// eso el panel muestra de dónde vino cada matriz.
// ---------------------------------------------------------------------------
const statusEl = document.getElementById('status');
const originEl = document.getElementById('origin');
const matrixEl = document.getElementById('matrix');
let ws;

function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        statusEl.innerHTML = 'WebSocket: <b class="ok">conectado</b>';
        dirty = true;
    };

    ws.onclose = () => {
        statusEl.innerHTML = 'WebSocket: <b class="bad">desconectado</b> · reintentando…';
        setTimeout(connect, 1500);
    };

    ws.onmessage = (event) => {
        const res = JSON.parse(event.data);

        if (res.origen === 'error') {
            originEl.innerHTML = `Matriz: <b class="bad">sin calcular</b> — ${res.error}`;
            return;
        }

        if (res.matrix) {
            // Los 16 elementos llegan en orden column-major
            model.matrix.fromArray(res.matrix);
            model.matrixWorldNeedsUpdate = true;

            originEl.innerHTML =
                `Matriz: <b class="ok">calculadora</b> · ${res.factores} factores · <span class="dim">${res.url}</span>`;

            matrixEl.textContent = res.rows
                .map(r => r.map(v => v.toFixed(3).padStart(8)).join(' '))
                .join('\n');
        }
    };
}
connect();

// Segundo WebSocket, solo para el morph: manda t y recibe los vértices que
// calculó la calculadora.
const morphEl = document.getElementById('morph-estado');
let wsMorph;
function conectarMorph() {
    wsMorph = new WebSocket(API.replace(/^http/, 'ws') + '/ws/morph');
    wsMorph.onopen = () => { if (morphActivo) pedirT(parseFloat(tSlider.value)); };
    wsMorph.onclose = () => setTimeout(conectarMorph, 1500);
    wsMorph.onmessage = (event) => {
        const res = JSON.parse(event.data);
        if (res.origen === 'error') {
            morphEl.className = 'bad';
            morphEl.textContent = `Morph: ${res.error}`;
            return;
        }
        aplicarVertices(res.vertices);
        morphEl.className = 'dim';
        morphEl.textContent = `Morph: calculadora · t = ${res.t.toFixed(2)} · ${res.count} vértices`;
    };
}
conectarMorph();

// ---------------------------------------------------------------------------
// Bucle de render
//
// El envío va limitado a 25 mensajes por segundo: cada uno provoca una
// petición HTTP del backend a la calculadora, y a 60 cuadros por segundo
// serían 60 productos matriciales por segundo sin ninguna ganancia visual.
// El render sigue a 60 fps con la última matriz recibida.
// ---------------------------------------------------------------------------
const INTERVALO_MS = 40;
let ultimoEnvio = 0;
let ultimoEnvioMorph = 0;   // el morph va limitado igual: 25 t por segundo
let t = 0;

function animate(ahora) {
    requestAnimationFrame(animate);

    if (auto) {
        t += 1;
        const set = (k, v) => {
            const s = sliders.find(x => x.dataset.k === k);
            if (s) s.value = v;
        };
        set('rx', ((t * 0.8 + 180) % 360) - 180);
        set('ry', ((t * 0.5 + 180) % 360) - 180);
        set('tx', (Math.sin(t * 0.02) * 2).toFixed(1));
        readSliders();
        dirty = true;
    }

    if (animandoMorph && morphActivo) {
        // vaivén suave 0 → 1 → 0 cada ~6 s
        const v = (1 - Math.cos(ahora / 1000 * Math.PI / 3)) / 2;
        tSlider.value = v;
        tOut.textContent = v.toFixed(2);
        pedirT(v);
    }

    if (dirty && ws.readyState === WebSocket.OPEN && ahora - ultimoEnvio >= INTERVALO_MS) {
        ws.send(JSON.stringify(params));
        dirty = false;
        ultimoEnvio = ahora;
    }

    if (tPendiente !== null && wsMorph.readyState === WebSocket.OPEN
        && ahora - ultimoEnvioMorph >= INTERVALO_MS) {
        wsMorph.send(JSON.stringify({ t: tPendiente }));
        tPendiente = null;
        ultimoEnvioMorph = ahora;
    }

    controls.update();
    renderer.render(scene, camera);
}
requestAnimationFrame(animate);

window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});
