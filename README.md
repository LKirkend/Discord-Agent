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

## ✍️ Authorship & Credits

* **Author**: Logan Kirkendall (<Logan@LKAud.io>) | Website: [LKAud.io](https://LKAud.io)
* **Default Author Contact**: `Logan@LKAud.io`

For installation instructions, configurations, and bot command usage guides, consult the sub-module files or run the unified launcher `install.py`.
