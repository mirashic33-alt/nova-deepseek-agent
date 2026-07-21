"""
ui/main_window.py — главное окно чата DeepSeek Agent.
Стиль: ui/theme.py  |  Промт: workspace/SOUL.md  |  История: workspace/chat_history.json
"""
import time
import datetime
import re
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame, QScrollArea, QMessageBox,
    QCheckBox, QFileDialog,
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QKeyEvent, QPixmap, QDesktopServices

from ui import theme
from ui.settings_dialog import SettingsDialog
from core.bridge import AgentBridge
from core.worker import ChatWorker
from core.memory_loader import load_system_prompt
from data import config
from data import chat_history


# ── Вспомогательные функции ──────────────────────────────────────────────────

def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Plain)
    line.setFixedHeight(1)
    return line


def _icon_font() -> QFont:
    return QFont(theme.ICON_FONT_FAMILY, theme.ICON_FONT_SIZE)


def _now() -> str:
    return datetime.datetime.now().strftime("%H:%M")


_PHOTO_RE = re.compile(r'\[\[ФОТО:\s*([^\]]+)\]\]')
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_TEXT_EXTS = {
    ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv", ".log",
    ".ini", ".cfg", ".toml", ".js", ".ts", ".html", ".css", ".xml",
}
_MAX_FILE_PREVIEW_CHARS = 12_000


def _fmt_elapsed(seconds: float) -> str:
    return f"{seconds:.2f}с"


# ── Пузырь сообщения ─────────────────────────────────────────────────────────

class MessageBubble(QFrame):
    """Один блок сообщения: prefix → text → [footer с временем]."""

    def __init__(self, sender: str, text: str, is_user: bool,
                 ts: str = "", footer: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("bubble_user" if is_user else "bubble_agent")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(2)

        # Prefix: "[12:00]  Вы"
        time_str = ts or _now()
        prefix = QLabel(f"[{time_str}]  {'Вы' if is_user else sender}")
        prefix.setObjectName("bubble_prefix")
        layout.addWidget(prefix)

        # Текст сообщения
        body = QLabel(text)
        body.setObjectName("bubble_text")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextBrowserInteraction)
        body.setOpenExternalLinks(True)
        layout.addWidget(body)

        # Footer: время ответа — только у агента
        if footer:
            foot_lbl = QLabel(footer)
            foot_lbl.setObjectName("bubble_prefix")
            layout.addWidget(foot_lbl)


# ── Пузырь с картинкой ───────────────────────────────────────────────────────

class ImageBubble(QFrame):
    """Пузырь с превью картинки в чате."""

    def __init__(self, path: str, sender: str, ts: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("bubble_agent")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)

        time_str = ts or _now()
        prefix = QLabel(f"[{time_str}]  {sender}")
        prefix.setObjectName("bubble_prefix")
        layout.addWidget(prefix)

        img_label = QLabel()
        img_label.setObjectName("bubble_text")
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaledToWidth(min(640, pix.width()), Qt.SmoothTransformation)
        img_label.setPixmap(pix)
        img_label.setToolTip(path)
        img_label.setCursor(Qt.PointingHandCursor)
        img_label.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        layout.addWidget(img_label)


# ── Область прокрутки чата ───────────────────────────────────────────────────

class ChatArea(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chat_frame")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("chat_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.content = QWidget()
        self.content.setObjectName("chat_content")
        self._inner = QVBoxLayout(self.content)
        self._inner.setContentsMargins(8, 8, 8, 8)
        self._inner.setSpacing(6)
        self._inner.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)

    def add_message(self, sender: str, text: str, is_user: bool,
                    ts: str = "", footer: str = "") -> MessageBubble:
        bubble = MessageBubble(sender, text, is_user, ts=ts, footer=footer)
        self._inner.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)
        return bubble

    def add_image(self, path: str, sender: str = "DeepSeek", ts: str = ""):
        bubble = ImageBubble(path, sender, ts=ts)
        self._inner.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def clear_all(self):
        while self._inner.count():
            item = self._inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())


# ── Главное окно ─────────────────────────────────────────────────────────────

class MainWindow(QWidget):
    AGENT_NAME = "DeepSeek"

    def __init__(self):
        super().__init__()
        self.setObjectName("main_window")
        self.setWindowTitle(theme.WINDOW_TITLE)
        self.resize(theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)

        # Сигнальный мост и воркер
        self._bridge = AgentBridge()
        self._worker: ChatWorker | None = None
        self._tg_bot = None
        self._ping_active = False

        # Таймер ответа
        self._start_time: float = 0.0
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(100)
        self._tick_timer.timeout.connect(self._on_tick)

        # Таймер авто-пинка
        self._ping_remaining: int = 0       # секунд до пинка
        self._ping_enabled: bool = False
        self._ping_timer = QTimer(self)
        self._ping_timer.setInterval(1000)  # тик раз в секунду
        self._ping_timer.timeout.connect(self._on_ping_tick)

        self._build_ui()
        self.setStyleSheet(theme.build_qss())
        self._connect_signals()

        # Загружаем историю из workspace/
        self._load_history()
        self._update_header_count()

    # ── Построение UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(5)

        # Заголовок
        header_row = QWidget()
        hl = QHBoxLayout(header_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        hl.setAlignment(Qt.AlignCenter)

        header_icon = QLabel(theme.HEADER_ICON)
        header_icon.setFont(QFont(theme.ICON_FONT_FAMILY, theme.HEADER_ICON_SIZE))
        header_icon.setAlignment(Qt.AlignVCenter)
        header_icon.setStyleSheet(
            f"color: {theme.HEADER_COLOR}; background: transparent;"
            f"font-family: '{theme.ICON_FONT_FAMILY}';"
            f"font-size: {theme.HEADER_ICON_SIZE}px;"
        )

        header_txt = QLabel(
            f'<a href="{theme.BILLING_URL}" '
            f'style="color: {theme.HEADER_COLOR}; text-decoration: none; font-weight: 600;">'
            f'{theme.HEADER_TEXT}</a>'
        )
        header_txt.setObjectName("header_label")
        header_txt.setAlignment(Qt.AlignVCenter)
        header_txt.setOpenExternalLinks(True)
        header_txt.setCursor(Qt.PointingHandCursor)

        # Модель + счётчик: "deepseek-chat  12/100"
        self._model_label = QLabel()
        self._model_label.setObjectName("header_model_label")
        self._model_label.setAlignment(Qt.AlignVCenter)

        hl.addWidget(header_icon)
        hl.addWidget(header_txt)
        hl.addWidget(self._model_label)
        header_row.setMinimumHeight(theme.HEADER_HEIGHT)

        # Чат
        self._chat = ChatArea()

        # Кнопки
        mid_row = QWidget()
        mid_layout = QHBoxLayout(mid_row)
        mid_layout.setContentsMargins(0, 4, 0, 4)
        mid_layout.setSpacing(8)
        mid_layout.setAlignment(Qt.AlignLeft)

        self._btn_attach = QPushButton(theme.ICON_ATTACH)
        self._btn_attach.setObjectName("btn_attach")
        self._btn_attach.setFont(_icon_font())
        self._btn_attach.setFixedSize(theme.MID_BTN_SIZE, theme.MID_BTN_SIZE)
        self._btn_attach.setToolTip("Загрузить файл или картинку")

        self._btn_stop = QPushButton(theme.ICON_STOP)
        self._btn_stop.setObjectName("btn_stop")
        self._btn_stop.setFont(_icon_font())
        self._btn_stop.setFixedSize(theme.MID_BTN_SIZE, theme.MID_BTN_SIZE)
        self._btn_stop.setToolTip("Остановить генерацию")
        self._btn_stop.setEnabled(False)

        self._btn_settings = QPushButton(theme.ICON_SETTINGS)
        self._btn_settings.setObjectName("btn_settings")
        self._btn_settings.setFont(_icon_font())
        self._btn_settings.setFixedSize(theme.MID_BTN_SIZE, theme.MID_BTN_SIZE)
        self._btn_settings.setToolTip("Настройки")

        self._btn_images = QPushButton(theme.ICON_FOLDER)
        self._btn_images.setObjectName("btn_images")
        self._btn_images.setFont(_icon_font())
        self._btn_images.setFixedSize(theme.MID_BTN_SIZE, theme.MID_BTN_SIZE)
        self._btn_images.setToolTip("Открыть папку с картинками")

        mid_layout.addWidget(self._btn_attach)
        mid_layout.addWidget(self._btn_images)
        mid_layout.addWidget(self._btn_stop)
        mid_layout.addWidget(self._btn_settings)

        # Галка авто-пинка
        self._ping_checkbox = QCheckBox("Таймер")
        self._ping_checkbox.setObjectName("ping_checkbox")
        self._ping_checkbox.setToolTip("Авто-пинк: агент просыпается по таймеру")
        self._ping_checkbox.toggled.connect(self._on_ping_toggle)

        self._ping_countdown = QLabel("")
        self._ping_countdown.setObjectName("ping_countdown")
        self._ping_countdown.setToolTip("Обратный отсчёт до пробуждения")

        mid_layout.addWidget(self._ping_checkbox)
        mid_layout.addWidget(self._ping_countdown)

        # Поле ввода
        input_row = QWidget()
        ir_layout = QHBoxLayout(input_row)
        ir_layout.setContentsMargins(0, 4, 0, 4)
        ir_layout.setSpacing(6)

        input_bubble = QFrame()
        input_bubble.setObjectName("input_bubble")
        ib_layout = QHBoxLayout(input_bubble)
        ib_layout.setContentsMargins(5, 5, 5, 5)
        ib_layout.setSpacing(5)

        self._input = QTextEdit()
        self._input.setObjectName("input_field")
        self._input.setPlaceholderText(theme.INPUT_PLACEHOLDER)
        self._input.setMaximumHeight(theme.INPUT_HEIGHT)

        self._btn_send = QPushButton(theme.ICON_SEND)
        self._btn_send.setObjectName("btn_send")
        self._btn_send.setFont(_icon_font())
        self._btn_send.setFixedSize(theme.SEND_BTN_SIZE, theme.SEND_BTN_SIZE)
        self._btn_send.setToolTip("Отправить (Ctrl+Enter)")

        ib_layout.addWidget(self._input)
        ib_layout.addWidget(self._btn_send, 0, Qt.AlignVCenter)

        self._btn_mic = QPushButton(theme.ICON_MIC)
        self._btn_mic.setObjectName("btn_mic")
        self._btn_mic.setFont(_icon_font())
        self._btn_mic.setFixedSize(theme.MIC_BTN_SIZE, theme.MIC_BTN_SIZE)
        self._btn_mic.setToolTip("Голосовой ввод (скоро)")

        ir_layout.addWidget(input_bubble, 1)
        ir_layout.addWidget(self._btn_mic, 0, Qt.AlignVCenter)

        # Статусбар
        self._status = QLabel(theme.STATUS_READY)
        self._status.setObjectName("status_label")
        self._status.setAlignment(Qt.AlignCenter)

        # Сборка
        root.addWidget(header_row)
        root.addWidget(_hline())
        root.addWidget(self._chat, 1)
        root.addWidget(_hline())
        root.addWidget(mid_row)
        root.addWidget(_hline())
        root.addWidget(input_row)
        root.addWidget(_hline())
        root.addWidget(self._status)

    # ── Сигналы ──────────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._btn_send.clicked.connect(self._on_send)
        self._btn_attach.clicked.connect(self._on_attach_file)
        self._btn_images.clicked.connect(self._open_images_folder)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_settings.clicked.connect(self._on_settings)
        self._bridge.response_ready.connect(self._on_response)
        self._bridge.status_changed.connect(self._set_status)
        self._bridge.error_occurred.connect(self._on_error)
        # Промежуточные события (tool-calling)
        self._bridge.interim.connect(self._on_interim)
        # Токены
        self._bridge.token_info.connect(self._on_token_info)
        self._token_footer = ""
        # Телеграм
        self._bridge.tg_interim.connect(self._on_tg_interim)
        self._bridge.tg_user_message.connect(self._on_tg_user)
        self._bridge.tg_agent_message.connect(self._on_tg_agent)
        self._bridge.history_cleared.connect(lambda: self._on_clear(confirm=False))
        # Картинка
        self._bridge.image_ready.connect(self._on_image_ready)

    # ── История ──────────────────────────────────────────────────────────────

    def _load_history(self):
        """Загружает прошлые сообщения из workspace/chat_history.json в UI."""
        messages = chat_history.load()
        if not messages:
            self._chat.add_message(
                self.AGENT_NAME,
                "Привет! Я DeepSeek Agent. Чем могу помочь?",
                is_user=False
            )
        else:
            for msg in messages:
                is_user = msg["role"] == "user"
                sender = "Вы" if is_user else self.AGENT_NAME
                elapsed = msg.get("elapsed")
                footer = f"⏱ {elapsed}с" if elapsed else ""
                text = msg["text"]
                ts = msg.get("ts", "")
                # Показываем картинки из истории — по image_path или маркеру [[ФОТО:...]]
                img_path = msg.get("image_path", "")
                if img_path:
                    self._chat.add_image(img_path, sender=sender, ts=ts)
                for m in _PHOTO_RE.finditer(text):
                    self._chat.add_image(m.group(1).strip(), sender=sender, ts=ts)
                # Убираем маркер из текста
                clean_text = _PHOTO_RE.sub("", text).strip()
                if clean_text:
                    self._chat.add_message(
                        sender, clean_text,
                        is_user=is_user,
                        ts=ts,
                        footer=footer
                    )
        self._set_status(theme.STATUS_READY)

    def _build_openai_messages(self) -> list[dict]:
        """Собирает messages для API: системный промт + история."""
        system_prompt = load_system_prompt()
        return chat_history.to_openai_messages(system_prompt)

    def _update_header_count(self):
        """Обновляет счётчик в шапке: 'deepseek-chat  12/100'"""
        count = chat_history.count()
        limit = config.get_history_limit()
        model = config.get_model()
        self._model_label.setText(f"{model}  {count}/{limit}")

    def update_model(self):
        """Вызывать после смены модели в настройках."""
        self._update_header_count()

    def set_tg_bot(self, bot):
        self._tg_bot = bot

    # ── Таймер ───────────────────────────────────────────────────────────────

    def _start_timer(self):
        self._start_time = time.monotonic()
        self._tick_timer.start()

    def _stop_timer(self) -> float:
        self._tick_timer.stop()
        return time.monotonic() - self._start_time

    def _on_tick(self):
        elapsed = time.monotonic() - self._start_time
        self._status.setText(f"Думаю...  {_fmt_elapsed(elapsed)}")

    # ── Пинг-таймер ────────────────────────────────────────────────────────

    def _on_ping_toggle(self, checked: bool):
        """Включение/выключение авто-пинка через галку."""
        if checked:
            interval_min = config.get_ping_interval()
            self._ping_remaining = interval_min * 60
            self._ping_enabled = True
            self._ping_timer.start()
            self._update_ping_label()
            # Первый пинг — сразу при включении, не ждём интервал
            self._fire_ping()
        else:
            self._ping_enabled = False
            self._ping_timer.stop()
            self._ping_countdown.setText("")
            self._set_status(theme.STATUS_READY)

    def _on_ping_tick(self):
        """Тик раз в секунду: обновить отсчёт, при 0 — пнуть агента."""
        if not self._ping_enabled:
            return
        self._ping_remaining -= 1
        if self._ping_remaining <= 0:
            self._fire_ping()
        else:
            # Не затираем статус «Думаю...» пока агент работает
            busy = self._worker and self._worker.isRunning()
            self._update_ping_label(update_status=not busy)

    def _update_ping_label(self, update_status: bool = True):
        """Показать обратный отсчёт в формате MM:SS."""
        m = self._ping_remaining // 60
        s = self._ping_remaining % 60
        text = f"{m:02d}:{s:02d}"
        self._ping_countdown.setText(text)
        if update_status:
            self._status.setText(text)

    def _fire_ping(self):
        """Таймер сработал — отправляем агенту авто-пинок."""
        # Сбросить таймер для следующего цикла
        interval_min = config.get_ping_interval()
        self._ping_remaining = interval_min * 60

        topic = config.get_ping_topic()
        if topic:
            prompt = f"Пинг по таймеру. Тема: {topic}"
        else:
            prompt = (
                "Пинг по таймеру. Свободный полёт — ты сама решаешь чем заняться: "
                "изучить новости, нарисовать картинку, покопаться в своих файлах, "
                "написать мысль в дневник, или просто ответить что на душе."
            )

        # Не запускаем если агент уже думает
        if self._worker and self._worker.isRunning():
            return

        self._chat.add_message("⏱ Пинк", prompt, is_user=True)
        chat_history.append("user", prompt)
        self._update_header_count()

        self._btn_send.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._start_timer()
        self._ping_active = True

        messages = self._build_openai_messages()
        self._worker = ChatWorker(messages, self._bridge)
        self._worker.start()

    # ── Обработчики ──────────────────────────────────────────────────────────

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        if self._worker and self._worker.isRunning():
            return

        self._input.clear()
        self._chat.add_message("Вы", text, is_user=True)
        chat_history.append("user", text)
        self._update_header_count()

        self._btn_send.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._start_timer()

        messages = self._build_openai_messages()
        self._worker = ChatWorker(messages, self._bridge)
        self._worker.start()

    def _append_to_input(self, text: str):
        current = self._input.toPlainText().strip()
        self._input.setPlainText(f"{current}\n\n{text}" if current else text)
        self._input.setFocus()
        cursor = self._input.textCursor()
        cursor.movePosition(cursor.End)
        self._input.setTextCursor(cursor)

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать файл",
            str(config.ROOT_DIR / "workspace"),
            "Все файлы (*.*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix in _IMAGE_EXTS:
            self._attach_image(path)
            return

        if suffix in _TEXT_EXTS:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                self._append_to_input(f"Файл: {path}\nНе удалось прочитать текст: {e}")
                return
            if len(text) > _MAX_FILE_PREVIEW_CHARS:
                text = text[:_MAX_FILE_PREVIEW_CHARS] + "\n...[файл обрезан]"
            self._append_to_input(f"Файл: {path}\n\n```text\n{text}\n```")
            return

        self._append_to_input(
            f"Файл: {path}\n"
            "Это не текстовый файл. Если нужно, попроси меня обработать его подходящим инструментом."
        )

    def _attach_image(self, path: Path):
        self._chat.add_image(str(path), sender="Вы")
        desc = ""
        try:
            from tools.image_tools import analyze_image
            result = analyze_image(str(path), "Опиши подробно что изображено на этой картинке.")
            if result.get("status") == "ok":
                desc = result.get("result", "")
            else:
                desc = f"[Gemini Vision не смог описать картинку: {result.get('error', 'ошибка')}]"
        except Exception as e:
            desc = f"[Ошибка анализа картинки: {e}]"

        text = f"Пользователь загрузил картинку.\nПуть к файлу: {path}\n\n[Gemini описывает картинку:]\n{desc}"
        chat_history.append("user", text, image_path=str(path))
        self._update_header_count()
        self._append_to_input(
            f"Картинка загружена: {path}\n"
            "Описание уже добавлено в историю. Напиши, что с ней сделать."
        )

    def _open_images_folder(self):
        images_dir = config.ROOT_DIR / "workspace" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(images_dir)))

    def _on_response(self, text: str):
        elapsed = self._stop_timer()
        timing = _fmt_elapsed(elapsed)

        chat_history.append("assistant", text, elapsed=elapsed)
        self._update_header_count()

        footer = f"⏱ {timing}{self._token_footer}"
        self._token_footer = ""  # сбросить до следующего ответа

        self._chat.add_message(
            self.AGENT_NAME, text, is_user=False,
            footer=footer
        )

        if self._ping_active and self._tg_bot:
            self._tg_bot.post_message(f"{text}\n\n{footer}")
        self._ping_active = False

        self._btn_send.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._set_status(f"{theme.STATUS_READY}  ·  последний ответ: {timing}")

    def _on_clear(self, confirm=True):
        # Если вызов идёт от клика по кнопке (confirm=True), спрашиваем
        if confirm:
            msg = QMessageBox(self)
            msg.setWindowTitle("Очистка истории")
            msg.setText("Ты уверен, что хочешь очистить всю историю чата? Это действие необратимо.")
            msg.setIcon(QMessageBox.Question)
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)
            msg.setStyleSheet(theme.build_qss())
            if msg.exec() == QMessageBox.No:
                return

        chat_history.clear()
        self._chat.clear_all()
        self._chat.add_message(
            self.AGENT_NAME, "История очищена. Начнём заново!", is_user=False
        )
        self._update_header_count()
        self._set_status(theme.STATUS_READY)

    def _on_stop(self):
        self._stop_timer()
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            if not self._worker.wait(2000):
                self._worker.terminate()
            self._worker = None
        self._btn_send.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._set_status("Остановлено")

    def _on_interim(self, text: str):
        """[tool] уведомления — показываем в статусной строке что делается."""
        if text.startswith("[tool]"):
            label = text[6:]
            self._set_status(label)
            self._chat._scroll_to_bottom()
            if self._tg_bot:
                self._tg_bot.post_message(label)

    def _on_token_info(self, prompt: int, completion: int):
        """Запомнить токены — пригодятся когда придёт ответ."""
        def _fmt(n: int) -> str:
            if n >= 1000:
                return f"{n/1000:.1f}K"
            return str(n)
        if prompt or completion:
            self._token_footer = f" · 📥{_fmt(prompt)}📤{_fmt(completion)}"
        else:
            self._token_footer = ""

    def _on_tg_interim(self, text: str):
        """Промежуточные события из Telegram-потока — только статусбар, без повтора в TG."""
        if text.startswith("[tool]"):
            self._set_status(text[6:])

    def _on_tg_user(self, ts: str, text: str):
        """Сообщение из Telegram — показать в чате UI."""
        self._chat.add_message("Телеграм", text, is_user=True, ts=ts)
        self._update_header_count()

    def _on_tg_agent(self, ts: str, text: str):
        """Ответ агента в Telegram — показать в чате UI."""
        self._chat.add_message(self.AGENT_NAME, text, is_user=False, ts=ts)
        self._update_header_count()

    def _on_image_ready(self, path: str):
        """Картинка сгенерирована — добавить в чат, сохранить в историю и отправить в Telegram."""
        # Защита от дубликатов: один и тот же путь за раз не шлём дважды
        if hasattr(self, '_last_image_path') and self._last_image_path == path:
            return
        self._last_image_path = path
        self._chat.add_image(path, sender=self.AGENT_NAME)
        # Сохраняем в историю, чтобы при перезапуске картинка подгрузилась
        chat_history.append("assistant", f"📷 {path}", image_path=path)
        self._update_header_count()
        if self._tg_bot:
            self._tg_bot.post_photo(path)

    def _on_settings(self):
        dlg = SettingsDialog(self)
        dlg.clear_history_requested.connect(lambda: self._on_clear(confirm=True))
        if dlg.exec():
            self._update_header_count()

    def _on_error(self, msg: str):
        self._stop_timer()
        self._ping_active = False
        self._chat.add_message("Система", f"Ошибка: {msg}", is_user=False)
        self._btn_send.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._set_status(theme.STATUS_ERROR)

    def _set_status(self, text: str):
        self._status.setText(text)

    # ── Ctrl+Enter = отправить ───────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if (event.key() == Qt.Key_Return
                and event.modifiers() & Qt.ControlModifier):
            self._on_send()
        else:
            super().keyPressEvent(event)
