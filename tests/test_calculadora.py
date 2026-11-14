"""Pruebas de la calculadora que ya existían en main (línea base)."""


def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_multiplicar_por_id(cliente):
    a = cliente.post("/matrices", json={"nombre": "A", "datos": [[1, 2], [3, 4]]}).json()
    b = cliente.post("/matrices", json={"nombre": "B", "datos": [[5, 6], [7, 8]]}).json()
    r = cliente.post(f"/operaciones/multiplicar?id1={a['id']}&id2={b['id']}")
    assert r.json()["resultado"] == [[19, 22], [43, 50]]


def test_cadena_con_dimensiones_incompatibles_da_400(cliente):
    r = cliente.post(
        "/operaciones/multiplicar-cadena",
        json={"matrices": [[[1, 2, 3]], [[1, 2], [3, 4]]]},
    )
    assert r.status_code == 400


def test_transformacion_rota_y_escala(cliente):
    r = cliente.post("/operaciones/transformacion", json={"tx": 1, "rz": 90, "s": 2})
    m = r.json()["resultado"]
    esperado = [[0, -2, 0, 1], [2, 0, 0, 0], [0, 0, 2, 0], [0, 0, 0, 1]]
    for fila, fila_esperada in zip(m, esperado, strict=True):
        for v, e in zip(fila, fila_esperada, strict=True):
            assert abs(v - e) < 1e-9


def test_matriz_demasiado_grande_se_rechaza(cliente):
    grande = [[1.0] * 51] * 51
    r = cliente.post("/matrices", json={"nombre": "G", "datos": grande})
    assert r.status_code == 422


def test_repositorio_de_matrices_tiene_tope(cliente):
    for i in range(100):
        cliente.post("/matrices", json={"nombre": f"M{i}", "datos": [[1]]})
    r = cliente.post("/matrices", json={"nombre": "sobra", "datos": [[1]]})
    assert r.status_code == 409
