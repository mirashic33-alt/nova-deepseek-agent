"""
core/agent_loop.py — агентный цикл с вызовом инструментов (OpenAI tool-calling).

on_interim callback получает строки:
  "[tool]⚙ tool_name(arg='val')"  — до вызова инструмента
  "[tool]✅ result_short"          — после (только если успех)
  "[tool]❌ error"                 — после (если ошибка)
"""
import json
import logging
import re

from llm.provider import DeepSeekProvider
from tools import ALL_SCHEMAS, TOOL_MAP
from data import config

log = logging.getLogger(__name__)


_PHOTO_RE = re.compile(r'\[\[ФОТО:\s*([^\]]+)\]\]')
_IMAGE_REQUEST_RE = re.compile(
    r"(?i)\b("
    r"нарисуй|сгенерируй\s+(?:картинку|изображение|фото)|"
    r"создай\s+(?:картинку|изображение|фото)|"
    r"изобрази|сделай\s+(?:картинку|изображение|фото)|"
    r"draw|generate\s+(?:an\s+)?image|create\s+(?:an\s+)?image"
    r")\b"
)


def _last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content") or ""
            if isinstance(content, str):
                return content
            return str(content)
    return ""


def _needs_image_tool(messages: list[dict]) -> bool:
    text = _last_user_text(messages)
    return bool(_IMAGE_REQUEST_RE.search(text))


def run(
    messages: list[dict],
    on_interim=None,   # callback(str) — для UI и Telegram
    on_image=None,     # callback(path: str) — когда картинка готова
    model=None,        # str — переопределить модель (например для vision)
):
    """
    Запускает агентный цикл с tool-calling.
    messages — история в формате OpenAI (включая системный промт).
    on_interim — опциональный callback для промежуточных уведомлений.
    model — если задана, используется вместо модели из конфига.
    Возвращает (текст_ответа, usage_dict | None).
    usage_dict: {"prompt": N, "completion": N} — сумма по всем раундам.
    """
    provider = DeepSeekProvider()
    if model:
        provider.model = model
    msgs = list(messages)
    max_rounds = config.get_tool_rounds()
    total_prompt_tokens = 0
    total_completion_tokens = 0
    wants_image = _needs_image_tool(msgs)
    if wants_image:
        msgs.append({
            "role": "system",
            "content": (
                "[CONTEXT] Последний запрос пользователя просит создать изображение. "
                "Если это возможно, сначала вызови инструмент generate_image с подходящим промптом. "
                "Не отвечай, что картинка создана, пока инструмент реально не был вызван."
            ),
        })

    for round_num in range(max_rounds):
        tool_choice = "auto"
        # Логируем размер запроса перед отправкой
        total_chars = sum(len(str(m.get("content") or "")) for m in msgs)
        log.info(
            "→ API запрос: раунд=%d модель=%s сообщений=%d ~%d симв. tool_choice=%s",
            round_num + 1, provider.model, len(msgs), total_chars, tool_choice
        )
        try:
            response = provider.client.chat.completions.create(
                model=provider.model,
                messages=msgs,
                tools=ALL_SCHEMAS,
                tool_choice=tool_choice,
                max_tokens=provider.max_tokens,
                temperature=provider.temperature,
                timeout=90,   # секунд — не ждём бесконечно
            )
            if response is None or not response.choices:
                log.error("API вернул пустой ответ (раунд %d)", round_num + 1)
                return "[Ошибка: API вернул пустой ответ. Попробуй ещё раз.]", None

            choice = response.choices[0]
            msg = choice.message

            # Собираем токены
            if response.usage:
                total_prompt_tokens += response.usage.prompt_tokens or 0
                total_completion_tokens += response.usage.completion_tokens or 0

        except Exception as api_err:
            log.error("API ошибка (раунд %d): %s", round_num + 1, api_err)
            return f"[Ошибка API: {api_err}]", None

        # Нет вызовов инструментов → финальный ответ
        if not msg.tool_calls:
            content = msg.content or ""
            usage = None
            if total_prompt_tokens or total_completion_tokens:
                usage = {"prompt": total_prompt_tokens, "completion": total_completion_tokens}
            return content, usage

        # Добавляем assistant message с tool_calls
        msgs.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        # Выполняем каждый инструмент
        called_tools = []  # собираем список вызванных инструментов
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            # Краткое представление аргументов
            args_short = ", ".join(f"{k}={str(v)[:40]!r}" for k, v in args.items())

            log.info("Tool call: %s(%s)", tool_name, args)

            # Уведомляем — ДО вызова
            if on_interim:
                on_interim(f"[tool]⚙ {tool_name}({args_short})")

            # Вызываем инструмент
            fn = TOOL_MAP.get(tool_name)
            if fn is None:
                result = {"status": "error", "error": f"Инструмент '{tool_name}' не найден."}
            else:
                try:
                    result = fn(**args)
                except Exception as e:
                    result = {"status": "error", "error": str(e)}

            if not isinstance(result, dict):
                result = {"status": "ok", "result": str(result)}

            log.info("Tool result: %s → %s", tool_name, str(result)[:200])

            # Уведомляем — ПОСЛЕ вызова
            if result.get("status") == "ok":
                result_str = str(result.get("result", ""))
                if on_interim:
                    on_interim(f"[tool]✅ {tool_name} → {result_str[:120]}")
                # Если generate_image вернул картинку — сообщаем UI/Telegram.
                # Не сканируем результаты read_file/run_shell: там могут быть
                # примеры кода или строки логов с [[ФОТО: ...]], не реальные файлы.
                if on_image and tool_name == "generate_image":
                    for m in _PHOTO_RE.finditer(result_str):
                        on_image(m.group(1).strip())
            else:
                if on_interim:
                    on_interim(f"[tool]❌ {tool_name}: {result.get('error', '?')}")

            # Добавляем результат в историю
            msgs.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

            called_tools.append(tool_name)

        # ── Строка правды (идея Ады) ──────────────────────────────────────
        # Сообщаем модели какие инструменты реально были вызваны.
        # Это помогает избежать "симуляции" действий: модель видит факт
        # и не может притвориться что сделала то, чего не делала.
        tools_summary = ", ".join(called_tools) if called_tools else "нет"
        msgs.append({
            "role": "system",
            "content": (
                f"[CONTEXT] Раунд {round_num + 1}: вызванные инструменты: {tools_summary}. "
                "Отвечай только о том, что реально сделано через инструменты выше."
            ),
        })

    usage = None
    if total_prompt_tokens or total_completion_tokens:
        usage = {"prompt": total_prompt_tokens, "completion": total_completion_tokens}
    return "[Агент: превышен лимит раундов инструментов]", usage
