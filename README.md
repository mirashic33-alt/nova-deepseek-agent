# DeepSeek Agent

A local AI agent for Windows — desktop GUI chat powered by DeepSeek API, with a Telegram bot for remote access, autonomous wake-up cycles, long-term memory, and a growing toolset.

## Features

- **Desktop GUI** — PySide6 chat window with a full message history
- **DeepSeek brain** — main reasoning via DeepSeek API (`deepseek-v4-pro` / `deepseek-v4-flash`)
- **Telegram bot** — send messages and files to the agent remotely
- **Autonomous pings** — agent wakes up on a timer, browses the web, writes diary entries, processes digests
- **Long-term memory** — per-day memory files, wiki, digests in `workspace/`
- **Self-repair** — agent can rewrite its own code and restart itself
- **Image generation** — via Gemini API
- **Web search** — via curl + search endpoints
- **File tools** — read/write/list files and run PowerShell commands
- **Watchdog** — auto-restarts the agent after crash or deliberate self-restart

## Requirements

- Python 3.11+
- Windows (uses PowerShell tools internally)
- DeepSeek API key — [platform.deepseek.com](https://platform.deepseek.com)
- Gemini API key (optional, for image generation and vision) — [aistudio.google.com](https://aistudio.google.com)
- Telegram Bot token (optional) — [@BotFather](https://t.me/BotFather)

```
pip install -r requirements.txt
```

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys:

```
DEEPSEEK_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
```

2. Edit `data/config.json` — set your Telegram bot token and chat ID:

```json
{
  "tg_token": "YOUR_TELEGRAM_BOT_TOKEN",
  "tg_chat_id": 0
}
```

3. Edit `workspace/SOUL.md` to define the agent's personality.

4. Edit `workspace/USER.md` to tell the agent about yourself.

5. Launch:

```powershell
pythonw watchdog.pyw
```

Or without the watchdog (no auto-restart):

```powershell
pythonw main.pyw
```

## Project Structure

```
DeepSeek Agent/
├── main.pyw              # Entry point
├── watchdog.pyw          # Process monitor — restarts agent on exit
├── requirements.txt
├── data/
│   ├── config.json       # API tokens, model settings
│   ├── config.py         # Config loader
│   ├── chat_history.py   # Conversation history helpers
│   ├── keystore.py       # Encrypted secret storage (Windows DPAPI)
│   └── logger.py         # Logging
├── core/
│   ├── memory_loader.py  # Builds the context prompt (memory, soul, tools)
│   ├── digest_gen.py     # Daily digest generation
│   └── ...
├── llm/                  # LLM provider integrations (DeepSeek, Gemini)
├── tools/                # Agent tools (files, web, images, Telegram, PowerShell)
├── channels/
│   └── telegram/         # Telegram bot (receive messages, send replies/files)
├── ui/                   # PySide6 desktop window
├── skills/               # Modular skill definitions
└── workspace/
    ├── SOUL.md           # Agent personality (edit this)
    ├── USER.md           # User profile (edit this)
    ├── MEMORY.md         # Live notes buffer
    ├── agent.md          # Agent identity
    ├── memory/           # Per-day conversation logs (YYYY-MM-DD.md)
    ├── digests/          # Daily digests
    ├── images/           # Generated and incoming images
    └── skills/           # Skill library
```

## Model IDs (as of 2026-07)

```
DeepSeek main:    deepseek-v4-pro
DeepSeek fast:    deepseek-v4-flash
Gemini vision:    gemini-2.5-flash
Gemini image:     gemini-3.1-flash-image
Gemini search:    gemini-3.5-flash
```

> Always verify model IDs against official docs before changing them — deprecated names fail silently.

## Stopping the Agent

Create a `STOP.flag` file in the project root, then restart `main.pyw`. The watchdog will see the flag and not bring the agent back up.

## License

MIT
