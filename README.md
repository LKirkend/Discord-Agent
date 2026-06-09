# Antigravity Discord Liaison Bot (Unified Workspace)

A centralized, interactive Discord bot and API daemon designed to act as an approval liaison, dashboard monitor, and message routing hub for Google Antigravity SDK agents. 

This repository consolidates the bot backend code into a single, unified codebase at the root level, serving both Antigravity-IDE and Antigravity 2 clients.

---

## 🎯 Long-Term Goal
A standalone Discord bot that can act as a liaison to AI models requesting permissions or requiring user input, serving that data from Discord DM chats & servers. Compatible with Antigravity-IDE and Antigravity 2, but aiming to be an agent compatible with any model that acts as a user message delivery and translation layer. Aiming for Odysseus support soon.

---

## 📂 Repository Structure

- `/` (Root): Contains the consolidated daemon backend Python modules:
  - `bot.py`: Core Discord bot loop and message dispatch logic.
  - `web_server.py`: FastAPI server processing `/approve` hooks and serving the status bar web UI.
  - `discord_policy.py`: Safe policy hooks loaded into client agents to delegate tool execution confirmations.
  - `discord_ui.py`: UI views and input modals.
  - `agent_manager.py`: Spawns and manages agent instances.
  - `helpers.py`: Directory scanner, project resolver, and process utilities.
  - `state.py`: Configuration and shared variable states.
  - `install.py`: macOS LaunchAgent daemon registration script.
  - `config.json`: Dynamic endpoints and API key configuration settings.
- `/ide`: Specific VS Code extension files (such as compiled `main.js` integrations).
- `/agy2`: Specific Antigravity 2 GUI extension assets and scripts.

---

## 🚀 Running in Standalone Mode

The daemon can run as a standalone service, acting as an OpenAI-compatible API translation proxy layer for any IDE, local script, or agent.

1. Install dependencies in your virtual environment:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the daemon:
   ```bash
   python3 bot.py
   ```
   Upon startup, the daemon binds to the port specified in `config.json` (default: `18000`) and logs:
   `🚀 Discord Liaison Standalone API running on http://localhost:18000/v1`

---

## ⚙️ Configuration & Endpoints (`config.json`)

To set target LLMs and keys, edit [config.json](file:///Users/logankirkendall/Documents/antigravity/discord-agent/config.json) in the root directory:

```json
{
  "model_provider": "gemini",
  "auto_switch_local": false,
  "discord_bot_permissions": "8471182706732241",
  "local_endpoint": "http://localhost:11434/v1",
  "local_model_name": "qwen2.5-coder:7b",
  "remote_endpoint": "",
  "remote_api_key": "",
  "port": 18000
}
```

### Options:
- **`model_provider`**: `"gemini"` or `"ollama"`.
- **`local_endpoint`**: The base URL of your local Ollama instance (default: `http://localhost:11434/v1`).
- **`local_model_name`**: The model Ollama should run (default: `qwen2.5-coder:7b`).
- **`remote_endpoint`**: Optional custom OpenAI-compatible remote endpoint. If left empty when provider is `"gemini"`, defaults to the Google Gemini OpenAI-compatibility API endpoint (`https://generativelanguage.googleapis.com/v1beta/openai`).
- **`remote_api_key`**: Your API key (e.g., Gemini API Key). If left empty, fallback to environment `GEMINI_API_KEY` is used.
- **`port`**: Port for the daemon web server (default: `18000`).

---

## 🔌 Connecting Clients (IDE / Scripts)

To route any OpenAI-compatible client (like Cursor, VSCode extensions, custom agent scripts, or Ollama clients) through the Discord liaison daemon:

1. **Set Base URL / API Endpoint**: Point your client's OpenAI API base URL to:
   ```
   http://localhost:18000/v1
   ```
2. **API Key**: Any string (or your Gemini API Key if bypassing daemon cache).
3. **Session Tracking (Optional)**: Pass a header `x-conversation-id` or set the request's `"user"` parameter to track conversational logs per session.

When your client makes completions calls (e.g. to `http://localhost:18000/v1/chat/completions`), the prompt and the model response will be mirrored directly to your Discord DM channel in real-time.

---

## ✍️ Authorship & Credits

* **Author**: Logan Kirkendall (<Logan@LKAud.io>) | Website: [LKAud.io](https://LKAud.io)
* **Default Author Contact**: `Logan@LKAud.io`

For installation instructions, configurations, and bot command usage guides, consult the sub-module files or run the unified launcher `install.py`.

