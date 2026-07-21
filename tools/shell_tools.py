"""
tools/shell_tools.py — инструменты запуска команд и процессов.

run_shell      — выполнить PowerShell команду, вернуть stdout/stderr/код
run_file       — запустить .py / .bat / .exe как фоновый процесс
list_processes — список процессов запущенных агентом в этой сессии
kill_process   — остановить процесс по PID
list_windows   — список видимых окон
close_window   — закрыть окно
"""
import html
import os
import re
import subprocess
import sys
import threading
import urllib.parse

# ── Чёрный список опасных команд ─────────────────────────────────────────────

_BLOCKED = [
    "format ", "format/", "diskpart",
    "rm -rf", "rm -r /", "del /s", "del /f /s",
    "rd /s", "rmdir /s",
    "shutdown", "restart-computer",
    "reg delete", "regedit",
    "bcdedit", "bootrec",
    "cipher /w",
    "net user", "net localgroup",
    "taskkill /f /im",
    ":(){:|:&};:",   # fork bomb
]


def _is_blocked(cmd: str) -> str | None:
    low = cmd.lower()
    for pattern in _BLOCKED:
        if pattern in low:
            return pattern
    return None


def _ok(data: dict) -> dict:
    return {"status": "ok", **data}


def _err(msg: str) -> dict:
    return {"status": "error", "error": msg}


# ── Реестр процессов (текущая сессия) ─────────────────────────────────────────

_lock = threading.Lock()
_processes: dict[int, dict] = {}


# ── Инструменты ───────────────────────────────────────────────────────────────

def run_shell(command: str, timeout: int = 60) -> dict:
    """
    Выполнить PowerShell команду и вернуть результат (stdout, stderr, exit_code).
    timeout: максимальное время ожидания в секундах (по умолчанию 60, максимум 300).
    Пример: run_shell("Get-ChildItem C:/Users") или run_shell("python --version")
    """
    blocked = _is_blocked(command)
    if blocked:
        return _err(
            f"Команда заблокирована по соображениям безопасности: содержит '{blocked}'. "
            f"Эта операция запрещена."
        )

    timeout = min(max(int(timeout), 1), 300)

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        return _ok({
            "exit_code": result.returncode,
            "stdout": stdout or "(нет вывода)",
            "stderr": stderr or "",
        })
    except subprocess.TimeoutExpired:
        return _err(f"Таймаут {timeout}с: {command!r}")
    except FileNotFoundError:
        return _err("PowerShell не найден.")
    except Exception as e:
        return _err(str(e))


def run_file(path: str, args: str = "") -> dict:
    """
    Запустить файл как фоновый процесс.
    .py, .bat, .cmd, .ps1, .exe — запускаются напрямую.
    Остальные файлы (.html, .pdf, .jpg и т.д.) открываются в программе по умолчанию.
    Поддерживает алиасы: workspace:, desktop:, documents:, downloads:, home:.
    Пример: run_file("workspace:script.py") или run_file("desktop:report.html")
    """
    from tools.path_utils import resolve_path

    real = resolve_path(path)
    if not os.path.exists(real):
        return _err(f"Файл не найден: {path!r}")

    ext = os.path.splitext(real)[1].lower()
    if ext == ".py":
        cmd = [sys.executable, real]
    elif ext in (".bat", ".cmd"):
        cmd = ["cmd", "/c", real]
    elif ext == ".ps1":
        cmd = ["powershell", "-NoProfile", "-File", real]
    elif ext == ".exe":
        cmd = [real]
    else:
        cmd = ["cmd", "/c", "start", "", real]

    if args:
        cmd += args.split()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(real),
        )
        name = os.path.basename(real)
        with _lock:
            _processes[proc.pid] = {"name": name, "cmd": " ".join(str(c) for c in cmd), "proc": proc}
        return _ok({"pid": proc.pid, "name": name, "message": f"Запущено: {name} (PID {proc.pid})"})
    except Exception as e:
        return _err(str(e))


def list_processes() -> dict:
    """
    Показать все процессы, запущенные агентом в этой сессии, и их статус.
    Пример: list_processes()
    """
    with _lock:
        if not _processes:
            return _ok({"result": "Нет запущенных процессов в этой сессии."})
        lines = []
        for pid, info in list(_processes.items()):
            proc = info["proc"]
            status = "работает" if proc.poll() is None else f"завершён ({proc.poll()})"
            lines.append(f"PID {pid}  [{status}]  {info['name']}")
        return _ok({"result": "\n".join(lines)})


def kill_process(pid: int) -> dict:
    """
    Остановить процесс по PID. Только процессы запущенные агентом в этой сессии.
    Пример: kill_process(12345)
    """
    with _lock:
        info = _processes.get(int(pid))
    if not info:
        return _err(f"PID {pid} не найден среди запущенных агентом процессов.")
    proc = info["proc"]
    if proc.poll() is not None:
        return _ok({"result": f"Процесс {pid} ({info['name']}) уже завершён."})
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return _ok({"result": f"Процесс {pid} ({info['name']}) остановлен."})
    except Exception as e:
        return _err(str(e))


def list_windows() -> dict:
    """
    Показать все видимые окна: PID, имя процесса, заголовок окна.
    Используй чтобы найти что закрыть. Пример: list_windows()
    """
    ps = (
        "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
        "Select-Object Id, Name, MainWindowTitle | "
        "ForEach-Object { \"PID $($_.Id)  [$($_.Name)]  $($_.MainWindowTitle)\" }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        if not output:
            return _ok({"result": "Видимых окон не найдено."})
        return _ok({"result": output})
    except subprocess.TimeoutExpired:
        return _err("Таймаут 10с при получении списка окон.")


def close_window(pid: int = 0, title: str = "") -> dict:
    """
    Закрыть окно (как нажать X). Используй pid ИЛИ title (частичное совпадение).
    Сначала вызови list_windows() чтобы найти нужный PID или заголовок.
    Примеры: close_window(pid=1234) или close_window(title="chrome")
    """
    if pid:
        ps = f"$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue; if ($p) {{ $p.CloseMainWindow() | Out-Null; 'closed' }} else {{ 'not found' }}"
    elif title:
        safe = title.replace("'", "")
        ps = (
            f"$p = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{safe}*'}} | Select-Object -First 1; "
            f"if ($p) {{ $p.CloseMainWindow() | Out-Null; \"Закрыто: PID $($p.Id) $($p.MainWindowTitle)\" }} else {{ 'Окно не найдено: {safe}' }}"
        )
    else:
        return _err("Укажи pid или title.")

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10
        )
        output = (result.stdout.strip() or result.stderr.strip())
        return _ok({"result": output})
    except subprocess.TimeoutExpired:
        return _err("Таймаут 10с при закрытии окна.")


# ── Веб-поиск ─────────────────────────────────────────────────────────────────

def _strip_html(raw: str, max_chars: int = 3000) -> str:
    """Превратить HTML в компактный читаемый текст без внешних зависимостей."""
    text = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav|form|aside).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) >= 40:
            lines.append(line)
    compact = "\n".join(lines)
    compact = re.sub(r"\n{3,}", "\n\n", compact).strip()
    return compact[:max_chars]


def _fetch_url_text(url: str, timeout: int = 20, max_chars: int = 3000) -> dict:
    """Открыть URL и вернуть очищенный текст страницы."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return _err(f"Неподдерживаемая схема URL: {parsed.scheme or '(пусто)'}")

        result = subprocess.run(
            [
                "curl.exe",
                "-s",
                "-L",
                "--compressed",
                "--max-time",
                str(max(5, min(timeout, 45))),
                "-A",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DeepSeekAgent/1.0",
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(8, min(timeout + 5, 55)),
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            return _err(f"curl вернул код {result.returncode}: {stderr or stdout}")
        if not stdout:
            return _err("Пустой ответ от сервера.")
        return _ok({"text": _strip_html(stdout, max_chars=max_chars), "raw_chars": len(stdout)})
    except FileNotFoundError:
        return _err("curl.exe не найден.")
    except subprocess.TimeoutExpired:
        return _err(f"Таймаут {timeout}с при запросе к URL.")
    except Exception as e:
        return _err(str(e))


def _grounded_search(query: str, max_results: int = 6) -> dict:
    """Вызвать Gemini grounding и вернуть текст + URL из metadata."""
    import json as _json
    import urllib.request
    from data import keystore

    keystore.load_if_exists()
    api_key = keystore.get("GEMINI_API_KEY")
    if not api_key:
        return _err("GEMINI_API_KEY не найден в keystore.")

    # Gemini Search grounding: model id менять только после проверки
    # официальной документации Google. LLM-память часто предлагает старые
    # Gemini/preview названия, которые уже не работают.
    model_id = "gemini-3.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    payload = _json.dumps({
        "contents": [{"role": "user", "parts": [{"text": query}]}],
        "tools": [{"google_search": {}}],
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = _json.loads(resp.read().decode("utf-8"))

    cand = data.get("candidates", [{}])[0]
    parts = cand.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()

    chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
    sources = []
    seen = set()
    for chunk in chunks:
        web = chunk.get("web") or {}
        source_url = web.get("uri") or ""
        if not source_url or source_url in seen:
            continue
        seen.add(source_url)
        sources.append({
            "title": web.get("title") or source_url,
            "url": source_url,
        })
        if len(sources) >= max(1, min(int(max_results), 10)):
            break

    return _ok({"answer": text, "sources": sources})

def web_search(url: str) -> dict:
    """
    Выполнить HTTP-запрос к указанному URL и вернуть содержимое как текст.
    Использует curl.exe (должен быть установлен в системе).
    Подходит для получения погоды, новостей, документации и т.д.
    Пример: web_search("https://wttr.in/Nikolaev?format=3")
    """
    try:
        result = subprocess.run(
            ["curl.exe", "-s", "-L", "--max-time", "15", url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            return {"status": "error", "error": f"curl вернул код {result.returncode}: {stderr or stdout}"}
        if not stdout:
            return {"status": "error", "error": "Пустой ответ от сервера."}
        return {"status": "ok", "result": stdout[:4000]}
    except FileNotFoundError:
        return {"status": "error", "error": "curl.exe не найден. Установи curl или используй run_shell с Invoke-WebRequest."}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Таймаут 20с при запросе к URL."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def search_web(query: str, max_results: int = 6) -> dict:
    """
    Найти информацию в интернете по поисковому запросу через Google (Gemini grounding).
    Возвращает текст ответа с реальными данными из интернета.
    Используй когда нужно найти что-то в интернете — просто напиши что ищешь на любом языке.
    Пример: search_web("погода Берлин сегодня") или search_web("SpaceX Starship последний запуск")
    """
    try:
        found = _grounded_search(query, max_results=max_results)
        if found.get("status") != "ok":
            return found
        text = found.get("answer", "")
        if not text:
            return {"status": "ok", "result": f"Ничего не найдено по запросу: {query!r}"}
        sources = found.get("sources", [])
        source_lines = [f"- {s['title']}: {s['url']}" for s in sources[:max_results]]
        suffix = "\n\nИсточники:\n" + "\n".join(source_lines) if source_lines else ""
        return {"status": "ok", "result": (text[:3500] + suffix)[:4500], "sources": sources}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def deep_research(query: str, max_results: int = 5) -> dict:
    """
    Глубокий интернет-поиск: найти через Google, открыть топ-ссылки и вернуть чистые выдержки страниц.
    Используй для исследований, новостей, сравнения источников и актуальных тем, где сниппетов мало.
    Пример: deep_research("новые тарифы Gemini image generation 2026", max_results=5)
    """
    try:
        max_results = max(1, min(int(max_results), 5))
        found = _grounded_search(query, max_results=max_results)
        if found.get("status") != "ok":
            return found

        sources = found.get("sources", [])
        pages = []
        for idx, source in enumerate(sources[:max_results], start=1):
            fetched = _fetch_url_text(source["url"], timeout=20, max_chars=2600)
            if fetched.get("status") == "ok":
                pages.append({
                    "rank": idx,
                    "title": source["title"],
                    "url": source["url"],
                    "text": fetched.get("text", ""),
                    "raw_chars": fetched.get("raw_chars", 0),
                })
            else:
                pages.append({
                    "rank": idx,
                    "title": source["title"],
                    "url": source["url"],
                    "error": fetched.get("error", "Не удалось открыть страницу."),
                })

        if not pages:
            return _ok({
                "query": query,
                "search_answer": found.get("answer", "")[:2500],
                "result": "Поиск сработал, но Gemini не вернул URL источников для чтения.",
                "sources": [],
            })

        lines = [
            f"Запрос: {query}",
            "",
            "Короткий ответ Gemini grounding:",
            found.get("answer", "")[:2200] or "(пусто)",
            "",
            "Прочитанные источники:",
        ]
        for page in pages:
            lines.append(f"\n[{page['rank']}] {page['title']}\nURL: {page['url']}")
            if page.get("error"):
                lines.append(f"Ошибка чтения: {page['error']}")
            else:
                lines.append(page.get("text", "")[:2600] or "(текст не извлечён)")

        return _ok({
            "query": query,
            "result": "\n".join(lines)[:14000],
            "sources": [{"title": p["title"], "url": p["url"], "error": p.get("error", "")} for p in pages],
        })
    except Exception as e:
        return {"status": "error", "error": str(e)}


ALL_SHELL_TOOLS = [
    run_shell, run_file, list_processes, kill_process, list_windows, close_window,
    web_search, search_web, deep_research,
]
