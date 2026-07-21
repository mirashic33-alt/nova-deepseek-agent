"""
tools/__init__.py — сборка всех инструментов и OpenAI-схем.
"""
import inspect
import json
from tools.file_tools import ALL_TOOLS as FILE_TOOLS
from tools.shell_tools import ALL_SHELL_TOOLS as SHELL_TOOLS
from tools.image_tools import ALL_IMAGE_TOOLS as IMAGE_TOOLS
from tools.screenshot_tools import ALL_SCREENSHOT_TOOLS as SCREENSHOT_TOOLS
from tools.mail_tools import ALL_MAIL_TOOLS as MAIL_TOOLS
from tools.telegram_tools import ALL_TELEGRAM_TOOLS as TELEGRAM_TOOLS
ALL_TOOLS = FILE_TOOLS + SHELL_TOOLS + IMAGE_TOOLS + SCREENSHOT_TOOLS + MAIL_TOOLS + TELEGRAM_TOOLS


# ── Генератор OpenAI JSON-схем из Python-функций ─────────────────────────────

_PY_TO_JSON = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
}


def _build_schema(fn) -> dict:
    """Строит OpenAI tool-schema из сигнатуры и docstring функции."""
    sig = inspect.signature(fn)
    doc = (fn.__doc__ or "").strip()
    # Первая строка docstring — краткое описание
    description = doc.split("\n")[0].strip()

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        ann = param.annotation
        if ann is inspect.Parameter.empty:
            json_type = "string"
        else:
            type_name = ann.__name__ if hasattr(ann, "__name__") else str(ann)
            json_type = _PY_TO_JSON.get(type_name, "string")

        properties[name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# Готовые схемы для DeepSeek API
ALL_SCHEMAS: list[dict] = [_build_schema(fn) for fn in ALL_TOOLS]

# Словарь: имя → функция (для быстрого вызова по имени)
TOOL_MAP: dict[str, callable] = {fn.__name__: fn for fn in ALL_TOOLS}
