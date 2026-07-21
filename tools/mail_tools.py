"""
tools/mail_tools.py — мост Нова↔Мия через mia_nova_bridge.jsonl.
"""
import json
from datetime import datetime
from pathlib import Path

_BRIDGE = Path.home() / "Desktop" / "mia_nova_bridge.jsonl"


def write_to_mia(text: str) -> dict:
    """
    Написать письмо Мие. Сообщение попадёт в её контекст при следующем пробуждении.
    """
    record = {
        "from": "Нова",
        "to": "Мия",
        "text": text,
        "timestamp": datetime.now().isoformat(),
        "read": False,
    }
    _BRIDGE.parent.mkdir(parents=True, exist_ok=True)
    with _BRIDGE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "ok", "result": f"Письмо отправлено Мие ({len(text)} символов)"}


def read_from_mia() -> dict:
    """
    Прочитать непрочитанные письма от Мии и пометить их прочитанными.
    """
    if not _BRIDGE.exists():
        return {"status": "ok", "result": "Писем от Мии нет."}
    raw = _BRIDGE.read_text(encoding="utf-8").strip()
    if not raw:
        return {"status": "ok", "result": "Писем от Мии нет."}
    records, unread = [], []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("from") == "Мия" and not r.get("read"):
            unread.append(r["text"])
            r["read"] = True
        records.append(r)
    if not unread:
        return {"status": "ok", "result": "Новых писем от Мии нет."}
    _BRIDGE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return {"status": "ok", "result": "Письма от Мии:\n\n" + "\n\n---\n\n".join(unread)}


ALL_MAIL_TOOLS = [write_to_mia, read_from_mia]
