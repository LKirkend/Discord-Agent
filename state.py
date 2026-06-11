"""
File: state.py
Description:
    Manages global configuration, paths, and shared runtime states for the
    Antigravity Discord Liaison Bot. Loads configuration from config.json,
    overrides with .env variables, and exposes state variables dynamically.
Author: Logan Kirkendall <Logan@LKAud.io>
"""

import os
import sys
import glob
import time
import json

# Dynamically locate the site-packages inside the local .venv of the root workspace
venv_lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv/lib")
if os.path.exists(venv_lib_dir):
    for d in glob.glob(os.path.join(venv_lib_dir, "python3.*/site-packages")):
        if d not in sys.path:
            sys.path.insert(0, d)

# Configuration Paths
DEFAULT_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
ENV_PATH = os.getenv("ENV_FILE_PATH", DEFAULT_ENV_PATH)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
CONFIG_PATH = os.getenv("CONFIG_FILE_PATH", DEFAULT_CONFIG_PATH)

# Load config.json if present
config_data = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r") as f:
            config_data = json.load(f)
    except Exception as e:
        print(f"Error loading config.json: {e}")

# Load .env environment variables
try:
    from dotenv import load_dotenv
    if os.path.exists(ENV_PATH):
        load_dotenv(ENV_PATH)
except ImportError:
    pass

# Model & Core Configuration Loader
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", config_data.get("model_provider", "gemini"))
AGENT_PROVIDER = os.getenv("AGENT_PROVIDER", config_data.get("agent_provider", "ollama"))

raw_auto_switch = os.getenv("AUTO_SWITCH_LOCAL")
if raw_auto_switch is not None:
    AUTO_SWITCH_LOCAL = raw_auto_switch.lower() in ("true", "1", "yes")
else:
    AUTO_SWITCH_LOCAL = config_data.get("auto_switch_local", False)

raw_force_server_chat = os.getenv("FORCE_SERVER_CHAT") or os.getenv("FORCE_ONLY_SERVER")
if raw_force_server_chat is not None:
    FORCE_SERVER_CHAT = raw_force_server_chat.lower() in ("true", "1", "yes")
else:
    val = config_data.get("force_server_chat", config_data.get("force_only_server", 0))
    if isinstance(val, str):
        FORCE_SERVER_CHAT = val.lower() in ("true", "1", "yes")
    else:
        FORCE_SERVER_CHAT = bool(val)

DISCORD_BOT_PERMISSIONS = os.getenv("DISCORD_BOT_PERMISSIONS", config_data.get("discord_bot_permissions", "8471182706732241"))

# Local & Remote Endpoint Configurations (Renamed to Agent & Forward Endpoints)
AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT", os.getenv("LOCAL_ENDPOINT", config_data.get("agent_endpoint", config_data.get("local_endpoint", "http://localhost:11434/v1"))))
AGENT_MODEL_NAME = os.getenv("AGENT_MODEL_NAME", os.getenv("LOCAL_MODEL_NAME", config_data.get("agent_model_name", config_data.get("local_model_name", "qwen2.5-coder:7b"))))
FORWARD_ENDPOINT = os.getenv("FORWARD_ENDPOINT", os.getenv("REMOTE_ENDPOINT", config_data.get("forward_endpoint", config_data.get("remote_endpoint", ""))))
FORWARD_API_KEY = os.getenv("FORWARD_API_KEY", os.getenv("REMOTE_API_KEY", config_data.get("forward_api_key", config_data.get("remote_api_key", ""))))
AGENT_API_KEY = os.getenv("AGENT_API_KEY", config_data.get("agent_api_key", ""))

# Provider Specific Configurations
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", config_data.get("claude_api_key", ""))
CLAUDE_MODEL_NAME = os.getenv("CLAUDE_MODEL_NAME", config_data.get("claude_model_name", "claude-3-5-sonnet-latest"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", config_data.get("deepseek_api_key", ""))
DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", config_data.get("deepseek_model_name", "deepseek-chat"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", config_data.get("groq_api_key", ""))
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", config_data.get("groq_model_name", "llama3-8b-8192"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", config_data.get("openrouter_api_key", ""))
OPENROUTER_MODEL_NAME = os.getenv("OPENROUTER_MODEL_NAME", config_data.get("openrouter_model_name", "meta-llama/llama-3-8b-instruct:free"))

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", config_data.get("together_api_key", ""))
TOGETHER_MODEL_NAME = os.getenv("TOGETHER_MODEL_NAME", config_data.get("together_model_name", "meta-llama/Llama-3-8b-chat-hf"))

HF_API_KEY = os.getenv("HF_API_KEY", config_data.get("hf_api_key", ""))
HF_MODEL_NAME = os.getenv("HF_MODEL_NAME", config_data.get("hf_model_name", "meta-llama/Meta-Llama-3-8B-Instruct"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", config_data.get("openai_api_key", ""))
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", config_data.get("openai_model_name", "gpt-4o"))

CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", config_data.get("custom_api_key", ""))
CUSTOM_MODEL_NAME = os.getenv("CUSTOM_MODEL_NAME", config_data.get("custom_model_name", ""))
CUSTOM_ENDPOINT = os.getenv("CUSTOM_ENDPOINT", config_data.get("custom_endpoint", ""))

# App and Brain directory resolution
DEFAULT_BRAIN_DIR = os.path.expanduser("~/.gemini/antigravity-ide/brain")
if not os.path.exists(DEFAULT_BRAIN_DIR):
    DEFAULT_BRAIN_DIR = os.path.expanduser("~/.gemini/antigravity/brain")
BRAIN_DIR = os.getenv("ANTIGRAVITY_BRAIN_DIR", DEFAULT_BRAIN_DIR)

is_ide_version = "antigravity-ide" in BRAIN_DIR

DEFAULT_REMOVER_DIR = os.path.expanduser("~/Documents/antigravity/OpenFeedbackRemover")
REMOVER_DIR = os.getenv("OPEN_FEEDBACK_REMOVER_DIR", DEFAULT_REMOVER_DIR)

APP_DATA_DIR = os.path.expanduser("~/.gemini/antigravity-ide") if is_ide_version else os.path.expanduser("~/.gemini/antigravity")

# Global shared bot and interaction states
pending_approvals = {}
pending_interactions = {}
active_text_prompts = {}  # user_id -> future
active_pending_items = {}
bot = None
START_TIME = time.time()
has_message_content = True
dashboard_msg = None
dashboard_state = {"view": "main", "project": None}
IS_PAUSED = False

raw_port = os.getenv("ANTIGRAVITY_SIDECAR_WEB_PORT", os.getenv("PORT"))
if raw_port is not None:
    PORT = int(raw_port)
else:
    PORT = int(config_data.get("port", 18000))

DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
notified_pending_keys = set()

