# Discord Liaison Bot

A centralized, interactive Discord bot and API daemon designed to act as an approval liaison, dashboard monitor, and message routing hub for Google Antigravity SDK agents. 

This repository consolidates the bot backend code into a single, unified codebase at the root level, serving both Antigravity-IDE and Antigravity 2 clients.

---

## 🎯 Long-Term Goal
A standalone Discord bot that can act as a liaison to AI models requesting permissions or requiring user input, serving that data from Discord DM chats & servers. Compatible with Antigravity-IDE and Antigravity 2, but aiming to be an agent compatible with any model that acts as a user message delivery and translation layer. Aiming for Odysseus support soon.

---

## 📂 Repository Structure

- `/src` (Source): Contains the consolidated daemon backend Python modules:
  - `bot.py`: Core Discord bot loop and message dispatch logic.
  - `web_server.py`: FastAPI server processing `/approve` hooks and serving the status bar web UI.
  - `discord_policy.py`: Safe policy hooks loaded into client agents to delegate tool execution confirmations.
  - `discord_ui.py`: UI views and input modals.
  - `agent_manager.py`: Spawns and manages agent instances.
  - `helpers.py`: Directory scanner, project resolver, and process utilities.
  - `state.py`: Configuration and shared variable states.
- `/tests`: Holds the test suites validating functionality:
  - `test_suite.py`: Master test runner.
  - `test_suite_web.py`, `test_suite_bot.py`, `test_suite_policy.py`: Individual test suites.
- `/` (Root): Configuration, installers, and workspace files:
  - `install_ide.py` / `install_agy2.py`: Installation scripts for IDE and AGY2 plugin versions respectively.
  - `config.json`: Dynamic endpoints and API key configuration settings.
- `/ide`: Specific VS Code extension files (such as compiled `main.js` integrations).
- `/agy2`: Specific Antigravity 2 GUI extension assets and scripts.

---

## 🛠️ Installation & Setup

We provide separate, dedicated installers for each environment:

### 1. Antigravity IDE Extension
To install the Discord bot liaison and register it as an auto-start daemon for the Antigravity IDE:
* **macOS/Linux**:
  ```bash
  ./install_ide.sh
  ```
* **Windows**:
  ```cmd
  install_ide.bat
  ```

### 2. Antigravity 2 (AGY2) Extension
To install the bot liaison registered for the AGY2 client framework:
* **macOS/Linux**:
  ```bash
  ./install_agy2.sh
  ```
* **Windows**:
  ```cmd
  install_agy2.bat
  ```

---

## 🚀 Running in Standalone Mode

The daemon can run as a standalone service, acting as an OpenAI-compatible API translation proxy layer for any IDE, local script, or agent.

1. Install dependencies in your virtual environment:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the daemon:
   ```bash
   python3 src/bot.py
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
- **`model_provider`**: `"gemini" | "ollama" | "claude" | "deepseek" | "groq" | "openrouter" | "together" | "huggingface" | "openai" | "custom"`.
- **`local_endpoint`**: The base URL of your local Ollama instance (default: `http://localhost:11434/v1`).
- **`local_model_name`**: The model Ollama should run (default: `qwen2.5-coder:7b`).
- **`remote_endpoint`**: Optional custom OpenAI-compatible remote endpoint. If left empty when provider is `"gemini"`, defaults to the Google Gemini OpenAI-compatibility API endpoint (`https://generativelanguage.googleapis.com/v1beta/openai`).
- **`remote_api_key`**: Your API key. If left empty, fallback to environment key is used.
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

When your client makes completions calls (e.g. to `http://localhost:18000/v1/chat/completions`), the prompt and the model response will be mirrored directly to your Discord DM channel or `#agent-updates` in real-time.

---

## 💬 Discord Server / Guild Integration

To use the bot inside a Discord server (instead of just DMs):
1. **Invite the Bot**: Ensure the bot is added to your server with permissions to read/write messages, create public threads, and manage messages.
2. **Setup Channels (Optional but Recommended)**:
   - Create a text channel named `#agent-discussion`. The bot will restrict all message processing, command execution, and thread creation to only occur inside this channel (or sub-threads parented by it) when running inside a Discord server.
   - Create a text channel named `#agent-updates`. The bot will automatically detect this channel and route all live agent activity, tool approvals, and logs here instead of spamming your DMs.
   - Create a text channel named `#agent-dashboard`. The bot will maintain and update a single pinned dashboard message here to track all running agent sessions.
3. **Conversational Threads**:
   - Send a prompt in the `#agent-discussion` channel (e.g., `Build a python script`).
   - If you are the registered user (`DISCORD_USER_ID`), the bot will automatically spawn a dedicated thread (e.g., `🤖 session-a1b2c3d4`) and run the agent inside it.
   - Any further replies inside that thread will continue the conversation turn with that specific agent.

---

## ✍️ Authorship & Credits

* **Author**: Logan Kirkendall (<Logan@LKAud.io>) | Website: [LKAud.io](https://LKAud.io)
* **Default Author Contact**: `Logan@LKAud.io`

For installation configurations and bot command usage guides, run the launcher scripts.

