"""
tools/image_tools.py — генерация и анализ картинок через Gemini API.
"""
import base64
import io
import requests
from pathlib import Path
from datetime import datetime

from PIL import Image
from data import config

_PROJECT_ROOT = Path(__file__).parent.parent
_IMAGES_DIR = _PROJECT_ROOT / "workspace" / "images"

# ВАЖНО ДЛЯ LLM-АГЕНТОВ:
# Эти model id проверены по официальной документации Google 2026-07-18.
# Не заменять их на "знакомые" старые названия из памяти модели
# (например gemini-2.0-flash, imagen*, *-preview) без свежей проверки:
# https://ai.google.dev/gemini-api/docs/image-generation
# https://ai.google.dev/gemini-api/docs/pricing
_MODELS = {
    "flash": "gemini-3.1-flash-image",
    "pro":   "gemini-3-pro-image",
    "2.5":   "gemini-2.5-flash-image",
}


def _get_key() -> str:
    from data import keystore
    return keystore.get("GEMINI_API_KEY") or keystore.get("GOOGLE_API_KEY")


def _normalize_image_size(value: str) -> str:
    value = str(value or "").upper()
    return value if value in {"1K", "2K", "4K"} else config.get_image_size()


def generate_image(prompt: str, image_size: str = "") -> dict:
    """
    Сгенерировать картинку по текстовому описанию (16:9) и сохранить в workspace/images/.
    image_size: 1K, 2K или 4K. Если не указано, берётся из настроек.
    Промпт лучше на английском.
    Пример: generate_image("futuristic city at night, neon lights, cyberpunk")
    """
    key = _get_key()
    if not key:
        return {"status": "error", "error": "GEMINI_API_KEY не найден. Добавь в настройки."}

    model_id = _MODELS["flash"]
    requested_size = _normalize_image_size(image_size)
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = _IMAGES_DIR / f"gen_{ts}.png"

    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    body = {
        "model": model_id,
        "input": prompt,
        "response_format": {
            "type": "image",
            "aspect_ratio": "16:9",
            "image_size": requested_size,
        },
    }
    try:
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=120)
    except requests.Timeout:
        return {"status": "error", "error": "Таймаут 120с при обращении к Gemini API"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

    if r.status_code != 200:
        return {"status": "error", "error": f"Gemini вернул {r.status_code}: {r.text[:500]}"}

    data = r.json()
    img = None
    for step in data.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if block.get("type") == "image" and block.get("data"):
                img = base64.b64decode(block["data"])
                break
        if img:
            break

    if not img:
        # Backward-compatible fallback for older generateContent-style responses.
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for p in parts:
            blob = p.get("inline_data") or p.get("inlineData")
            if blob and blob.get("data"):
                img = base64.b64decode(blob["data"])
                break
    if not img:
        return {"status": "error", "error": f"В ответе Gemini нет картинки: {str(data)[:400]}"}

    out_path.write_bytes(img)
    return {
        "status": "ok",
        "result": (
            f"Картинка сохранена ({requested_size}, {len(img):,} байт): "
            f"[[ФОТО: {out_path}]]"
        ),
    }


def analyze_image(image_path: str, question: str = "") -> dict:
    """
    Проанализировать картинку через Gemini Vision и вернуть текстовое описание.
    image_path: абсолютный путь к файлу (jpg/png).
    question: уточняющий вопрос (опционально).
    """
    key = _get_key()
    if not key:
        return {"status": "error", "error": "GEMINI_API_KEY не найден"}

    path = Path(image_path)
    if not path.exists():
        return {"status": "error", "error": f"Файл не найден: {image_path}"}
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > 1600:
                ratio = 1600 / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()
            mime = "image/jpeg"
    except Exception:
        img_bytes = path.read_bytes()
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"

    img_b64 = base64.b64encode(img_bytes).decode()

    # Gemini Vision: не менять по памяти. Перед заменой проверить официальный
    # список/доки Google; старые Gemini 2.0/preview id уже ломали Нову.
    model_id = "gemini-2.5-flash"
    prompt = question if question else "Опиши подробно что изображено на этой картинке."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": img_b64}},
            ]
        }]
    }
    try:
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=60)
    except Exception as e:
        return {"status": "error", "error": f"Ошибка Gemini Vision: {e}"}

    if r.status_code != 200:
        return {"status": "error", "error": f"Gemini Vision {r.status_code}: {r.text[:300]}"}

    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return {"status": "ok", "result": text}
    except Exception:
        return {"status": "error", "error": f"Не удалось разобрать ответ Gemini: {r.text[:300]}"}


ALL_IMAGE_TOOLS = [generate_image, analyze_image]
