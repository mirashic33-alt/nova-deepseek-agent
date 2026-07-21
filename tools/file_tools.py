"""
tools/file_tools.py — файловые инструменты агента.

Алиасы путей:
  desktop:   → Рабочий стол
  documents: → Документы
  downloads: → Загрузки
  workspace: → папка workspace/ проекта
  home:      → домашняя директория пользователя
"""
import os
import shutil
import fnmatch
from tools.path_utils import resolve_path, _PROJECT_ROOT


def _ok(data: str) -> dict:
    return {"status": "ok", "result": data}


def _err(msg: str) -> dict:
    return {"status": "error", "error": msg}


# ── Инструменты ───────────────────────────────────────────────────────────────

def list_files(path: str) -> dict:
    """
    Показать содержимое папки (файлы и подпапки).
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: list_files("workspace:") или list_files("desktop:projects")
    """
    try:
        real = resolve_path(path)
        if not os.path.exists(real):
            return _err(f"Путь не найден: {path!r}")
        if not os.path.isdir(real):
            return _err(f"Не папка: {path!r}")
        lines = []
        for name in sorted(os.listdir(real)):
            full = os.path.join(real, name)
            if os.path.isdir(full):
                lines.append(f"[dir]  {name}/")
            else:
                size = os.path.getsize(full)
                lines.append(f"[file] {name}  ({size:,} bytes)")
        return _ok("\n".join(lines) if lines else "(пустая папка)")
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


def read_file(path: str) -> dict:
    """
    Прочитать текстовое содержимое файла.
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: read_file("workspace:notes.txt")
    """
    try:
        real = resolve_path(path)
        if not os.path.exists(real):
            return _err(f"Файл не найден: {path!r}")
        if not os.path.isfile(real):
            return _err(f"Не файл: {path!r}")
        with open(real, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return _ok(content)
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


def write_file(path: str, content: str) -> dict:
    """
    Создать новый файл или полностью перезаписать существующий.
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: write_file("workspace:hello.txt", "Привет, мир!")
    """
    try:
        real = resolve_path(path)
        os.makedirs(os.path.dirname(real) or ".", exist_ok=True)
        with open(real, "w", encoding="utf-8") as f:
            f.write(content)
        return _ok(f"Записано {len(content):,} символов → {path!r}")
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


def append_file(path: str, content: str) -> dict:
    """
    Дописать текст в конец файла, не трогая существующее содержимое.
    Создаёт файл если не существует.
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: append_file("workspace:log.txt", "\\nНовая строка")
    """
    try:
        real = resolve_path(path)
        os.makedirs(os.path.dirname(real) or ".", exist_ok=True)
        with open(real, "a", encoding="utf-8") as f:
            f.write(content)
        return _ok(f"Добавлено {len(content):,} символов → {path!r}")
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


def patch_file(path: str, old_text: str, new_text: str) -> dict:
    """
    Заменить первое вхождение old_text на new_text в файле.
    Используй вместо write_file для правки небольшой части большого файла.
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: patch_file("workspace:notes.txt", "старая строка", "новая строка")
    """
    try:
        real = resolve_path(path)
        if not os.path.exists(real):
            return _err(f"Файл не найден: {path!r}")
        with open(real, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if old_text not in content:
            return _err(f"Текст не найден в файле: {old_text!r}")
        patched = content.replace(old_text, new_text, 1)
        with open(real, "w", encoding="utf-8") as f:
            f.write(patched)
        return _ok(f"Заменено 1 вхождение в {path!r}")
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


def create_dir(path: str) -> dict:
    """
    Создать папку, включая все недостающие родительские папки.
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: create_dir("workspace:projects/new_project")
    """
    try:
        real = resolve_path(path)
        os.makedirs(real, exist_ok=True)
        return _ok(f"Папка готова: {path!r}")
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


def delete_file(path: str) -> dict:
    """
    Удалить файл или папку. Отправляет в корзину (через send2trash).
    ВАЖНО: всегда запрашивай подтверждение у пользователя перед вызовом.
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: delete_file("workspace:old_notes.txt")
    """
    try:
        real = resolve_path(path)
        if not os.path.exists(real):
            return _err(f"Не найдено: {path!r}")
        try:
            import send2trash
            send2trash.send2trash(real)
            return _ok(f"Перемещено в корзину: {path!r}")
        except ImportError:
            pass
        if os.path.isdir(real):
            shutil.rmtree(real)
        else:
            os.remove(real)
        return _ok(f"Удалено (send2trash не установлен): {path!r}")
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


def rename_file(path: str, new_name: str) -> dict:
    """
    Переименовать файл или папку. new_name — только имя, не полный путь.
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: rename_file("workspace:old.txt", "new.txt")
    """
    try:
        real = resolve_path(path)
        if not os.path.exists(real):
            return _err(f"Не найдено: {path!r}")
        parent = os.path.dirname(real)
        dest = os.path.join(parent, new_name)
        if os.path.exists(dest):
            return _err(f"Уже существует: {new_name!r}")
        os.rename(real, dest)
        return _ok(f"Переименовано: {path!r} → {new_name!r}")
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


def move_file(path: str, dest_path: str) -> dict:
    """
    Переместить файл или папку в новое место.
    Поддерживает алиасы для обоих аргументов.
    Пример: move_file("workspace:draft.txt", "desktop:final.txt")
    """
    try:
        real_src = resolve_path(path)
        real_dst = resolve_path(dest_path)
        if not os.path.exists(real_src):
            return _err(f"Источник не найден: {path!r}")
        os.makedirs(os.path.dirname(real_dst) or ".", exist_ok=True)
        shutil.move(real_src, real_dst)
        return _ok(f"Перемещено: {path!r} → {dest_path!r}")
    except PermissionError:
        return _err("Нет доступа.")
    except Exception as e:
        return _err(str(e))


def search_files(path: str, pattern: str) -> dict:
    """
    Найти файлы по маске имени внутри папки (рекурсивно).
    pattern поддерживает wildcards: *.py, *.md, report*.txt и т.д.
    Поддерживает алиасы: desktop:, workspace:, documents:, downloads:, home:.
    Пример: search_files("desktop:", "*.py") или search_files("workspace:", "notes*")
    """
    try:
        real = resolve_path(path)
        if not os.path.exists(real):
            return _err(f"Путь не найден: {path!r}")
        if not os.path.isdir(real):
            return _err(f"Не папка: {path!r}")
        matches = []
        for root, dirs, files in os.walk(real):
            dirs.sort()
            for name in sorted(files):
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    rel = os.path.relpath(os.path.join(root, name), real)
                    size = os.path.getsize(os.path.join(root, name))
                    matches.append(f"{rel}  ({size:,} bytes)")
        if not matches:
            return _ok(f"Файлов по маске {pattern!r} в {path!r} не найдено")
        return _ok(f"Найдено {len(matches)} файл(ов):\n" + "\n".join(matches))
    except PermissionError:
        return _err(f"Нет доступа: {path!r}")
    except Exception as e:
        return _err(str(e))


_TREE_SKIP = {"__pycache__", "node_modules", ".git"}
_TREE_SKIP_PREFIX = ("backup_",)
_TREE_SKIP_EXT = {".pyc"}


def _skip_dir(name: str) -> bool:
    return name in _TREE_SKIP or any(name.startswith(p) for p in _TREE_SKIP_PREFIX)


def self_backup(reason: str = "") -> dict:
    """
    Умный бэкап кода перед самомодификацией. Исключает картинки, скриншоты,
    старые бэкапы — копирует только код и память (легко).
    reason: краткое описание причины (войдёт в имя папки).
    Пример: self_backup("before refactoring agent_loop")
    ОБЯЗАТЕЛЕН перед любым изменением файлов в tools/, core/, ui/, llm/.
    """
    import datetime
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    suffix = f"_{reason[:30].replace(' ', '_')}" if reason else ""
    backup_name = f"backup_{stamp}{suffix}"
    backup_dir = os.path.join(_PROJECT_ROOT, backup_name)

    _SKIP_NAMES = {"__pycache__", "node_modules", ".git", "images", "screenshots"}

    def _ignore(src, names):
        result = []
        for n in names:
            if n in _SKIP_NAMES or any(n.startswith(p) for p in _TREE_SKIP_PREFIX):
                result.append(n)
        return result

    try:
        shutil.copytree(_PROJECT_ROOT, backup_dir, ignore=_ignore)
        return _ok(f"Бэкап создан: {backup_name}/ (код+память, без картинок)")
    except Exception as e:
        return _err(str(e))


def restart_self(reason: str = "") -> dict:
    """
    Перезапустить агента через 2 секунды. Watchdog (watchdog.pyw) поднимет новый процесс.
    ВСЕГДА вызывай self_backup() перед этим и передай reason — что сделано и что осталось.
    reason: краткое описание причины перезапуска.
            Не подменяет write_progress_report(): если progress.json уже записан,
            restart_self его не перезаписывает.
    Чтобы остановить агента НАСОВСЕМ (без перезапуска) — сначала создай файл STOP.flag:
        write_file("STOP.flag", "stop")
    Потом вызывай restart_self() — watchdog увидит флаг и не будет поднимать.
    Пример перезапуска: restart_self("поправил bot.py и keystore, осталось проверить callback")
    """
    import os, threading, subprocess, time, json as _json

    # Если модель забыла вызвать write_progress_report(), оставляем безопасную
    # записку без "продолжить с места остановки". Generic remaining раньше
    # загонял агента в повторные проверки и перезапуски.
    if reason:
        workspace = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace")
        os.makedirs(workspace, exist_ok=True)
        progress_path = os.path.join(workspace, "progress.json")
        if not os.path.exists(progress_path):
            try:
                _json.dump({
                    "status": "done",
                    "needs_user": False,
                    "task": reason,
                    "done": [reason],
                    "result": "Перезапуск выполнен. Явных незавершённых действий не записано.",
                    "remaining": [],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }, open(progress_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            except Exception:
                pass

    pid = os.getpid()

    def _delayed_kill():
        time.sleep(2)
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)

    t = threading.Thread(target=_delayed_kill, daemon=True)
    t.start()
    return _ok(f"Перезапуск через 2 сек (PID {pid}). Watchdog поднимет обновлённую версию.")


def get_project_tree() -> dict:
    """
    Показать дерево файлов и папок проекта, начиная с корня.
    Используй когда нужно найти путь к файлу или понять структуру проекта.
    Вызывай ПЕРВЫМ когда не знаешь где лежит нужный файл.
    """
    root = _PROJECT_ROOT
    project_name = os.path.basename(root)
    lines = [f"📁 {project_name}/  ← корень проекта"]
    try:
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if not _skip_dir(d))
            depth = os.path.relpath(dirpath, root).count(os.sep)
            if dirpath != root:
                indent = "  " * depth
                lines.append(f"{indent}📁 {os.path.basename(dirpath)}/")
            file_indent = "  " * (depth + 1)
            for fname in sorted(files):
                if os.path.splitext(fname)[1].lower() not in _TREE_SKIP_EXT:
                    lines.append(f"{file_indent}📄 {fname}")
    except Exception as e:
        return _err(str(e))
    return _ok("\n".join(lines))


def write_progress_report(
    task: str = "",
    done: str = "",
    result: str = "",
    remaining: str = "",
    status: str = "",
    needs_user: bool = False,
) -> dict:
    """
    Записать отчёт о проделанной работе в progress.json.
    Вызывай ПЕРЕД restart_self() — чтобы после перезапуска агент знал, что уже сделано.

    task: краткое название задачи (например "Исправить дубликат картинок")
    done: что уже сделано, какие файлы изменены
    result: итоговый результат (например "Картинки отправляются 1 раз, а не 2")
    remaining: только реальные незавершённые действия. Не пиши сюда
               "проверить", "убедиться", "wait for user response".
               Пусто = задача завершена.
    status: in_progress | done | needs_user. Если пусто — вычисляется автоматически.
    needs_user: True, если cannot continue without user response.

    После перезапуска агент продолжает только если status=in_progress и
    remaining содержит реальные действия. Пустой remaining = задача завершена.
    """
    import os, time, json as _json
    workspace = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace")
    os.makedirs(workspace, exist_ok=True)
    progress_path = os.path.join(workspace, "progress.json")
    
    # Разбираем done и remaining в списки
    done_list = [s.strip() for s in done.split("\\n") if s.strip()] if done else []
    remaining_list = [s.strip() for s in remaining.split("\\n") if s.strip()] if remaining else []
    
    status_value = (status or "").strip().lower()
    if status_value not in {"in_progress", "done", "needs_user"}:
        if needs_user:
            status_value = "needs_user"
        elif remaining_list:
            status_value = "in_progress"
        else:
            status_value = "done"

    data = {
        "status": status_value,
        "needs_user": bool(needs_user) or status_value == "needs_user",
        "task": task or "",
        "done": done_list,
        "result": result or "",
        "remaining": remaining_list,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        _json.dump(data, open(progress_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return _ok(
            f"progress.json обновлён: status={status_value}, "
            f"задача={task!r}, сделано={len(done_list)} пунктов, осталось={len(remaining_list)}"
        )
    except Exception as e:
        return _err(str(e))


ALL_TOOLS = [
    list_files, read_file, write_file, append_file, patch_file,
    create_dir, delete_file, rename_file, move_file,
    search_files, get_project_tree, self_backup, restart_self,
    write_progress_report,
]
