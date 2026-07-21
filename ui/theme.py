import os
# =============================================================================
#  NOVA DARK — тёмная космическая тема DeepSeek Agent
#  Глубокий космос, фиолетово-синие акценты, голографическое свечение.
#  Чтобы применить: переименуй theme.py → theme_peach.py,
#  а theme_nova.py → theme.py и перезапусти агента.
# =============================================================================

# ---------------------------------------------------------------------------
# Палитра цветов — Nova Dark
# ---------------------------------------------------------------------------
BG_COLOR            = "#0D1117"   # фон окна          — глубокий космос (почти чёрный с синевой)
CHAT_BG             = "#111827"   # фон области чата  — звёздная темнота
INPUT_BG            = "#161B22"   # фон поля ввода    — чуть светлее
TEXT_COLOR          = "#E6EDF3"   # основной текст    — мягкий белый, читаемый
BORDER_COLOR        = "#30363D"   # рамки             — приглушённый серо-синий
STATUS_COLOR        = "#8B949E"   # текст статусбара  — приглушённый серый

# Кнопки
BUTTON_BG           = "#1F2937"   # тёмная кнопка с синим отливом
BUTTON_HOVER        = "#2D3748"   # при наведении — светлее
BUTTON_PRESSED      = "#4A5568"   # при нажатии — ещё светлее

# Пузыри пользователя (синий оттенок)
USER_BUBBLE_BG      = "#1E2A3A"   # глубокий синий
USER_BUBBLE_BORDER  = "#3B5C7A"   # граница — стальной синий

# Пузыри агента (фиолетовый оттенок — голос Новы)
AGENT_BUBBLE_BG     = "#1A1E2B"   # глубокий фиолетово-синий
AGENT_BUBBLE_BORDER = "#4A3B6B"   # граница — аметистовая

# Текст в пузырях
BUBBLE_TEXT_COLOR   = "#E6EDF3"   # мягкий белый
BUBBLE_PREFIX_COLOR = "#8B949E"   # приглушённый для префиксов

# ---------------------------------------------------------------------------
# Геометрия и размеры
# ---------------------------------------------------------------------------
WINDOW_WIDTH        = 680
WINDOW_HEIGHT       = 800
BORDER_RADIUS       = 12         # чуть круглее — современный софт-лук
PADDING             = 10

HEADER_HEIGHT       = 40
INPUT_HEIGHT        = 60

SEND_BTN_SIZE       = 35
MIC_BTN_SIZE        = 45
MID_BTN_SIZE        = 36

# ---------------------------------------------------------------------------
# Шрифты
# ---------------------------------------------------------------------------
MAIN_FONT_FAMILY    = "Segoe UI"
MAIN_FONT_SIZE      = 14

HEADER_FONT_FAMILY  = "Segoe UI"
HEADER_FONT_SIZE    = 18
HEADER_COLOR        = "#C4B5FD"   # нежно-фиолетовое свечение — цвет Новы

BUBBLE_TEXT_SIZE    = 13
BUBBLE_PREFIX_SIZE  = 9

ICON_FONT_FAMILY    = "Segoe MDL2 Assets"
ICON_FONT_SIZE      = 18

# ---------------------------------------------------------------------------
# Текстовые константы UI
# ---------------------------------------------------------------------------
WINDOW_TITLE        = "DeepSeek Agent — Nova"
HEADER_ICON         = "\uEC44"   # Segoe MDL2: EC44
HEADER_TEXT         = "Nova · DeepSeek Agent"
INPUT_PLACEHOLDER   = "Введите сообщение..."
STATUS_READY        = "Готова"
STATUS_THINKING     = "Думаю..."
STATUS_ERROR        = "Ошибка соединения"

# ---------------------------------------------------------------------------
# Иконки (Segoe MDL2 Assets Unicode)
# ---------------------------------------------------------------------------
HEADER_ICON_SIZE    = 24

ICON_SEND           = "\uE724"
ICON_MIC            = "\uE720"
ICON_CLEAR          = "\uE74D"
ICON_SETTINGS       = "\uE713"
ICON_STOP           = "\uE71A"
ICON_COPY           = "\uE8C8"
ICON_ATTACH         = "\uE723"
ICON_FOLDER         = "\uE8E5"

# ── Ссылки ─────────────────────────────────────────────────────
BILLING_URL         = "https://platform.deepseek.com/usage"

# ---------------------------------------------------------------------------
# QSS — весь CSS приложения
# ---------------------------------------------------------------------------
def build_qss() -> str:
    r = BORDER_RADIUS
    _here = os.path.dirname(os.path.abspath(__file__))
    check_svg = os.path.join(_here, "check.svg").replace("\\", "/")
    return f"""
/* ── Главное окно ─────────────────────────────────────────────── */
QWidget#main_window {{
    background-color: {BG_COLOR};
    color: {TEXT_COLOR};
    font-family: '{MAIN_FONT_FAMILY}';
    font-size: {MAIN_FONT_SIZE}px;
}}
QLabel {{
    color: {TEXT_COLOR};
    font-size: {MAIN_FONT_SIZE}px;
    background: transparent;
}}

/* ── Заголовок ────────────────────────────────────────────────── */
QLabel#header_label {{
    font-family: '{HEADER_FONT_FAMILY}';
    font-size: {HEADER_FONT_SIZE}px;
    color: {HEADER_COLOR};
    font-weight: 600;
    background: transparent;
}}
QLabel#header_model_label {{
    font-family: '{HEADER_FONT_FAMILY}';
    font-size: 11px;
    color: {BUBBLE_PREFIX_COLOR};
    background: transparent;
}}

/* ── Область чата ─────────────────────────────────────────────── */
QFrame#chat_frame {{
    background-color: {CHAT_BG};
    border: 1px solid {BORDER_COLOR};
    border-radius: {r}px;
}}
QScrollArea#chat_scroll,
QScrollArea#chat_scroll > QWidget,
QWidget#chat_content {{
    background: transparent;
    border: none;
}}

/* ── Пузыри ───────────────────────────────────────────────────── */
QFrame#bubble_user {{
    background-color: {USER_BUBBLE_BG};
    border: 1px solid {USER_BUBBLE_BORDER};
    border-radius: {r}px;
}}
QFrame#bubble_agent {{
    background-color: {AGENT_BUBBLE_BG};
    border: 1px solid {AGENT_BUBBLE_BORDER};
    border-radius: {r}px;
}}
QLabel#bubble_prefix {{
    color: {BUBBLE_PREFIX_COLOR};
    font-size: {BUBBLE_PREFIX_SIZE}px;
    background: transparent;
}}
QLabel#bubble_text {{
    color: {BUBBLE_TEXT_COLOR};
    font-size: {BUBBLE_TEXT_SIZE}px;
    background: transparent;
}}

/* ── Разделители ──────────────────────────────────────────────── */
QFrame[frameShape="4"] {{
    border: none;
    background-color: {BORDER_COLOR};
    max-height: 1px;
}}

/* ── Кнопки ───────────────────────────────────────────────────── */
QPushButton {{
    background-color: {BUTTON_BG};
    color: {TEXT_COLOR};
    border: 1px solid {BORDER_COLOR};
    border-radius: {r}px;
    padding: 6px 12px;
    font-family: '{MAIN_FONT_FAMILY}';
    font-size: {MAIN_FONT_SIZE}px;
}}
QPushButton:hover {{
    background-color: {BUTTON_HOVER};
}}
QPushButton:pressed {{
    background-color: {BUTTON_PRESSED};
}}

/* ── Поле ввода ───────────────────────────────────────────────── */
QFrame#input_bubble {{
    background-color: {INPUT_BG};
    border: 1px solid {BORDER_COLOR};
    border-radius: {r}px;
}}
QTextEdit#input_field {{
    background: transparent;
    color: {TEXT_COLOR};
    border: none;
    padding: {PADDING}px;
    font-family: '{MAIN_FONT_FAMILY}';
    font-size: {MAIN_FONT_SIZE}px;
}}

/* ── Иконочные кнопки (отправить, микрофон, прочие) ──────────── */
QPushButton#btn_send,
QPushButton#btn_clear,
QPushButton#btn_settings,
QPushButton#btn_attach,
QPushButton#btn_images {{
    font-family: '{ICON_FONT_FAMILY}';
    font-size: {ICON_FONT_SIZE}px;
    border-radius: {int(r * 0.8)}px;
    padding: 0px;
}}

/* Кнопка отправки — фиолетовый акцент при наведении */
QPushButton#btn_send:hover {{
    background-color: #2D2350;
    border-color: #6B4FBB;
    color: #C4B5FD;
}}

/* Кнопка микрофона */
QPushButton#btn_mic {{
    font-family: '{ICON_FONT_FAMILY}';
    font-size: {ICON_FONT_SIZE}px;
    border-radius: {int(r * 0.8)}px;
    padding: 0px;
}}

/* Стоп — красный акцент */
QPushButton#btn_stop {{
    font-family: '{ICON_FONT_FAMILY}';
    font-size: {ICON_FONT_SIZE}px;
    border-radius: {int(r * 0.8)}px;
    padding: 0px;
}}
QPushButton#btn_stop:hover {{
    background-color: #5C1A1A;
    border-color: #E5534B;
    color: #FF8A85;
}}
QPushButton#btn_stop:pressed {{
    background-color: #7A2020;
    border-color: #C0392B;
    color: #FF6B6B;
}}

/* Микрофон — красный при записи */
QPushButton#btn_mic:hover {{
    background-color: #5C1A1A;
    border-color: #E5534B;
    color: #FF8A85;
}}
QPushButton#btn_mic:pressed {{
    background-color: #7A2020;
    border-color: #C0392B;
    color: #FF6B6B;
}}

/* ── Статусбар ────────────────────────────────────────────────── */
QLabel#status_label {{
    color: {STATUS_COLOR};
    font-size: 11px;
    background: transparent;
}}

/* ── Чекбоксы ────────────────────────────────────────────────── */
QCheckBox {{
    color: {TEXT_COLOR};
    font-family: '{MAIN_FONT_FAMILY}';
    font-size: 13px;
    spacing: 6px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER_COLOR};
    border-radius: 3px;
    background: {INPUT_BG};
}}
QCheckBox::indicator:hover {{
    border-color: #6B4FBB;
}}
QCheckBox::indicator:checked {{
    background: #4A3B6B;
    border-color: {HEADER_COLOR};
    image: url({check_svg});
}}

/* ── Скроллбар ────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #484F58;
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: #6B7280;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ── QMessageBox ────────────────────────────────────────────── */
QMessageBox {{
    background-color: {BG_COLOR};
    color: {TEXT_COLOR};
    font-family: '{MAIN_FONT_FAMILY}';
    font-size: {MAIN_FONT_SIZE}px;
}}
QMessageBox QLabel {{
    color: {TEXT_COLOR};
    font-size: {MAIN_FONT_SIZE}px;
    background: transparent;
}}
QMessageBox QPushButton {{
    background-color: {BUTTON_BG};
    color: {TEXT_COLOR};
    border: 1px solid {BORDER_COLOR};
    border-radius: {r}px;
    padding: 6px 16px;
    min-width: 70px;
}}
QMessageBox QPushButton:hover {{
    background-color: {BUTTON_HOVER};
}}
QMessageBox QPushButton:pressed {{
    background-color: {BUTTON_PRESSED};
}}
""".strip()
