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


# Las figuras guardadas tampoco expiran: el mismo tope que las matrices.
MAX_FIGURAS_GUARDADAS = 100


class NombreEnUso(Exception):
    pass


class FiguraRepository:
    """Figuras del morph guardadas con nombre.

    Guardar es idempotente por nombre: repetir la misma petición devuelve la
    figura que ya existe en lugar de crear otra. Usar el nombre con otros
    valores de t o resolucion es un conflicto, no una sobreescritura.
    """

    def __init__(self):
        self._data: dict[int, dict] = {}
        self._por_nombre: dict[str, int] = {}
        self._next_id = 1

    def guardar(self, figura: dict) -> tuple[dict, bool]:
        """Devuelve (figura, creada). creada es False si ya existía igual."""
        clave = figura["nombre"].casefold()
        if clave in self._por_nombre:
            existente = self._data[self._por_nombre[clave]]
            mismos = all(existente[k] == figura[k] for k in ("t", "resolucion"))
            if not mismos:
                raise NombreEnUso(
                    f"ya existe una figura llamada {existente['nombre']!r} con otros valores"
                )
            return existente, False
        if len(self._data) >= MAX_FIGURAS_GUARDADAS:
            raise RepositorioLleno(
                f"ya hay {MAX_FIGURAS_GUARDADAS} figuras guardadas, el máximo permitido"
            )
        figura = {"id": self._next_id, **figura}
        self._data[self._next_id] = figura
        self._por_nombre[clave] = self._next_id
        self._next_id += 1
        return figura, True

    def obtener(self, id: int) -> dict | None:
        return self._data.get(id)

    def listar(self) -> list[dict]:
        return list(self._data.values())
