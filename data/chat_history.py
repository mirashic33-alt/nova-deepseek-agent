"""
data/chat_history.py — сохранение и загрузка истории чата.
Файл: workspace/chat_history.json
Формат: [{role, text, ts, elapsed?}, ...]
"""
import json
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
HISTORY_PATH = ROOT_DIR / "workspace" / "chat_history.json"
MEMORY_DIR = ROOT_DIR / "workspace" / "memory"

# Максимальная длина одного сообщения при сохранении
_MAX_MSG_CHARS = 15_000


def _limit() -> int:
    try:
        from data import config
        return config.get_history_limit()
    except Exception:
        return 100


def _ensure_dir():
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Загрузка ─────────────────────────────────────────────────────────────────

def load() -> list[dict]:
    """
    Загружает историю из файла.
    Возвращает список записей: [{role, text, ts, elapsed?}, ...]
    """
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[-_limit():]
    except Exception:
        pass
    return []


def to_openai_messages(system_prompt: str) -> list[dict]:
    """
    Конвертирует сохранённую историю в формат OpenAI для отправки в API.
    Изображения в DeepSeek не отправляются: фото и скриншоты сначала описывает Gemini Vision,
    а в историю попадает текстовое описание и путь к файлу.
    """
    messages = [{"role": "system", "content": system_prompt}]
    for entry in load():
        role = "user" if entry["role"] == "user" else "assistant"
        text = entry.get("text", "")
        messages.append({"role": role, "content": text})
    return messages


# ── Сохранение ───────────────────────────────────────────────────────────────

def _calc_pause_seconds(messages: list[dict]) -> float:
    """Вычисляет сколько секунд прошло между последним сообщением в истории и новым."""
    if not messages:
        return 0.0
    last = messages[-1]
    try:
        last_date = last.get("date", "")
        last_ts = last.get("ts", "")
        if not last_date or not last_ts:
            return 0.0
        last_dt = datetime.strptime(f"{last_date} {last_ts}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        delta = (now - last_dt).total_seconds()
        return max(0.0, delta)
    except (ValueError, TypeError):
        return 0.0


def append(role: str, text: str, elapsed: float = 0.0, image_path: str = None, image_b64: str = None) -> list[dict]:
    """
    Добавляет сообщение и сохраняет файл.
    role: "user" | "assistant"
    image_path: путь к фото (для дневного лога)
    image_b64: игнорируется — DeepSeek не поддерживает vision
    Возвращает обновлённый список.
    """
    if len(text) > _MAX_MSG_CHARS:
        text = text[:_MAX_MSG_CHARS] + "\n...[обрезано]"

    messages = load()
    pause = _calc_pause_seconds(messages)
    entry: dict = {
        "role": role,
        "text": text,
        "ts": datetime.now().strftime("%H:%M"),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    if elapsed:
        entry["elapsed"] = round(elapsed, 2)
    if pause:
        entry["pause_sec"] = round(pause)
    if image_path:
        entry["image_path"] = image_path
    # image_b64 не сохраняем — DeepSeek не поддерживает vision, только раздувает json

    messages.append(entry)
    if len(messages) > _limit():
        messages = messages[-_limit():]

    _save(messages)
    _append_daily(entry)
    return messages


def _append_daily(entry: dict) -> None:
    """Дописывает реплику в дневной файл workspace/memory/ГГГГ-ММ-ДД.md."""
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        day_file = MEMORY_DIR / f"{entry['date']}.md"
        label = "**User:**" if entry["role"] == "user" else "**Нова:**"
        text = entry["text"]
        if entry.get("image_path"):
            text += f"\n  📷 `{entry['image_path']}`"
        line = f"[{entry['ts']}] {label} {text}\n\n"
        with open(day_file, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def clear() -> None:
    """Очищает историю."""
    _ensure_dir()
    HISTORY_PATH.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")


def count() -> int:
    """Количество сообщений в истории."""
    return len(load())


# ── Внутреннее ───────────────────────────────────────────────────────────────

def _save(messages: list[dict]) -> None:
    _ensure_dir()
    HISTORY_PATH.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
