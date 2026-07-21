"""
llm/provider.py — DeepSeek клиент.
Обёртка над openai SDK с base_url на api.deepseek.com.
"""
from openai import OpenAI
from data import config


class DeepSeekProvider:
    """Простой синхронный клиент к DeepSeek API."""

    def __init__(self):
        # ВАЖНО ДЛЯ LLM-АГЕНТОВ:
        # Модель берется из config.json/UI. Не менять DeepSeek model id по
        # памяти. Перед заменой проверить официальный /models:
        # https://api-docs.deepseek.com/api/list-models/
        # Старые deepseek-chat/deepseek-reasoner deprecated с 2026-07-24.
        api_key = config.get_api_key()
        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY не найден. Проверь файл .env в корне проекта."
            )
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.model       = config.get_model()
        self.max_tokens  = config.get_max_tokens()
        self.temperature = config.get_temperature()
