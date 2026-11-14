"""Fixtures compartidas.

Las pruebas importan la calculadora como paquete de módulos sueltos
(main, models, services, repository), igual que la arranca uvicorn dentro
de su contenedor.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

CALCULADORA = Path(__file__).resolve().parents[1] / "calculadora_matrices"
sys.path.insert(0, str(CALCULADORA))

import main  # noqa: E402


@pytest.fixture
def app_calculadora():
    """La app con repositorios vacíos en cada prueba."""
    main.repo = main.MatrixRepository()
    if hasattr(main, "figuras"):
        main.figuras = main.FiguraRepository()
    return main.app


@pytest.fixture
def cliente(app_calculadora):
    return TestClient(app_calculadora)
