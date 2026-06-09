# Implementation Plan — Self-Hosted Local Open-Source LLM Setup

We will set up a local, self-hosted open-source model environment on macOS to act as a free, offline alternative to Claude. We will install Ollama, set up a service daemon, select and pull an optimized open-source model (such as `qwen2.5-coder` or `deepseek-r1`), and expose it via an OpenAI-compatible local API endpoint.

---

## Proposed Plan & Steps

### 1. Install Ollama via Homebrew
Ollama is the standard local inference engine on macOS. We will install it using the available Homebrew environment:
```bash
brew install ollama
```

### 2. Set Up the Ollama Background Service
To ensure the model server runs in the background and starts automatically, we will set up the Homebrew service daemon:
```bash
brew services start ollama
```
We will verify that the server is active by querying the status:
```bash
curl http://localhost:11434/api/tags
```

### 3. Model Recommendation & Pulling
Depending on the machine's hardware specs (RAM/VRAM), we propose pulling one of the following state-of-the-art open-weights models:
*   **Coding & Agentic Workflows (Recommended):** `qwen2.5-coder:7b` (fast, highly optimized for programming tasks) or `qwen2.5-coder:14b` (higher accuracy).
*   **Reasoning & Logic:** `deepseek-r1:8b` or `deepseek-r1:14b` (incorporates chain-of-thought similar to Claude's reasoning mode).

We will pull the model using the Ollama CLI:
```bash
ollama pull qwen2.5-coder:7b
```

### 4. Integration & OpenAI-Compatible API Endpoint
Once running, Ollama exposes an OpenAI-compatible chat completion endpoint at:
`http://localhost:11434/v1/chat/completions`

We will write a verification/test script `test_local_llm.py` in the workspace to test connection, streaming, and correct response generation from the local model.

---

## User Review Required

> [...IMPORTANT]
> **Hardware Capacity Check**: Running a local model requires sufficient RAM/VRAM.
> - **8GB - 16GB Unified Memory**: We recommend `qwen2.5-coder:7b` or `deepseek-r1:8b`.
> - **24GB+ Unified Memory**: You can comfortably run `qwen2.5-coder:14b` or `deepseek-r1:14b`.
> Please let us know if you have a preference for the model size or type before we proceed with downloading!

---

## Open Questions

> [...TIP]
> Do you want the local model integrated with the Discord Bot Sidecar, or is this for general development work?

---

## Verification Plan

### Automated/Local Tests
- Run `test_local_llm.py` using Python to verify the local inference engine replies correctly.
- Query Ollama API directly using `curl` to ensure it is healthy and responsive.
