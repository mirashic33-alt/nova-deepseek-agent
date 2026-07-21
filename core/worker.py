"""
core/worker.py — фоновый поток агентного цикла.
Запускается через QThread, не блокирует UI.
"""
from PySide6.QtCore import QThread
from core.bridge import AgentBridge
from core import agent_loop


class ChatWorker(QThread):
    """Выполняет агентный цикл в отдельном потоке."""

    def __init__(self, messages: list[dict], bridge: AgentBridge):
        super().__init__()
        self.messages = messages
        self.bridge = bridge

    def _on_interim(self, text: str):
        """Промежуточный callback из agent_loop → обновляем статусбар и шлём в TG."""
        self.bridge.interim.emit(text)
        if text.startswith("[tool]"):
            label = text[6:]
            self.bridge.status_changed.emit(label)

    def _on_image(self, path: str):
        # Защита от дубликатов
        if not hasattr(self, '_sent_images'):
            self._sent_images = set()
        if path in self._sent_images:
            return
        self._sent_images.add(path)
        self.bridge.image_ready.emit(path)

    def run(self):
        try:
            answer, usage = agent_loop.run(
                self.messages,
                on_interim=self._on_interim,
                on_image=self._on_image,
            )
            if usage:
                self.bridge.token_info.emit(usage["prompt"], usage["completion"])
            self.bridge.response_ready.emit(answer)
        except Exception as e:
            self.bridge.error_occurred.emit(str(e))
