"""
ui/settings_dialog.py — диалог настроек DeepSeek Agent.
Вкладки: Модель, Ключи.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QFrame, QFormLayout, QDoubleSpinBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ui import theme
from data import config, keystore


# ── Вспомогательные ─────────────────────────────────────────────────────────

def _section(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet(
        f"font-weight: 600; font-size: 12px;"
        f"color: {theme.HEADER_COLOR}; margin-top: 8px;"
    )
    return lbl


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Plain)
    return line


# ── Вкладка: Модель ──────────────────────────────────────────────────────────

class ModelTab(QWidget):
    # (id, описание, цена вход, цена выход — за 1M токенов)
    # ВАЖНО: список моделей и цены не обновлять "по памяти" LLM.
    # Проверять официальные DeepSeek docs: https://api-docs.deepseek.com/quick_start/pricing/
    MODELS = [
        ("deepseek-v4-flash",  "V4 Flash — быстрая, 1M контекст",  "$0.14", "$0.28"),
        ("deepseek-v4-pro",    "V4 Pro — самая мощная",            "$0.435", "$0.87"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(_section("Модель"))
        layout.addWidget(_hline())

        # Выбор модели
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._model_combo = QComboBox()
        for model_id, label, price_in, price_out in self.MODELS:
            display = f"{model_id}  —  {label}  │  ↓{price_in} / ↑{price_out}"
            self._model_combo.addItem(display, model_id)

        current = config.get_model()
        for i, (mid, *_) in enumerate(self.MODELS):
            if mid == current:
                self._model_combo.setCurrentIndex(i)

        form.addRow("Модель:", self._model_combo)

        layout.addWidget(_section("Параметры генерации"))
        layout.addWidget(_hline())

        # Температура
        self._temp_spin = QDoubleSpinBox()
        self._temp_spin.setRange(0.0, 2.0)
        self._temp_spin.setSingleStep(0.05)
        self._temp_spin.setDecimals(2)
        self._temp_spin.setValue(config.get_temperature())
        self._temp_spin.setToolTip("0 = детерминированный,  1 = креативный,  2 = хаос")
        form.addRow("Температура:", self._temp_spin)

        # Max tokens
        self._tokens_spin = QSpinBox()
        self._tokens_spin.setRange(256, 32768)
        self._tokens_spin.setSingleStep(256)
        self._tokens_spin.setValue(config.get_max_tokens())
        self._tokens_spin.setToolTip(
            "Max Tokens = максимальная длина ОТВЕТА модели (8192 — норма).\n"
            "Читать большие файлы — это входной контекст, он ограничен окном 64K токенов."
        )
        form.addRow("Max tokens:", self._tokens_spin)

        layout.addLayout(form)
        layout.addStretch()

    def apply(self):
        """Сохранить изменения в конфиг."""
        cfg = config._load()
        cfg["model"]       = self._model_combo.currentData()
        cfg["temperature"] = round(self._temp_spin.value(), 2)
        cfg["max_tokens"]  = self._tokens_spin.value()
        config._save(cfg)


# ── Вкладка: Чат ────────────────────────────────────────────

class ChatTab(QWidget):
    INTERVALS = [
        (1, "1 минута"),
        (5, "5 минут"),
        (15, "15 минут"),
        (30, "30 минут"),
        (60, "1 час"),
        (120, "2 часа"),
        (240, "4 часа"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(_section("Память диалога"))
        layout.addWidget(_hline())

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(10, 1000)
        self._limit_spin.setSingleStep(10)
        self._limit_spin.setValue(config.get_history_limit())
        self._limit_spin.setToolTip(
            "Максимальное количество сообщений, хранящихся в истории и передающихся модели"
        )
        form.addRow("Сообщений в чате:", self._limit_spin)

        layout.addWidget(_section("Инструменты"))
        layout.addWidget(_hline())

        form2 = QFormLayout()
        form2.setSpacing(10)
        form2.setLabelAlignment(Qt.AlignRight)

        self._rounds_spin = QSpinBox()
        self._rounds_spin.setRange(3, 50)
        self._rounds_spin.setSingleStep(5)
        self._rounds_spin.setValue(config.get_tool_rounds())
        self._rounds_spin.setToolTip(
            "Максимальное число раундов API за один запрос.\n"
            "За один раунд модель может вызвать несколько инструментов сразу (batch).\n"
            "10 — норма, 20-30 — для сложных многошаговых задач."
        )
        form2.addRow("Раундов инструментов:", self._rounds_spin)

        self._image_size_combo = QComboBox()
        for value, label in [
            ("2K", "2K — обычный режим, дешевле"),
            ("4K", "4K — тест/финальные кадры, дороже"),
        ]:
            self._image_size_combo.addItem(label, value)
        current_image_size = config.get_image_size()
        for i in range(self._image_size_combo.count()):
            if self._image_size_combo.itemData(i) == current_image_size:
                self._image_size_combo.setCurrentIndex(i)
                break
        self._image_size_combo.setToolTip(
            "Разрешение новых картинок Gemini. 4K дороже и медленнее, но может быть полезен для финальных кадров."
        )
        form2.addRow("Картинки:", self._image_size_combo)
        layout.addLayout(form2)

        layout.addWidget(_section("Авто-пинк (таймер пробуждения)"))
        layout.addWidget(_hline())

        form3 = QFormLayout()
        form3.setSpacing(10)
        form3.setLabelAlignment(Qt.AlignRight)

        self._ping_interval_combo = QComboBox()
        for mins, label in self.INTERVALS:
            self._ping_interval_combo.addItem(label, mins)

        current_interval = config.get_ping_interval()
        for i, (mins, _) in enumerate(self.INTERVALS):
            if mins == current_interval:
                self._ping_interval_combo.setCurrentIndex(i)
                break

        self._ping_interval_combo.setToolTip(
            "Как часто агент будет просыпаться и действовать самостоятельно"
        )
        form3.addRow("Интервал:", self._ping_interval_combo)

        self._ping_topic_edit = QLineEdit()
        self._ping_topic_edit.setText(config.get_ping_topic())
        self._ping_topic_edit.setPlaceholderText("пусто = свободный полёт")
        self._ping_topic_edit.setToolTip(
            "Оставь пустым — агент сам решит чем заняться.\n"
            "Заполни — будет действовать по теме (например «проверь новости»)."
        )
        form3.addRow("Тема:", self._ping_topic_edit)

        layout.addLayout(form3)

        layout.addLayout(form)
        layout.addStretch()

    def apply(self):
        config.set_history_limit(self._limit_spin.value())
        config.set_tool_rounds(self._rounds_spin.value())
        config.set_image_size(self._image_size_combo.currentData())
        config.set_ping_interval(self._ping_interval_combo.currentData())
        config.set_ping_topic(self._ping_topic_edit.text())


# ── Вкладка: Ключи ──────────────────────────────────────────────────────────

def _secret_row(edit: "QLineEdit") -> "QHBoxLayout":
    chk = QCheckBox("показать")
    chk.toggled.connect(
        lambda v, e=edit: e.setEchoMode(QLineEdit.Normal if v else QLineEdit.Password)
    )
    row = QHBoxLayout()
    row.addWidget(edit, 1)
    row.addWidget(chk)
    return row


class KeysTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._ds_key = QLineEdit()
        self._ds_key.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxx")
        self._ds_key.setEchoMode(QLineEdit.Password)
        self._ds_key.setText(keystore.get("DEEPSEEK_API_KEY"))
        form.addRow("DeepSeek API Key:", _secret_row(self._ds_key))

        self._gemini_key = QLineEdit()
        self._gemini_key.setPlaceholderText("AIzaSy...")
        self._gemini_key.setEchoMode(QLineEdit.Password)
        self._gemini_key.setText(keystore.get("GEMINI_API_KEY"))
        form.addRow("Gemini API Key:", _secret_row(self._gemini_key))

        self._eleven_key = QLineEdit()
        self._eleven_key.setPlaceholderText("sk_xxxxxxxxxxxxxxxxxxxxxxxx")
        self._eleven_key.setEchoMode(QLineEdit.Password)
        self._eleven_key.setText(keystore.get("ELEVENLABS_API_KEY"))
        form.addRow("ElevenLabs API Key:", _secret_row(self._eleven_key))

        self._tg_token = QLineEdit()
        self._tg_token.setPlaceholderText("1234567890:AAxxxxxx...")
        self._tg_token.setEchoMode(QLineEdit.Password)
        self._tg_token.setText(config.get_tg_token())
        form.addRow("Telegram Bot Token:", _secret_row(self._tg_token))

        stored_cid = config.get_tg_chat_id()
        self._tg_chatid = QLineEdit()
        self._tg_chatid.setText(str(stored_cid) if stored_cid else "")
        self._tg_chatid.setPlaceholderText("Отправь /start боту — он ответит твоим chat_id")
        form.addRow("Chat ID:", self._tg_chatid)

        layout.addLayout(form)

        hint = QLabel("Не знаешь chat_id? Введи токен, сохрани, перезапусти и напиши /start боту.")
        hint.setStyleSheet(f"color: {theme.BUBBLE_PREFIX_COLOR}; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()

    def apply(self):
        ds = self._ds_key.text().strip()
        if ds:
            keystore.set_key("DEEPSEEK_API_KEY", ds)

        gemini = self._gemini_key.text().strip()
        if gemini:
            keystore.set_key("GEMINI_API_KEY", gemini)

        eleven = self._eleven_key.text().strip()
        if eleven:
            keystore.set_key("ELEVENLABS_API_KEY", eleven)

        config.set_tg_token(self._tg_token.text().strip())
        cid = self._tg_chatid.text().strip()
        if cid.lstrip("-").isdigit():
            config.set_tg_chat_id(int(cid))


# ── Вкладка: Обслуживание ───────────────────────────────────────────────────

class MaintenanceTab(QWidget):
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(_section("История чата"))
        layout.addWidget(_hline())

        hint = QLabel(
            "Очистка убирает локальную историю диалога. Кнопка спрятана здесь, "
            "чтобы не нажать её случайно рядом с настройками."
        )
        hint.setStyleSheet(f"color: {theme.BUBBLE_PREFIX_COLOR}; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._btn_clear = QPushButton("Очистить историю чата")
        self._btn_clear.setToolTip("Спросит подтверждение перед очисткой")
        self._btn_clear.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self._btn_clear, 0, Qt.AlignLeft)
        layout.addStretch()


# ── Главный диалог ──────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    clear_history_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки — DeepSeek Agent")
        self.setMinimumWidth(520)
        self.setMinimumHeight(440)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Вкладки
        self._tabs = QTabWidget()
        self._tab_model = ModelTab()
        self._tab_chat  = ChatTab()
        self._tab_keys  = KeysTab()
        self._tab_maintenance = MaintenanceTab()
        self._tab_maintenance.clear_requested.connect(self.clear_history_requested.emit)
        self._tabs.addTab(self._tab_model, "Модель")
        self._tabs.addTab(self._tab_chat,  "Чат")
        self._tabs.addTab(self._tab_keys,  "Ключи")
        self._tabs.addTab(self._tab_maintenance, "Обслуживание")
        layout.addWidget(self._tabs, 1)

        # Ссылка на DeepSeek платформу и статус
        balance_link = QLabel(
            f'<span style="font-family: {theme.MAIN_FONT_FAMILY}; font-size: 18px; color: {theme.STATUS_COLOR};">'
            f'<font face="{theme.ICON_FONT_FAMILY}">\uE774</font> '
            f'<a href="https://platform.deepseek.com/usage" style="color: {theme.HEADER_COLOR}; text-decoration: none;">'
            f'platform.deepseek.com/usage</a> — баланс и статистика<br>'
            f'<font face="{theme.ICON_FONT_FAMILY}">\uE701</font> '  # \uF13C — более надёжная иконка сервера/статуса в MDL2
            f'<a href="https://status.deepseek.com/" style="color: {theme.HEADER_COLOR}; text-decoration: none;">'
            f'status.deepseek.com</a> — статус сервера'
            f'</span>'
        )
        balance_link.setOpenExternalLinks(True)
        balance_link.setAlignment(Qt.AlignCenter)
        layout.addWidget(balance_link)

        # Кнопки OK / Отмена
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._btn_cancel = QPushButton("Отмена")
        self._btn_cancel.setObjectName("btn_cancel")
        self._btn_cancel.clicked.connect(self.reject)

        self._btn_ok = QPushButton("Сохранить")
        self._btn_ok.setObjectName("btn_ok")
        self._btn_ok.setDefault(True)
        self._btn_ok.clicked.connect(self._on_save)

        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_ok)
        layout.addLayout(btn_row)

        self.setStyleSheet(theme.build_qss() + f"""
QDialog {{
    background-color: {theme.BG_COLOR};
}}
QTabWidget::pane {{
    border: 1px solid {theme.BORDER_COLOR};
    border-radius: {theme.BORDER_RADIUS}px;
    background-color: {theme.CHAT_BG};
}}
QTabBar::tab {{
    background-color: {theme.BUTTON_BG};
    color: {theme.TEXT_COLOR};
    border: 1px solid {theme.BORDER_COLOR};
    border-bottom: none;
    padding: 6px 18px;
    border-top-left-radius: {theme.BORDER_RADIUS}px;
    border-top-right-radius: {theme.BORDER_RADIUS}px;
}}
QTabBar::tab:selected {{
    background-color: {theme.CHAT_BG};
    font-weight: 600;
}}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background-color: {theme.INPUT_BG};
    color: {theme.TEXT_COLOR};
    border: 1px solid {theme.BORDER_COLOR};
    border-radius: {theme.BORDER_RADIUS}px;
    padding: 4px 8px;
    min-width: 200px;
}}
QComboBox::drop-down {{
    border: none;
}}
""")

    def _on_save(self):
        self._tab_model.apply()
        self._tab_chat.apply()
        self._tab_keys.apply()
        self.accept()

    def get_selected_model(self) -> str:
        return self._tab_model._model_combo.currentData()
