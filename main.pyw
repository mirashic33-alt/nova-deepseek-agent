"""
main.pyw — точка входа DeepSeek Agent.
Запускать: pythonw main.pyw  (или через start_agent.bat)
"""
import sys
import logging
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from data import config, keystore
from data.logger import setup_file_logging

keystore.load_if_exists()  # расшифровываем secrets/keys.enc (или мигрируем из .env)
setup_file_logging()  # все логи только в agent.log, консоль чистая


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DeepSeek Agent")
    app.setApplicationVersion("0.2.0")

    _log = logging.getLogger("main")
    _log.info("=" * 60)
    _log.info(f"DeepSeek Agent v0.2 | model={config.get_model()} | tokens={config.get_max_tokens()}")

    from core.digest_gen import start_digest_check
    start_digest_check()

    window = MainWindow()
    window.show()

    # Запускаем Telegram бота если настроен
    tg_bot = None
    if config.is_tg_configured():
        try:
            from channels.telegram.bot import TelegramBot
            tg_bot = TelegramBot(
                token=config.get_tg_token(),
                chat_id=config.get_tg_chat_id(),
                bridge=window._bridge,
            )
            tg_bot.start()
            window.set_tg_bot(tg_bot)
            logging.getLogger("main").info(
                f"Telegram bot started (chat_id={config.get_tg_chat_id()})"
            )
        except Exception as e:
            logging.getLogger("main").error(f"Telegram bot failed to start: {e}")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
