# repository.py

# POST /matrices no tiene límite ni expiración: sin tope, el repositorio en
# memoria crecería hasta agotar la memoria del contenedor.
MAX_MATRICES_GUARDADAS = 100


class RepositorioLleno(Exception):
    pass


class MatrixRepository:
    def __init__(self):
        self._data: dict[int, dict] = {}
        self._next_id = 1

    def crear(self, matriz: dict) -> dict:
        if len(self._data) >= MAX_MATRICES_GUARDADAS:
            raise RepositorioLleno(
                f"el repositorio está lleno: ya hay {MAX_MATRICES_GUARDADAS} "
                "matrices guardadas, el máximo permitido"
            )
        matriz["id"] = self._next_id
        self._data[self._next_id] = matriz
        self._next_id += 1
        return matriz

    def obtener(self, id: int) -> dict | None:
        return self._data.get(id)

    def listar(self) -> list[dict]:
        return list(self._data.values())
