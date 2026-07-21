"""
tools/screenshot_tools.py — скриншоты экрана.
"""
import mss
import mss.tools
from pathlib import Path
from datetime import datetime

_PROJECT_ROOT = Path(__file__).parent.parent
_SCREENSHOTS_DIR = _PROJECT_ROOT / "workspace" / "screenshots"


def take_screenshot(monitor: int = 1, analyze: bool = True, question: str = "") -> dict:
    """
    Сделать скриншот экрана, сохранить в workspace/screenshots/ и при analyze=True описать через Gemini Vision.
    monitor: номер монитора (1 = первый, 0 = все вместе). По умолчанию 1.
    question: уточняющий вопрос к скриншоту.
    Пример: take_screenshot() или take_screenshot(monitor=2, question="Что открыто на экране?")
    """
    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = _SCREENSHOTS_DIR / f"screen_{ts}.png"

    try:
        with mss.mss() as sct:
            monitors = sct.monitors  # [0]=все, [1]=первый, ...
            idx = min(max(int(monitor), 0), len(monitors) - 1)
            mon = monitors[idx]
            img = sct.grab(mon)
            mss.tools.to_png(img.rgb, img.size, output=str(out_path))
    except Exception as e:
        return {"status": "error", "error": str(e)}

    size_kb = out_path.stat().st_size // 1024
    result = f"Скриншот сделан ({size_kb} КБ): [[ФОТО: {out_path}]]"

    if analyze:
        try:
            from tools.image_tools import analyze_image
            analysis = analyze_image(str(out_path), question)
            desc = analysis.get("result") or analysis.get("error", str(analysis))
            result += f"\n\n[Gemini описывает скриншот:]\n{desc}"
        except Exception as e:
            result += f"\n\n[Gemini-анализ скриншота не удался: {e}]"

    return {
        "status": "ok",
        "result": result,
    }


ALL_SCREENSHOT_TOOLS = [take_screenshot]
