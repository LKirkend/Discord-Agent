import os
import sys
import glob
import time

# Check if running in the IDE version
is_ide_version = "discord-agent/ide" in os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

# Dynamically locate the site-packages inside the .venv of Discord-Agent-IDE
if is_ide_version:
    venv_lib_dir = "/Users/logankirkendall/Documents/antigravity/discord-agent/ide/.venv/lib"
    if os.path.exists(venv_lib_dir):
        for d in glob.glob(os.path.join(venv_lib_dir, "python3.*/site-packages")):
            if d not in sys.path:
                sys.path.insert(0, d)

# Configuration Paths
DEFAULT_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
ENV_PATH = os.getenv("ENV_FILE_PATH", DEFAULT_ENV_PATH)

try:
    from dotenv import load_dotenv
    if os.path.exists(ENV_PATH):
        load_dotenv(ENV_PATH)
except ImportError:
    pass

# Model Settings
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")  # "gemini" or "ollama"
AUTO_SWITCH_LOCAL = os.getenv("AUTO_SWITCH_LOCAL", "False").lower() in ("true", "1", "yes")
DISCORD_BOT_PERMISSIONS = os.getenv("DISCORD_BOT_PERMISSIONS", "8471182706732241")


DEFAULT_BRAIN_DIR = (
    os.path.expanduser("~/.gemini/antigravity-ide/brain")
    if is_ide_version
    else os.path.expanduser("~/.gemini/antigravity/brain")
)
BRAIN_DIR = os.getenv("ANTIGRAVITY_BRAIN_DIR", DEFAULT_BRAIN_DIR)

DEFAULT_REMOVER_DIR = os.path.expanduser("~/Documents/antigravity/OpenFeedbackRemover")
REMOVER_DIR = os.getenv("OPEN_FEEDBACK_REMOVER_DIR", DEFAULT_REMOVER_DIR)

APP_DATA_DIR = (
    os.path.expanduser("~/.gemini/antigravity-ide")
    if is_ide_version
    else os.path.expanduser("~/.gemini/antigravity")
)

# Global variables
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
PORT = int(os.getenv("ANTIGRAVITY_SIDECAR_WEB_PORT", os.getenv("PORT", "18000")))
DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
notified_pending_keys = set()
