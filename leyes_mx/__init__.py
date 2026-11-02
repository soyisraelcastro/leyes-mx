"""leyes_mx: base de leyes fiscales y laborales de Mexico, un archivo por articulo."""
from .store import obtener_articulo, buscar, listar_leyes, estado_reforma, normalizar_articulo  # noqa: F401

__version__ = "0.1.0"
