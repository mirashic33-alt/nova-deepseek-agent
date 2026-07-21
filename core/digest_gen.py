"""
core/digest_gen.py — генератор ежедневного дайджеста.

Запускается при старте: если нет дайджеста за вчера — генерирует из лога.
"""
import logging
import threading
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger("digest_gen")

_WORKSPACE = Path(__file__).parent.parent / "workspace"
_MEMORY_DIR = _WORKSPACE / "memory"
_DIGESTS_DIR = _WORKSPACE / "digests"

_PROMPT = """Ты — Нова, DeepSeek-агент. Прочитай лог разговора за вчера и напиши себе письмо-дайджест.

Структура (8–12 пунктов):
1. Главные события и задачи дня
2. Что узнала about user или его проектах
3. Что сработало хорошо, что не получилось
4. Открытые хвосты (незакрытые вопросы)
5. Первый шаг на сегодня если понятно

Пиши коротко, по делу, от первого лица. Никаких вводных вроде "Дорогой дневник".

Лог за вчера:
{log_text}"""


def _last_digest_date() -> date | None:
    _DIGESTS_DIR.mkdir(exist_ok=True)
    files = sorted(_DIGESTS_DIR.glob("*.md"))
    if not files:
        return None
    try:
        return date.fromisoformat(files[-1].stem)
    except ValueError:
        return None


def _generate(yesterday: date) -> None:
    log_file = _MEMORY_DIR / f"{yesterday}.md"
    if not log_file.exists():
        log.info(f"Нет лога за {yesterday}, дайджест не нужен")
        return

    log_text = log_file.read_text(encoding="utf-8")
    if len(log_text.strip()) < 50:
        log.info(f"Лог за {yesterday} слишком короткий, пропускаем")
        return

    try:
        from data import config
        from openai import OpenAI
        api_key = config.get_api_key()
        model = config.get_model()
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _PROMPT.format(log_text=log_text[:8000])}],
            max_tokens=1500,
        )
        digest_text = response.choices[0].message.content or ""
        if not digest_text.strip():
            log.warning("Пустой ответ от DeepSeek, дайджест не сохранён")
            return

        out = _DIGESTS_DIR / f"{yesterday}.md"
        out.write_text(f"# Дайджест {yesterday}\n\n{digest_text}\n", encoding="utf-8")
        log.info(f"Дайджест за {yesterday} сохранён: {out}")
    except Exception as e:
        log.error(f"Ошибка генерации дайджеста: {e}")


def check_and_generate() -> None:
    """Вызывать при старте — проверяет и генерирует дайджест если нужно."""
    yesterday = date.today() - timedelta(days=1)
    last = _last_digest_date()
    if last and last >= yesterday:
        log.debug(f"Дайджест за {yesterday} уже есть, пропускаем")
        return
    log.info(f"Запускаем генерацию дайджеста за {yesterday}")
    _generate(yesterday)


def start_digest_check() -> None:
    """Запускает check_and_generate в фоновом потоке."""
    t = threading.Thread(target=check_and_generate, name="digest-gen", daemon=True)
    t.start()
