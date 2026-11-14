"""Relevo del morph en el visor (/ws/morph).

El visor se importa con otro nombre para no chocar con el main.py de la
calculadora. Sus llamadas HTTP a la calculadora se redirigen a la app real
de la calculadora (en memoria), así que se prueba el camino completo.
"""

import importlib.util
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = "http://localhost:8012"


def cargar_visor():
    spec = importlib.util.spec_from_file_location("visor_main", RAIZ / "modelotoro" / "main.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


visor = cargar_visor()


@pytest.fixture
def ws_cliente(app_calculadora, monkeypatch):
    """Cliente del visor cuyo httpx habla con la calculadora en memoria."""
    original = httpx.AsyncClient

    def cliente_hacia_calculadora(*args, **kwargs):
        kwargs["transport"] = httpx.ASGITransport(app=app_calculadora)
        return original(*args, **kwargs)

    monkeypatch.setattr(visor.httpx, "AsyncClient", cliente_hacia_calculadora)
    return TestClient(visor.app)


def test_relevo_devuelve_los_vertices_de_la_calculadora(ws_cliente, cliente):
    esperado = cliente.post("/operaciones/morph", json={"t": 0.4}).json()["vertices"]
    with ws_cliente.websocket_connect("/ws/morph", headers={"origin": ORIGEN}) as ws:
        ws.send_json({"t": 0.4})
        res = ws.receive_json()
    assert res["origen"] == "calculadora"
    assert res["count"] == 10_000
    assert len(res["vertices"]) == 30_000
    plano = [c for v in esperado for c in v]
    assert max(abs(a - b) for a, b in zip(res["vertices"], plano, strict=True)) < 1e-5


@pytest.mark.parametrize("mensaje", [{}, {"t": "hola"}, {"t": None}, {"t": "nan"}])
def test_mensajes_sin_t_valido_no_llegan_a_la_calculadora(ws_cliente, mensaje):
    with ws_cliente.websocket_connect("/ws/morph", headers={"origin": ORIGEN}) as ws:
        ws.send_json(mensaje)
        assert ws.receive_json()["origen"] == "error"


def test_t_fuera_de_rango_lo_rechaza_la_calculadora(ws_cliente):
    with ws_cliente.websocket_connect("/ws/morph", headers={"origin": ORIGEN}) as ws:
        ws.send_json({"t": 5})
        res = ws.receive_json()
    assert res["origen"] == "error"
    assert "422" in res["error"]


def test_origen_no_permitido_se_cierra(ws_cliente):
    with pytest.raises(WebSocketDisconnect) as e:
        ajeno = {"origin": "http://evil.example"}
        with ws_cliente.websocket_connect("/ws/morph", headers=ajeno) as ws:
            ws.receive_json()
    assert e.value.code == 1008
