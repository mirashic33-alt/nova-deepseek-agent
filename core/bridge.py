"""
core/bridge.py — Qt сигнальный мост.
Позволяет фоновым потокам безопасно отправлять данные в UI.
"""
from PySide6.QtCore import QObject, Signal


class AgentBridge(QObject):
    """Сигналы между worker/telegram-потоком и главным окном."""

    # ── Основной цикл ─────────────────────────────────────────────────────────
    response_ready  = Signal(str)   # финальный ответ агента
    status_changed  = Signal(str)   # обновление статусбара
    error_occurred  = Signal(str)   # критическая ошибка

    # Промежуточные события: "[tool]⚙ tool_name(args)" или простой текст
    interim         = Signal(str)

    # Токены: (prompt_tokens, completion_tokens) — сумма по всем раундам
    token_info      = Signal(int, int)

    # ── Telegram ──────────────────────────────────────────────────────────────
    # Сообщение пришло из Telegram — показать в чате UI
    tg_user_message = Signal(str, str)   # (ts, text)
    # Ответ агента отправлен в Telegram — показать в чате UI
    tg_agent_message = Signal(str, str)  # (ts, text)
    # Промежуточный статус из Telegram-потока
    tg_interim       = Signal(str)

    # История изменилась (очистка через /clear)
    history_cleared  = Signal()

    # Картинка сгенерирована — путь к файлу
    image_ready      = Signal(str)
