# Tasks — Self-Hosted Local Open-Source LLM Setup

- [x] Install Ollama using Homebrew
- [x] Start Ollama daemon background service
- [x] Pull default coding model `qwen2.5-coder:7b`
- [x] Create and execute local model verification script `test_local_llm.py`
- [x] Expose `MODEL_PROVIDER` and `AUTO_SWITCH_LOCAL` settings via FastAPI endpoints in `bot.py`
- [x] Add selection between Ollama and Gemini controls and auto-switch toggles on the Status GUI web page
- [x] Implement fallback logic to local Ollama (`qwen2.5-coder:7b`) in `bot.py` during execution or upon Gemini quota depletion
- [x] Add VS Code right-click context menu option "Open web UI" on the liaison status on the bottom of the IDE
- [x] Add Command Palette commands for Open Web UI, Pause, Resume, Reload, Switch to Local, and Switch to Gemini
- [x] Refactor `bot.py` into proper design pattern handlers to maintain clean architecture (< 1000 lines)
- [x] Add text field on dashboard to display current bot permissions integer
- [x] Train the liaison to feed prompts to agents running instead of trying to execute the prompt itself
- [x] Save settings for UI elements to local (.env)
