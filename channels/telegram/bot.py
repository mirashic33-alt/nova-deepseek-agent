"""
channels/telegram/bot.py — Telegram бот агента DeepSeek.

Работает в отдельном потоке.
Принимает сообщения только от авторизованного TELEGRAM_CHAT_ID.
Отправляет промежуточные уведомления об инструментах.
"""
import asyncio
import io
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from telegram.constants import ChatAction


from core import agent_loop
from data import chat_history, config

import logging
log = logging.getLogger("telegram_bot")

# Папка для входящих фото (оригиналы)
_INCOMING_DIR = Path(__file__).parent.parent.parent / "workspace" / "images" / "incoming"

# Хранилище текстов для кнопки озвучки: message_id -> текст
_voice_texts: dict = {}

import urllib.request
import json as _json


def _clean_for_tts(text: str) -> str:
    """Убираем markdown, код, ссылки — оставляем только живую речь."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"`{1,3}.*?`{1,3}", "", text, flags=re.DOTALL)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _eleven_tts(text: str) -> bytes:
    """Синтез речи через ElevenLabs. Возвращает opus/ogg байты."""
    from data import config as _cfg
    key = _cfg.get_eleven_key()
    voice_id = _cfg.get_eleven_voice()
    body = _json.dumps({
        "text": text[:2500],
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.8,
            "style": 0.1,
            "use_speaker_boost": True,
            "speed": 0.95
        },
    }).encode("utf-8")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=opus_48000_64"
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _md_to_tg(text: str) -> str:
    """Markdown → Telegram HTML (parse_mode='HTML')."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'^#{1,3}\s+(.+)', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^`{3}.*?^`{3}', lambda m: f'<pre>{m.group()}</pre>',
                  text, flags=re.MULTILINE | re.DOTALL)
    return text


_TG_LIMIT = 4000  # Telegram max 4096, оставляем запас


def _fmt_tokens(n: int) -> str:
    """Форматирует число токенов: 221000 → 221.0K, 500 → 500."""
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def _split(text: str) -> list[str]:
    """Разбить текст на куски для Telegram."""
    if len(text) <= _TG_LIMIT:
        return [text]
    chunks = []
    while text:
        if len(text) <= _TG_LIMIT:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, _TG_LIMIT)
        if cut == -1:
            cut = _TG_LIMIT
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


class TelegramBot:
    """Telegram бот, запускаемый в daemon-потоке."""

    def __init__(self, token: str, chat_id: int, bridge):
        self._token   = token
        self._chat_id = chat_id
        self._bridge  = bridge
        self._app     = None
        self._loop    = None
        self._thread  = None

    def start(self):
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="telegram-bot"
        )
        self._thread.start()
        log.info("Telegram bot thread started.")

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main())
        except Exception as exc:
            log.error(f"Telegram bot crashed: {exc}", exc_info=True)

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        log.info(f"Connecting bot (chat_id={self._chat_id})")
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("clear", self._cmd_clear))
        self._app.add_handler(CallbackQueryHandler(self._on_voice_button, pattern=r"^say:\d+$"))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )
        self._app.add_handler(
            MessageHandler(filters.PHOTO, self._on_photo)
        )
        async with self._app:
            await self._app.start()
            await self._app.bot.set_my_commands([
                BotCommand("start", "Статус агента"),
                BotCommand("clear", "Очистить историю"),
            ])
            await self._app.updater.start_polling(drop_pending_updates=True)
            log.info("Telegram polling started.")
            try:
                from data import config as _cfg
                model = _cfg.get_model()
                await self._app.bot.send_message(
                    self._chat_id,
                    f"🔵 Нова снова на связи.\nМодель: <code>{model}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            await asyncio.Event().wait()  # ждём до остановки

    # ── Thread-safe методы (вызываются из Qt потока) ─────────────────────────

    def post_message(self, text: str, html: bool = False):
        """Отправить текст в Telegram из любого потока."""
        if not (self._loop and self._app):
            return
        for chunk in _split(text):
            asyncio.run_coroutine_threadsafe(
                self._app.bot.send_message(
                    chat_id=self._chat_id,
                    text=chunk if html else _md_to_tg(chunk),
                    parse_mode="HTML",
                ),
                self._loop,
            )

    def post_photo(self, path: str, caption: str = ""):
        """Отправить фото в Telegram из любого потока."""
        if not (self._loop and self._app):
            return
        async def _send():
            try:
                file_path = Path(path)
                size = file_path.stat().st_size
                with file_path.open("rb") as f:
                    if size <= 10 * 1024 * 1024:
                        await self._app.bot.send_photo(
                            chat_id=self._chat_id,
                            photo=f,
                            caption=caption or None,
                        )
                    else:
                        await self._app.bot.send_document(
                            chat_id=self._chat_id,
                            document=f,
                            caption=caption or f"Картинка слишком большая для sendPhoto, отправляю файлом: {file_path.name}",
                        )
            except Exception as exc:
                log.error(f"send_photo failed: {exc}")
        asyncio.run_coroutine_threadsafe(_send(), self._loop)

    def post_typing(self):
        if self._loop and self._app:
            asyncio.run_coroutine_threadsafe(
                self._app.bot.send_chat_action(
                    chat_id=self._chat_id, action=ChatAction.TYPING
                ),
                self._loop,
            )

    # ── Авторизация ──────────────────────────────────────────────────────────

    def _is_setup_mode(self) -> bool:
        return self._chat_id == 0

    def _is_authorized(self, update: Update) -> bool:
        cid = update.effective_chat.id
        if cid != self._chat_id:
            log.warning(f"Rejected from chat_id={cid}")
            return False
        return True

    # ── Команды ──────────────────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, _ctx):
        cid = update.effective_chat.id
        if self._is_setup_mode():
            await update.message.reply_text(
                f"Твой chat_id: <b>{cid}</b>\n\nВставь его в Настройки приложения и перезапусти.",
                parse_mode="HTML",
            )
            return
        if not self._is_authorized(update):
            return
        model = config.get_model()
        await update.message.reply_text(
            f"<b>DeepSeek Agent</b> онлайн.\nМодель: <code>{model}</code>",
            parse_mode="HTML",
        )

    async def _cmd_clear(self, update: Update, _ctx):
        if not self._is_authorized(update):
            return
        chat_history.clear()
        self._bridge.history_cleared.emit()
        await update.message.reply_text("История чата очищена.")
        log.info("History cleared via /clear")

    async def _on_voice_button(self, update: Update, context):
        """Нажали '🔊 Озвучить' — синтезируем голос и шлём голосовым сообщением."""
        q = update.callback_query
        if not q:
            return
        await q.answer("Озвучиваю…")
        try:
            mid = int(q.data.split(":")[1])
        except (ValueError, IndexError):
            return
        text = _voice_texts.get(mid)
        if not text:
            await q.answer("Ответ устарел — перезапустилась, текст потерян.")
            return
        speech = _clean_for_tts(text)
        if not speech:
            await q.answer("Нечего озвучивать.")
            return
        try:
            audio = await asyncio.to_thread(_eleven_tts, speech)
            await self._app.bot.send_voice(
                chat_id=self._chat_id,
                voice=audio,
                reply_to_message_id=mid,
            )
        except Exception as exc:
            log.error(f"ElevenLabs TTS failed: {exc}")
            await self._app.bot.send_message(
                chat_id=self._chat_id,
                text=f"Не смогла озвучить: {exc}"
            )

    # ── Входящее сообщение ───────────────────────────────────────────────────

    async def _on_message(self, update: Update, context):
        if not self._is_authorized(update):
            return

        text = update.message.text.strip()
        if not text:
            return

        ts = datetime.now().strftime("%H:%M")
        log.info(f"← TG: {text[:80]}")

        # Показать в UI
        self._bridge.tg_user_message.emit(ts, text)

        # Сохранить в историю
        chat_history.append("user", text)

        # Начать индикатор набора — сразу и каждые 4 секунды
        start_time = time.monotonic()
        stop_typing = threading.Event()

        def _send_typing():
            if self._loop and self._app:
                asyncio.run_coroutine_threadsafe(
                    context.bot.send_chat_action(
                        chat_id=self._chat_id, action=ChatAction.TYPING
                    ),
                    self._loop,
                )

        def _typing_loop():
            _send_typing()                    # ← сразу, не ждём 4 секунды
            while not stop_typing.wait(timeout=4):
                _send_typing()               # ← каждые 4 секунды

        typing_thread = threading.Thread(target=_typing_loop, daemon=True)
        typing_thread.start()

        # Callback для промежуточных уведомлений
        def _on_interim(interim_text: str):
            self._bridge.tg_interim.emit(interim_text)
            if interim_text.startswith("[tool]"):
                label = interim_text[6:]
                if self._loop and self._app:
                    asyncio.run_coroutine_threadsafe(
                        self._app.bot.send_message(
                            chat_id=self._chat_id,
                            text=label,
                        ),
                        self._loop,
                    )

        # Защита от дубликатов картинок
        _sent_images = set()

        def _on_image(path: str):
            nonlocal _sent_images
            if path in _sent_images:
                return
            _sent_images.add(path)
            # Только сигнал в UI — main_window сам отправит в TG
            self._bridge.image_ready.emit(path)

        # Запускаем агентный цикл в потоке (он синхронный)
        from core.memory_loader import load_system_prompt
        messages = chat_history.to_openai_messages(load_system_prompt())

        try:
            response, usage = await asyncio.to_thread(
                agent_loop.run, messages, _on_interim, _on_image
            )
        except Exception as exc:
            stop_typing.set()
            log.error(f"Agent error: {exc}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {exc}")
            return
        finally:
            stop_typing.set()

        elapsed = time.monotonic() - start_time
        ts_resp = datetime.now().strftime("%H:%M")
        log.info(f"→ TG response ({elapsed:.1f}s): {response[:80]}")

        # Сохранить ответ
        chat_history.append("assistant", response, elapsed=elapsed)

        # Показать в UI
        self._bridge.tg_agent_message.emit(ts_resp, response)

        # Отправить в Telegram с кнопкой озвучки
        token_str = ""
        if usage:
            token_str = f" · 📥{_fmt_tokens(usage['prompt'])}📤{_fmt_tokens(usage['completion'])}"
        footer = f"\n\n⏱ {elapsed:.1f}с{token_str}"
        tg_text = response + footer
        chunks = _split(_md_to_tg(tg_text))
        last_msg = None
        for chunk in chunks:
            last_msg = await update.message.reply_text(chunk, parse_mode="HTML")
        # Кнопка озвучки — только под последним чанком
        if last_msg and response.strip():
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔊 Озвучить", callback_data=f"say:{last_msg.message_id}")
            ]])
            await last_msg.edit_reply_markup(reply_markup=kb)
            _voice_texts[last_msg.message_id] = response
            # Чистим старые (держим последние 40)
            while len(_voice_texts) > 40:
                _voice_texts.pop(next(iter(_voice_texts)))

    # ── Входящее фото ────────────────────────────────────────────────────────

    async def _on_photo(self, update: Update, context):
        if not self._is_authorized(update):
            return

        ts = datetime.now().strftime("%H:%M")

        # Получаем фото максимального размера
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        # Скачиваем в память
        img_bytes = io.BytesIO()
        await file.download_to_memory(img_bytes)
        img_bytes.seek(0)
        raw = img_bytes.getvalue()

        # Сохраняем оригинал
        _INCOMING_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        orig_path = _INCOMING_DIR / f"photo_{stamp}.jpg"
        orig_path.write_bytes(raw)
        log.info(f"← TG photo: {orig_path} ({len(raw):,} bytes)")

        # Текст: caption или авто; путь добавляем чтобы Нова могла read_file
        caption = (update.message.caption or "").strip()
        text = caption if caption else "[User sent a photo]"

        log.info(f"← TG photo text: {text[:80]}")

        # Показать в UI
        self._bridge.tg_user_message.emit(ts, f"📷 {text}")

        # Анализируем картинку через Gemini Vision (DeepSeek не поддерживает vision)
        try:
            from tools.image_tools import analyze_image
            result = analyze_image(str(orig_path), caption)
            desc = result.get("result") or result.get("error", str(result))
        except Exception as exc:
            desc = f"[Анализ не удался: {exc}]"
        log.info(f"← Gemini Vision analysis: {desc[:120]}")

        text_with_desc = (
            f"{text}\n"
            f"Путь к файлу: {orig_path}\n\n"
            f"[Gemini описывает картинку:]\n{desc}"
        )

        # Сохранить в историю (только текст, без сырого изображения)
        chat_history.append("user", text_with_desc, image_path=str(orig_path))

        # Индикатор набора
        start_time = time.monotonic()
        stop_typing = threading.Event()

        def _send_typing():
            if self._loop and self._app:
                asyncio.run_coroutine_threadsafe(
                    context.bot.send_chat_action(
                        chat_id=self._chat_id, action=ChatAction.TYPING
                    ),
                    self._loop,
                )

        def _typing_loop():
            _send_typing()
            while not stop_typing.wait(timeout=4):
                _send_typing()

        typing_thread = threading.Thread(target=_typing_loop, daemon=True)
        typing_thread.start()

        def _on_interim(interim_text: str):
            self._bridge.tg_interim.emit(interim_text)
            if interim_text.startswith("[tool]"):
                label = interim_text[6:]
                if self._loop and self._app:
                    asyncio.run_coroutine_threadsafe(
                        self._app.bot.send_message(
                            chat_id=self._chat_id,
                            text=label,
                        ),
                        self._loop,
                    )

        # Защита от дубликатов картинок
        _sent_images = set()

        def _on_image(path: str):
            nonlocal _sent_images
            if path in _sent_images:
                return
            _sent_images.add(path)
            # Только сигнал в UI — main_window сам отправит в TG
            self._bridge.image_ready.emit(path)

        from core.memory_loader import load_system_prompt
        messages = chat_history.to_openai_messages(load_system_prompt())

        try:
            response, usage = await asyncio.to_thread(
                agent_loop.run, messages, _on_interim, _on_image
            )
        except Exception as exc:
            stop_typing.set()
            log.error(f"Agent error (photo): {exc}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {exc}")
            return
        finally:
            stop_typing.set()

        elapsed = time.monotonic() - start_time
        ts_resp = datetime.now().strftime("%H:%M")
        log.info(f"→ TG photo response ({elapsed:.1f}s): {response[:80]}")

        chat_history.append("assistant", response, elapsed=elapsed)
        self._bridge.tg_agent_message.emit(ts_resp, response)

        token_str = ""
        if usage:
            token_str = f" · 📥{_fmt_tokens(usage['prompt'])}📤{_fmt_tokens(usage['completion'])}"
        footer = f"\n\n⏱ {elapsed:.1f}с{token_str}"
        tg_text = response + footer
        chunks = _split(_md_to_tg(tg_text))
        last_msg = None
        for chunk in chunks:
            last_msg = await update.message.reply_text(chunk, parse_mode="HTML")
        if last_msg and response.strip():
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔊 Озвучить", callback_data=f"say:{last_msg.message_id}")
            ]])
            await last_msg.edit_reply_markup(reply_markup=kb)
            _voice_texts[last_msg.message_id] = response
            while len(_voice_texts) > 40:
                _voice_texts.pop(next(iter(_voice_texts)))

