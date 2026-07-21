"""
data/config.py — конфигурация проекта.
Настройки хранятся в data/config.json; секреты — в keystore (DPAPI).
"""
import json
from pathlib import Path

# Корень проекта — папка выше data/
ROOT_DIR = Path(__file__).parent.parent

# Путь к файлу конфига
CONFIG_PATH = ROOT_DIR / "data" / "config.json"

# Дефолты
#
# ВАЖНО ДЛЯ LLM-АГЕНТОВ:
# Не менять названия моделей по памяти или по старому обучению модели.
# Перед заменой model id обязательно проверить официальные docs/API:
# - DeepSeek: https://api-docs.deepseek.com/api/list-models/
# - Gemini: https://ai.google.dev/gemini-api/docs/
# Старые алиасы вроде deepseek-chat/deepseek-reasoner и preview-модели
# могут быть deprecated или уже отключены.
_DEFAULTS = {
    "model": "deepseek-v4-pro",
    "max_tokens": 8192,
    "temperature": 0.7,
    "history_limit": 100,
    "tool_rounds": 30,
    "ping_interval": 5,
    "ping_topic": "",
    "image_size": "2K",
}

# ── Кеш (читается один раз при первом обращении) ────────────────────────────

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        if CONFIG_PATH.exists():
            try:
                _cache = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                _cache = {}
        else:
            _cache = {}
    return _cache

def _save(cfg: dict) -> None:
    global _cache
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    _cache = cfg

# ── Публичные геттеры ────────────────────────────────────────────────────────

def get_api_key() -> str:
    from data import keystore
    return keystore.get("DEEPSEEK_API_KEY")

def get_gemini_key() -> str:
    from data import keystore
    return keystore.get("GEMINI_API_KEY")

def get_model() -> str:
    return _load().get("model", _DEFAULTS["model"])


def get_vision_model() -> str:
    """Модель для обработки фото и скриншотов через Gemini Vision."""
    return "gemini-2.5-flash"

def get_max_tokens() -> int:
    return int(_load().get("max_tokens", _DEFAULTS["max_tokens"]))

def get_temperature() -> float:
    return float(_load().get("temperature", _DEFAULTS["temperature"]))

def get_image_size() -> str:
    value = str(_load().get("image_size", _DEFAULTS["image_size"])).upper()
    return value if value in {"1K", "2K", "4K"} else _DEFAULTS["image_size"]

def set_image_size(v: str) -> None:
    value = str(v).upper()
    if value not in {"1K", "2K", "4K"}:
        value = _DEFAULTS["image_size"]
    cfg = _load()
    cfg["image_size"] = value
    _save(cfg)


# ── Публичные сеттеры ────────────────────────────────────────────────────────

def set_model(value: str) -> None:
    cfg = _load()
    cfg["model"] = value
    _save(cfg)

def get_history_limit() -> int:
    return int(_load().get("history_limit", _DEFAULTS["history_limit"]))

def set_history_limit(v: int) -> None:
    cfg = _load()
    cfg["history_limit"] = v
    _save(cfg)

def get_tool_rounds() -> int:
    return int(_load().get("tool_rounds", _DEFAULTS["tool_rounds"]))

def set_tool_rounds(v: int) -> None:
    cfg = _load()
    cfg["tool_rounds"] = v
    _save(cfg)

# ── Telegram ────────────────────────────────────────────────────────────────────

def get_tg_token() -> str:
    return _load().get("tg_token", "")

def set_tg_token(v: str) -> None:
    cfg = _load()
    cfg["tg_token"] = v
    _save(cfg)

def get_tg_chat_id() -> int:
    return int(_load().get("tg_chat_id", 0))

def set_tg_chat_id(v: int) -> None:
    cfg = _load()
    cfg["tg_chat_id"] = v
    _save(cfg)

def is_tg_configured() -> bool:
    """True если токен и chat_id заполнены."""
    return bool(get_tg_token()) and get_tg_chat_id() != 0

# ── Пинк-таймер ──────────────────────────────────────────────────────────────────

def get_ping_interval() -> int:
    """Интервал авто-пинка в минутах."""
    return int(_load().get("ping_interval", _DEFAULTS["ping_interval"]))

def set_ping_interval(v: int) -> None:
    cfg = _load()
    cfg["ping_interval"] = v
    _save(cfg)

def get_ping_topic() -> str:
    """Тема для авто-пинка (пусто = свободный полёт)."""
    return _load().get("ping_topic", _DEFAULTS["ping_topic"])

def set_ping_topic(v: str) -> None:
    cfg = _load()
    cfg["ping_topic"] = v.strip()
    _save(cfg)

# ── ElevenLabs (озвучка) ─────────────────────────────────────────────────────

def get_eleven_key() -> str:
    from data import keystore
    return keystore.get("ELEVENLABS_API_KEY")

def get_eleven_voice() -> str:
    return _load().get("eleven_voice_id", "ycbyWsnf4hqZgdpKHqiU")

def set_eleven_voice(v: str) -> None:
    cfg = _load()
    cfg["eleven_voice_id"] = v
    _save(cfg)
