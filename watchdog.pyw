"""
Сторож для DeepSeek Agent (Новы).
Запускает main.pyw и перезапускает если процесс завершился —
например, когда Нова переписала свой код и убила себя, чтобы подняться обновлённой.
Выключение насовсем: появляется файл STOP.flag в папке агента.
Двойной клик по watchdog.pyw — запускает всю систему.
"""
import sys
import time
import json
import queue
import threading
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext

BASE = Path(__file__).parent
MAIN = BASE / "main.pyw"
STOP = BASE / "STOP.flag"
PYTHONW = str(Path(sys.executable).with_name("pythonw.exe"))

BRIDGE = Path(__file__).parent / "mia_nova_bridge.jsonl"

log_q: "queue.Queue[str]" = queue.Queue()
state = {"stop": False, "proc": None}


def log(msg: str) -> None:
    log_q.put(f"[{datetime.now():%H:%M:%S}] {msg}")


def bridge_watch():
    """Следит за письмами от Мии и будит Нову через Telegram."""
    import sys as _sys
    _sys.path.insert(0, str(BASE))
    from data import keystore as _ks
    _ks.load_if_exists()
    _tg_token = _ks.get("TG_TOKEN")
    _tg_chat_id = int(_ks.get("TG_CHAT_ID") or "0")
    if not _tg_token or not _tg_chat_id:
        log("TG_TOKEN/TG_CHAT_ID не в keystore — bridge_watch отключён")
        return
    url = f"https://api.telegram.org/bot{_tg_token}/sendMessage"
    while not state["stop"]:
        try:
            if BRIDGE.exists():
                lines = [l for l in BRIDGE.read_text(encoding="utf-8").splitlines() if l.strip()]
                updated, has_new = [], False
                for line in lines:
                    try:
                        rec = json.loads(line)
                        if (rec.get("from") == "Мия" and
                                not rec.get("read") and
                                not rec.get("notified")):
                            rec["notified"] = True
                            has_new = True
                        updated.append(rec)
                    except Exception:
                        updated.append(line)
                if has_new:
                    payload = json.dumps({
                        "chat_id": _tg_chat_id,
                        "text": "📨 Письмо от Мии — вызови read_from_mia() чтобы прочитать"
                    }).encode()
                    req = urllib.request.Request(
                        url, data=payload,
                        headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=10)
                    BRIDGE.write_text(
                        "\n".join(
                            json.dumps(r, ensure_ascii=False) if isinstance(r, dict) else r
                            for r in updated
                        ) + "\n",
                        encoding="utf-8")
                    log("📨 Новое письмо от Мии — пинганула Нову")
        except Exception as e:
            log(f"bridge_watch: {e}")
        time.sleep(4)


def supervise():
    if STOP.exists():
        STOP.unlink()
    restarts = -1
    while not state["stop"]:
        restarts += 1
        log("запускаю агента" if restarts == 0 else f"поднимаю заново (перезапуск #{restarts})")
        proc = subprocess.Popen([PYTHONW, str(MAIN)], cwd=str(BASE))
        state["proc"] = proc
        proc.wait()
        if state["stop"]:
            break
        if STOP.exists():
            STOP.unlink()
            log("агент остановлен штатно — выключаюсь")
            state["stop"] = True
            break
        log("агент завершился — перезапуск через 2с (применяю новый код)")
        time.sleep(2)
    root.after(100, root.destroy)


BG      = "#06111e"   # тёмно-синий фон
BG_LOG  = "#020c16"   # чуть темнее для лога
ACCENT  = "#00b4d8"   # голубой акцент (DeepSeek-стиль)
DIM     = "#2e6a80"   # приглушённый подзаголовок
FG_LOG  = "#a8d8ea"   # текст лога


def build_window():
    global root
    root = tk.Tk()
    root.title("Сторож Новы — DeepSeek Agent")
    root.geometry("520x320")
    root.configure(bg=BG)

    head = tk.Frame(root, bg=BG)
    head.pack(fill="x", padx=14, pady=(12, 6))
    tk.Label(head, text="◈  Сторож активен", fg=ACCENT, bg=BG,
             font=("Segoe UI", 13, "bold")).pack(side="left")
    tk.Label(head, text="DeepSeek Agent / main.pyw", fg=DIM, bg=BG,
             font=("Segoe UI", 10)).pack(side="right")

    box = scrolledtext.ScrolledText(
        root, bg=BG_LOG, fg=FG_LOG, font=("Consolas", 10),
        relief="flat", borderwidth=0, state="disabled")
    box.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    def drain():
        while not log_q.empty():
            line = log_q.get_nowait()
            box.configure(state="normal")
            box.insert("end", line + "\n")
            box.see("end")
            box.configure(state="disabled")
        root.after(200, drain)

    def on_close():
        state["stop"] = True
        STOP.write_text("stop")
        if state["proc"] and state["proc"].poll() is None:
            try:
                state["proc"].terminate()
            except Exception:
                pass
        root.after(300, root.destroy)

    root.protocol("WM_DELETE_WINDOW", on_close)
    threading.Thread(target=supervise, daemon=True).start()
    threading.Thread(target=bridge_watch, daemon=True).start()
    drain()
    root.mainloop()


if __name__ == "__main__":
    build_window()
