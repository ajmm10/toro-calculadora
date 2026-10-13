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

async function loadModel(nombre) {
    const res = await fetch(`${API}/model?nombre=${encodeURIComponent(nombre)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    const { points } = data;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(points.flat()), 3));
    geometry.computeBoundingSphere();
    const radio = geometry.boundingSphere.radius;

    // Una nube de volumen no tiene caras: solo existe la vista de puntos. La
    // separación entre puntos de un volumen va como 1/∛n, y el tamaño también.
    const nube = !data.grid;
    const dots = new THREE.Points(geometry, new THREE.PointsMaterial({
        color: 0xffa657, size: nube ? radio * 0.3 / Math.cbrt(points.length) : radio * 0.02,
    }));
    let solid = null, wire = null;
    if (!nube) {
        geometry.setIndex(carasDeMalla(data.grid));
        geometry.computeVertexNormals();
        solid = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
            color: 0x58a6ff, metalness: 0.2, roughness: 0.45, side: THREE.DoubleSide,
        }));
        wire = new THREE.LineSegments(
            new THREE.WireframeGeometry(geometry),
            new THREE.LineBasicMaterial({ color: 0x79c0ff, transparent: true, opacity: 0.3 }),
        );
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

    const forma = nube ? 'nube de puntos del volumen' : `malla ${data.grid}×${data.grid}`;
    document.getElementById('titulo').textContent = `Visualizador 3D — ${nombre}`;
    document.getElementById('info').textContent = `${points.length} vértices · ${forma}`;
}

const botonesModelo = [...document.querySelectorAll('button[data-modelo]')];
async function elegirModelo(nombre) {
    botonesModelo.forEach(b => b.classList.toggle('on', b.dataset.modelo === nombre));
    try {
        await loadModel(nombre);
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
// ?modelo=esfera abre directamente otro modelo
await elegirModelo(new URLSearchParams(location.search).get('modelo') ?? 'toro');
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

    if (dirty && ws.readyState === WebSocket.OPEN && ahora - ultimoEnvio >= INTERVALO_MS) {
        ws.send(JSON.stringify(params));
        dirty = false;
        ultimoEnvio = ahora;
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
