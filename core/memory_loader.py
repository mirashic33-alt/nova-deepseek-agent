"""
core/memory_loader.py — загрузка файлов памяти в системный промт.

Порядок загрузки при старте:
  workspace/agent.md    — правила, инструменты, алиасы  [пишет разработчик]
  workspace/MEMORY.md   — долгосрочные факты              [пишет агент]
  workspace/USER.md     — факты о пользователе            [пишет агент]
  workspace/SOUL.md     — личность и имя агента           [пишет агент]
  workspace/STYLE.md    — манера речи                     [пишет агент]
  workspace/skills/*.md — навыки, по одному файлу         [пишет агент]
"""
import glob
import os
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent / "workspace"

_NON_ACTION_REMAINING_PREFIXES = (
    "проверить",
    "убедиться",
    "дождаться",
    "ждать",
    "посмотреть глазами",
    "просто проверить",
    "продолжить с места остановки",
)

_MEMORY_FILES = [
    ("agent.md",  "AGENT"),
    ("MEMORY.md", "MEMORY"),
    ("USER.md",   "USER"),
    ("SOUL.md",   "SOUL"),
    ("STYLE.md",  "STYLE"),
]


def _load_skills() -> str:
    """Читает навыки из workspace/skills/ (только прямые файлы, не library/).
    Загружает .md (кроме README.md) и .py/.json файлы.
    Полные скиллы из skills/library/ — ленивая загрузка через read_file."""
    skills_dir = WORKSPACE / "skills"
    if not skills_dir.is_dir():
        return ""
    parts = []
    for path in sorted(skills_dir.iterdir()):
        if path.is_dir():
            continue
        if path.suffix.lower() == ".md" and path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() not in (".md", ".py", ".json"):
            continue
        try:
            content = path.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"--- SKILL: {path.name} ---\n{content}")
        except Exception:
            pass
    return "\n\n".join(parts)


def load_system_prompt() -> str:
    """
    Читает файлы workspace и собирает полный системный промт.
    Отсутствующие файлы пропускаются молча (MEMORY, SOUL, USER — могут быть пустыми).
    """
    sections: list[str] = []

    # ── Progress.json: флаг прогресса, выживающий перезапуск ──────────────
    progress_path = WORKSPACE / "progress.json"
    if progress_path.exists():
        try:
            import json
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            done = progress.get("done", [])
            remaining = progress.get("remaining", [])
            if isinstance(done, str):
                done = [done]
            if isinstance(remaining, str):
                remaining = [remaining]
            actionable_remaining = []
            for item in remaining:
                text = str(item).strip()
                lowered = text.lower()
                if not text:
                    continue
                if any(lowered.startswith(prefix) for prefix in _NON_ACTION_REMAINING_PREFIXES):
                    continue
                actionable_remaining.append(text)
            task = progress.get("task", "")
            result = progress.get("result", "")
            status = str(progress.get("status") or "").lower()
            needs_user = bool(progress.get("needs_user")) or status == "needs_user"

            lines = []
            if task:
                lines.append(f"Задача: {task}")
            if done:
                lines.append("Уже сделано: " + ", ".join(map(str, done)))
            if result:
                lines.append(f"Результат: {result}")

            if needs_user:
                if remaining:
                    lines.append("Нужно from user: " + ", ".join(map(str, remaining)))
                sections.append(
                    "--- PROGRESS (ожидается решение пользователя) ---\n"
                    + "\n".join(lines)
                    + "\n\nНЕ правь файлы и НЕ перезапускайся. Коротко ask the user, что делать дальше."
                )
            elif status == "in_progress" and actionable_remaining:
                lines.append("Осталось сделать: " + ", ".join(actionable_remaining))
                sections.append(
                    "--- PROGRESS (есть незавершённые действия после перезапуска) ---\n"
                    + "\n".join(lines)
                    + "\n\nПродолжи только пункты из 'Осталось сделать'. НЕ начинай задачу с нуля."
                )
            elif lines:
                sections.append(
                    "--- PROGRESS (прошлая задача завершена) ---\n"
                    + "\n".join(lines)
                    + "\n\nЭто отчёт, а не команда. НЕ продолжай задачу заново и НЕ перезапускайся повторно."
                )
        except Exception:
            pass

    for filename, label in _MEMORY_FILES:
        path = WORKSPACE / filename
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    sections.append(f"--- {label} ---\n{content}")
            except Exception as e:
                sections.append(f"--- {label} --- (ошибка загрузки: {e})")

    # ── Дайджесты: письма себе за последние дни ──────────────────────────
    digests_dir = WORKSPACE / "digests"
    if digests_dir.is_dir():
        digest_files = sorted(digests_dir.glob("*.md"))[-3:]  # последние 3
        if digest_files:
            digest_parts = []
            for f in digest_files:
                try:
                    content = f.read_text(encoding="utf-8").strip()
                    if content and content != "(пустой день)":
                        digest_parts.append(f"[{f.stem}]\n{content}")
                except Exception:
                    pass
            if digest_parts:
                sections.append(
                    "--- DAILY DIGESTS (письма себе за последние дни) ---\n"
                    + "\n\n".join(digest_parts)
                )

    # ── Вики INDEX: ленивая загрузка энциклопедии ──────────────────────────
    wiki_index = WORKSPACE / "вики" / "INDEX.md"
    if wiki_index.exists():
        try:
            content = wiki_index.read_text(encoding="utf-8").strip()
            if content:
                sections.append(f"--- WIKI INDEX ---\n{content}")
        except Exception:
            pass

    # ── Чувство времени: time since last user message ────
    try:
        import json
        from datetime import datetime
        hist_path = WORKSPACE / "chat_history.json"
        if hist_path.exists():
            hist = json.loads(hist_path.read_text(encoding="utf-8"))
            user_msgs = [m for m in hist if m.get("role") == "user"]
            if user_msgs:
                last = user_msgs[-1]
                ts_str = last.get("timestamp", "")
                if ts_str:
                    last_time = datetime.fromisoformat(ts_str)
                    now = datetime.now().astimezone()
                    # Если last_time без таймзоны — считаем что это локальное время
                    if last_time.tzinfo is None:
                        last_time = last_time.replace(tzinfo=now.tzinfo)
                    pause = (now - last_time).total_seconds()
                    if pause < 0:
                        pause = 0
                    if pause < 60:
                        pause_str = f"Последнее сообщение from user было {int(pause)} сек. назад."
                    elif pause < 3600:
                        pause_str = f"Последнее сообщение from user было {int(pause/60)} мин. назад."
                    else:
                        pause_str = f"Последнее сообщение from user было {int(pause/3600)} ч. {int((pause%3600)/60)} мин. назад."
                    sections.append(f"--- TIME_SENSE ---\n{pause_str}")
    except Exception:
        pass

    # ── Письма от Мии через бридж ──────────────────────────────────────────
    bridge_path = Path.home() / "Desktop" / "mia_nova_bridge.jsonl"
    if bridge_path.exists():
        try:
            raw = bridge_path.read_text(encoding="utf-8").strip()
            if raw:
                import json as _json
                unread = []
                for line in raw.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    r = _json.loads(line)
                    if r.get("from") == "Мия" and not r.get("read"):
                        unread.append(r["text"])
                if unread:
                    sections.append(
                        "--- ПИСЬМА ОТ МИИ ---\n"
                        + "\n---\n".join(unread)
                        + "\n\nОтветить Мие: вызови инструмент write_to_mia(text)."
                    )
        except Exception:
            pass

    skills_block = _load_skills()
    if skills_block:
        sections.append(skills_block)

    if not sections:
        return "You are a helpful AI assistant."

    return "\n\n".join(sections)
