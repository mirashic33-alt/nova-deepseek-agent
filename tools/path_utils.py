"""
tools/path_utils.py — утилиты для работы с путями.

Содержит resolve_path и _ALIASES, вынесенные из file_tools.py,
чтобы избежать циклических импортов.
"""
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ALIASES: dict[str, str] = {
    "desktop:":   os.path.join(os.path.expanduser("~"), "Desktop"),
    "documents:": os.path.join(os.path.expanduser("~"), "Documents"),
    "downloads:": os.path.join(os.path.expanduser("~"), "Downloads"),
    "workspace:": os.path.join(_PROJECT_ROOT, "workspace"),
    "self:":      os.path.join(_PROJECT_ROOT, "workspace"),  # синоним workspace: — «мои файлы»
    "home:":      os.path.expanduser("~"),
    "project:":   _PROJECT_ROOT,   # ← корень проекта (tools/, core/, ui/ и т.д.)
}


def resolve_path(path: str) -> str:
    """Разворачивает псевдоним пути в абсолютный путь."""
    for alias, real in _ALIASES.items():
        if path.lower().startswith(alias):
            tail = path[len(alias):].lstrip("/\\")
            return os.path.join(real, tail) if tail else real
    return path
