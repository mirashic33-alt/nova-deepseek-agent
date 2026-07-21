"""
tools/telegram_tools.py — отправка локальных файлов to user в Telegram.
"""
from pathlib import Path

import requests

from data import config
from tools.path_utils import resolve_path


_PHOTO_LIMIT = 10 * 1024 * 1024
_DOCUMENT_LIMIT = 50 * 1024 * 1024
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _err(message: str) -> dict:
    return {"status": "error", "error": message}


def _ok(message: str) -> dict:
    return {"status": "ok", "result": message}


def send_telegram_file(path: str, caption: str = "", mode: str = "auto") -> dict:
    """
    Отправить локальный файл to user в Telegram.
    path поддерживает алиасы desktop:, workspace:, downloads:, documents:, project:.
    mode: auto | photo | document. Для больших картинок auto отправляет документом.
    Пример: send_telegram_file("workspace:images/gen_20260718_195213.png")
    """
    token = config.get_tg_token()
    chat_id = config.get_tg_chat_id()
    if not token or not chat_id:
        return _err("Telegram token/chat_id не настроены.")

    real = Path(resolve_path(path))
    if not real.exists():
        return _err(f"Файл не найден: {path}")
    if not real.is_file():
        return _err(f"Это не файл: {path}")

    size = real.stat().st_size
    if size > _DOCUMENT_LIMIT:
        return _err(
            f"Файл слишком большой для Telegram Bot API: {size:,} байт "
            f"(лимит sendDocument около {_DOCUMENT_LIMIT:,} байт)."
        )

    selected = (mode or "auto").lower().strip()
    if selected not in {"auto", "photo", "document"}:
        selected = "auto"

    is_image = real.suffix.lower() in _IMAGE_EXTS
    use_photo = selected == "photo" or (selected == "auto" and is_image and size <= _PHOTO_LIMIT)
    endpoint = "sendPhoto" if use_photo else "sendDocument"
    field = "photo" if use_photo else "document"
    url = f"https://api.telegram.org/bot{token}/{endpoint}"

    try:
        with real.open("rb") as fh:
            response = requests.post(
                url,
                data={"chat_id": str(chat_id), "caption": caption[:1024]},
                files={field: (real.name, fh)},
                timeout=120,
            )
    except Exception as exc:
        return _err(f"Ошибка отправки в Telegram: {exc}")

    if response.status_code != 200:
        return _err(f"Telegram {endpoint} вернул {response.status_code}: {response.text[:500]}")

    sent_as = "фото" if use_photo else "документ"
    return _ok(f"Отправлено в Telegram как {sent_as}: {real} ({size:,} байт)")


ALL_TELEGRAM_TOOLS = [send_telegram_file]
