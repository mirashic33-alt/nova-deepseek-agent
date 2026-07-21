"""
data/logger.py — настройка файлового лога agent.log.

Лог пишется в корень проекта: agent.log
При каждом запуске лог очищается (mode='w').
Размер ограничен — пишутся только INFO+ сообщения нашего кода.
"""
import logging
import logging.handlers
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
LOG_PATH  = ROOT_DIR / "agent.log"
LOG1_PATH = ROOT_DIR / "agent.log.1"

_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_DATE   = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_file_logging():
    """
    Добавляет FileHandler к корневому логгеру.
    Лог очищается при каждом старте (mode='w').
    Вызывать один раз при старте приложения.
    """
    global _configured
    if _configured:
        return
    _configured = True

    # Удаляем старый архив если остался
    LOG1_PATH.unlink(missing_ok=True)

    # mode='w' — очищаем лог при каждом старте
    handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE))

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Подавляем шумные библиотечные логи
    for noisy in ("httpx", "httpcore", "telegram", "urllib3", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
