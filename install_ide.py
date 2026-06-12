"""
File: install_ide.py
Description:
    Self-contained setup and installation wizard for the Discord Liaison Bot (IDE) plugin.
    Deploys Python dependencies, structures config files, sets up sidecars,
    and registers launchd launch agents for auto-startup.
Author: Logan Kirkendall <Logan@LKAud.io>
"""

import os
import sys
import shutil
import json
import subprocess
import threading
import webbrowser
import platform

# Configuration Constants for IDE Version
PLUGIN_NAME = "discord-liaison-ide"
DISPLAY_NAME = "Discord Liaison Bot (IDE)"
DEFAULT_PORT = "18000"
PLIST_LABEL = "com.antigravity.discord-liaison-ide"

GUI_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    from tkinter.scrolledtext import ScrolledText
    # Verify display is available
    root = tk.Tk()
    root.destroy()
    GUI_AVAILABLE = True
except Exception:
    GUI_AVAILABLE = False


# The raw text templates for metadata files
PLUGIN_JSON_TEMPLATE = {
  "name": PLUGIN_NAME,
  "version": "1.0.0",
  "description": "Discord Liaison Bot integration for remote approvals, DMs, and agent dashboards in Antigravity IDE",
  "author": {
    "name": "Logan Kirkendall"
  },
  "license": "Apache-2.0",
  "keywords": [
    "discord",
    "liaison",
    "approval",
    "dashboard",
    "agent"
  ]
}

SKILL_MD_TEMPLATE = """---
name: discord-liaison-ide
description: "Manage approvals, notifications, dashboards, and conversational DMs for Google Antigravity agents using a Discord bot liaison, configured for Antigravity IDE. Use this skill when the user wants to monitor agent sessions, run background agent tasks, or approve shell commands/file edits remotely via Discord buttons."
---

# Discord Liaison Skill (IDE version)

This skill integrates a Discord bot into the Google Antigravity SDK to manage remote command approvals and task dashboards for Antigravity IDE.

## Architecture

- **Daemon (`bot.py`)**: Runs a concurrent Discord bot client and FastAPI local web server. Handles background process tracking, live dashboards, and routes messages/approvals.
- **Client Policy (`discord_policy.py`)**: Contains safety policy hooks that intercept agent tool calls and send them to the Discord bot daemon for approval.

## Setup Instructions

### 1. Requirements & Dependencies
Ensure the packages in `scripts/requirements.txt` are installed in the workspace's virtual environment:
```bash
pip install discord.py fastapi uvicorn psutil python-dotenv
```

### 2. Configure Credentials
Add the bot credentials, server channel, and user IDs to the `.env` file in the daemon scripts folder:
- `DISCORD_BOT_TOKEN`
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DISCORD_USER_ID` (your Discord user ID for pings)
- `DISCORD_USER_NAME` (your username for auto-registration)
- `PORT` (defaults to `18000`)
- `GEMINI_API_KEY` (required if running the persistent agent daemon)

### 3. Sourcing the Policy in Client Code
Import the Discord policies and load them into any local agent configuration:

```python
from google.antigravity import Agent, LocalAgentConfig
from discord_policy import get_discord_policies

config = LocalAgentConfig(
    policies=get_discord_policies()
)

async with Agent(config) as agent:
    # Any write action executed inside this block will prompt you on Discord
    pass
```

### 4. Running the Bot Daemon
Launch the daemon script in the background:
```bash
python3 scripts/bot.py
```
Once connected, the bot will post a live dashboard in your Discord DMs where you can monitor tasks, terminate processes, and chat directly with active agent sessions.
"""


PLIST_DEST = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")


def launchd_register(python_exe: str, bot_script: str, scripts_dir: str, log_callback) -> bool:
    """
    Description:
        Install and load the macOS LaunchAgent for auto-launch on login.
        No-op on non-macOS systems.
    Usage:
        launchd_register(python_exe, bot_script, scripts_dir, log_callback)
    Usage Example:
        launchd_register("/usr/bin/python3", "bot.py", "/path/to/scripts", print)
    """
    if platform.system() != "Darwin":
        log_callback("⚠️  LaunchAgent registration skipped (not macOS).")
        return True
    try:
        log_callback("🚀 Registering LaunchAgent for auto-launch on login...")
        log_dir = os.path.expanduser("~/.gemini/antigravity-ide/logs")
        os.makedirs(log_dir, exist_ok=True)
        launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
        os.makedirs(launch_agents_dir, exist_ok=True)

        # Build the plist content programmatically so paths are always current
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>-u</string>
        <string>{bot_script}</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>StandardOutPath</key>
    <string>{log_dir}/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/daemon.err.log</string>
    <key>WorkingDirectory</key>
    <string>{scripts_dir}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
        <key>HOME</key>
        <string>{os.path.expanduser('~')}</string>
    </dict>
</dict>
</plist>
"""
        with open(PLIST_DEST, "w") as pf:
            pf.write(plist_content)

        # Unload any conflicting launch agent from the other version
        other_plist_dest = os.path.expanduser("~/Library/LaunchAgents/com.antigravity.discord-liaison.plist")
        if os.path.exists(other_plist_dest):
            log_callback("🧹 Found conflicting Discord Liaison Bot (AGY2) launch agent. Unloading and removing it...")
            subprocess.run(["launchctl", "unload", "-w", other_plist_dest], capture_output=True)
            try:
                os.remove(other_plist_dest)
            except Exception as e:
                log_callback(f"⚠️ Warning: Could not remove old plist file: {e}")

        # Unload any stale entry first, then load the fresh one
        subprocess.run(["launchctl", "unload", PLIST_DEST], capture_output=True)
        result = subprocess.run(["launchctl", "load", "-w", PLIST_DEST], capture_output=True, text=True)
        if result.returncode != 0 and result.stderr:
            log_callback(f"⚠️  launchctl load warning: {result.stderr.strip()}")
        else:
            log_callback(f"✅ LaunchAgent registered: {PLIST_DEST}")
        return True
    except Exception as e:
        log_callback(f"❌ Failed to register LaunchAgent: {e}")
        return False


def launchd_unregister(log_callback=print) -> bool:
    """
    Description:
        Unload and remove the macOS LaunchAgent. No-op on non-macOS.
    Usage:
        launchd_unregister(log_callback)
    Usage Example:
        launchd_unregister(print)
    """
    if platform.system() != "Darwin":
        return True
    try:
        if os.path.exists(PLIST_DEST):
            subprocess.run(["launchctl", "unload", "-w", PLIST_DEST], capture_output=True)
            os.remove(PLIST_DEST)
            log_callback(f"✅ LaunchAgent unregistered and removed: {PLIST_DEST}")
        else:
            log_callback("⚠️  No LaunchAgent plist found to remove.")
        return True
    except Exception as e:
        log_callback(f"❌ Failed to unregister LaunchAgent: {e}")
        return False


def perform_installation(token, user_id, username, client_id, client_secret, gemini_key, port, log_callback):
    """
    Description:
        Executes the setup process step-by-step.
    Usage:
        perform_installation(token, user_id, username, client_id, client_secret, gemini_key, port, log_callback)
    Usage Example:
        perform_installation("token", "user_id", "Tig1", "", "", "", "18000", print)
    """
    try:
        log_callback("🚀 Starting installation wizard...")
        
        gemini_dir = os.path.expanduser("~/.gemini")
        plugin_dir = os.path.join(gemini_dir, "config", "plugins", PLUGIN_NAME)
        scripts_dir = os.path.join(plugin_dir, "skills", PLUGIN_NAME, "scripts")
        sidecars_dir = os.path.join(gemini_dir, "config", "sidecars")
        sidecar_json_path = os.path.join(sidecars_dir, f"{PLUGIN_NAME}.json")
        
        source_dir = os.path.dirname(os.path.abspath(__file__))
        
        log_callback(f"📂 Creating plugin directory: {plugin_dir}")
        os.makedirs(scripts_dir, exist_ok=True)
        os.makedirs(sidecars_dir, exist_ok=True)
        
        # Define files/directories to copy
        items_to_copy = [
            ("src", "src"),
            ("tests", "tests"),
            ("requirements.txt", "requirements.txt"),
            ("config.json", "config.json")
        ]
        for src_rel, dest_rel in items_to_copy:
            src = os.path.join(source_dir, src_rel)
            dest = os.path.join(scripts_dir, dest_rel)
            if os.path.exists(src):
                if os.path.isdir(src):
                    log_callback(f"📋 Copying directory {src_rel}...")
                    if os.path.exists(dest):
                        shutil.rmtree(dest)
                    shutil.copytree(src, dest)
                else:
                    log_callback(f"📋 Copying file {src_rel}...")
                    shutil.copy2(src, dest)
            else:
                log_callback(f"⚠️ Warning: Source not found: {src_rel}")
                
        # Generate plugin.json
        log_callback("📝 Generating plugin.json...")
        with open(os.path.join(plugin_dir, "plugin.json"), "w") as f_out:
            json.dump(PLUGIN_JSON_TEMPLATE, f_out, indent=2)
            
        # Generate SKILL.md
        log_callback("📝 Generating SKILL.md...")
        skill_dir = os.path.join(plugin_dir, "skills", PLUGIN_NAME)
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f_out:
            f_out.write(SKILL_MD_TEMPLATE)
            
        # Write .env file
        log_callback("🔐 Writing credentials config (.env)...")
        env_path = os.path.join(scripts_dir, ".env")
        with open(env_path, "w") as f_out:
            f_out.write(f"DISCORD_BOT_TOKEN={token}\n")
            f_out.write(f"DISCORD_USER_ID={user_id}\n")
            f_out.write(f"DISCORD_USER_NAME={username}\n")
            if client_id:
                f_out.write(f"DISCORD_CLIENT_ID={client_id}\n")
            if client_secret:
                f_out.write(f"DISCORD_CLIENT_SECRET={client_secret}\n")
            if gemini_key:
                f_out.write(f"GEMINI_API_KEY={gemini_key}\n")
            if port:
                f_out.write(f"PORT={port}\n")
                
        # Setup Python Virtual Environment
        log_callback("🐍 Provisioning virtual environment (.venv) inside plugin folder...")
        venv_path = os.path.join(scripts_dir, ".venv")
        subprocess.run([sys.executable, "-m", "venv", venv_path], cwd=scripts_dir, check=True)
        
        # Determine path to venv python executable
        is_windows = os.name == "nt"
        if is_windows:
            python_exe = os.path.join(venv_path, "Scripts", "python.exe")
        else:
            python_exe = os.path.join(venv_path, "bin", "python")
            
        if not os.path.exists(python_exe):
            # Fallback check
            alt_python = os.path.join(venv_path, "bin", "python3")
            if os.path.exists(alt_python):
                python_exe = alt_python
                
        log_callback("📦 Installing Python dependencies via pip...")
        subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], cwd=scripts_dir, check=True)
        subprocess.run([python_exe, "-m", "pip", "install", "-r", "requirements.txt"], cwd=scripts_dir, check=True)
        
        # Generate sidecar.json
        log_callback("⚙️ Registering sidecar configuration...")
        sidecar_config = {
            "display_name": DISPLAY_NAME,
            "description": f"Discord Liaison Bot for remote approvals, DMs, and agent dashboards in {DISPLAY_NAME}.",
            "command": os.path.abspath(python_exe),
            "args": [
                "-u",
                os.path.abspath(os.path.join(scripts_dir, "src", "bot.py"))
            ],
            "restart_policy": "always",
            "has_web_ui": True,
            "ui_config": {
                "display_name": "Discord Liaison",
                "views": [
                    { "entrypoint": 2, "path": "/status" },
                    { "entrypoint": 1, "path": "/status" }
                ]
            }
        }
        
        with open(sidecar_json_path, "w") as f_out:
            json.dump(sidecar_config, f_out, indent=2)
            
        log_callback("🎉 Installation completed successfully!")

        # Register LaunchAgent for auto-launch on macOS login
        launchd_register(
            python_exe=os.path.abspath(python_exe),
            bot_script=os.path.abspath(os.path.join(scripts_dir, "src", "bot.py")),
            scripts_dir=scripts_dir,
            log_callback=log_callback
        )
        return True
    except Exception as e:
        log_callback(f"❌ Installation failed: {e}")
        return False


class InstallerGUI:
    """
    Description:
        Graphical User Interface Class for the installer script.
        Builds a Sleek Dark mode theme using Tkinter and handles inputs.
    """
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{DISPLAY_NAME} Setup wizard")
        self.root.geometry("640x720")
        self.root.resizable(False, False)
        
        # Premium Sleeek Dark Theme colors (Harmonious Palette)
        self.bg_color = "#1e1e2e"
        self.fg_color = "#cdd6f4"
        self.frame_color = "#313244"
        self.entry_bg = "#45475a"
        self.btn_bg = "#89b4fa"
        self.btn_fg = "#11111b"
        
        self.root.configure(bg=self.bg_color)
        
        # Style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TProgressbar", thickness=15, troughcolor=self.frame_color, background=self.btn_bg)
        
        self.build_ui()
        
    def build_ui(self):
        # Header title
        header_frame = tk.Frame(self.root, bg=self.bg_color)
        header_frame.pack(fill="x", padx=25, pady=20)
        
        title_lbl = tk.Label(
            header_frame, 
            text=DISPLAY_NAME, 
            fg=self.btn_bg, 
            bg=self.bg_color, 
            font=("Inter", 18, "bold")
        )
        title_lbl.pack(anchor="w")
        
        desc_lbl = tk.Label(
            header_frame, 
            text="Provide your Discord configurations to globally install the liaison bot.", 
            fg="#a6adc8", 
            bg=self.bg_color, 
            font=("Inter", 11)
        )
        desc_lbl.pack(anchor="w", pady=4)
        
        # Fields Container
        fields_frame = tk.LabelFrame(
            self.root, 
            text=" ⚙️ Settings ", 
            fg=self.btn_bg, 
            bg=self.frame_color, 
            bd=1, 
            font=("Inter", 12, "bold")
        )
        fields_frame.pack(fill="both", padx=25, pady=5, expand=True)
        
        # Grid helpers
        def make_entry(parent, label_text, row, show=None, default="", link_text=None, link_url=None):
            lbl = tk.Label(parent, text=label_text, fg=self.fg_color, bg=self.frame_color, font=("Inter", 10))
            lbl.grid(row=row, column=0, padx=15, pady=8, sticky="nw")
            
            # Container frame for vertical stack of entry field and hyperlink
            col_frame = tk.Frame(parent, bg=self.frame_color)
            col_frame.grid(row=row, column=1, padx=15, pady=8, sticky="ew")
            
            entry = tk.Entry(
                col_frame, 
                show=show, 
                bg=self.entry_bg, 
                fg=self.fg_color, 
                insertbackground=self.fg_color, 
                bd=0, 
                font=("Inter", 10)
            )
            entry.pack(fill="x", expand=True)
            entry.insert(0, default)
            
            if link_text and link_url:
                link_lbl = tk.Label(
                    col_frame,
                    text=link_text,
                    fg=self.btn_bg,
                    bg=self.frame_color,
                    font=("Inter", 9, "underline"),
                    cursor="hand2"
                )
                link_lbl.pack(anchor="w", pady=(2, 0))
                link_lbl.bind("<Button-1>", lambda e: webbrowser.open_new_tab(link_url))
                
            return entry
            
        fields_frame.columnconfigure(1, weight=1)
        
        self.token_ent = make_entry(
            fields_frame, 
            "Discord Bot Token *", 
            0, 
            show="*", 
            link_text="Acquire Token: discord.com/developers/applications", 
            link_url="https://discord.com/developers/applications"
        )
        self.user_id_ent = make_entry(fields_frame, "Discord User ID *", 1)
        self.username_ent = make_entry(fields_frame, "Discord Username", 2, default="Tig1")
        self.client_id_ent = make_entry(fields_frame, "Discord Client ID (Opt)", 3)
        self.client_secret_ent = make_entry(fields_frame, "Discord Client Secret (Opt)", 4, show="*")
        self.gemini_key_ent = make_entry(
            fields_frame, 
            "Gemini API Key (Opt)", 
            5, 
            show="*", 
            link_text="Acquire Key: aistudio.google.com/app/apikey", 
            link_url="https://aistudio.google.com/app/apikey"
        )
        self.port_ent = make_entry(fields_frame, "Liaison Web Port", 6, default=DEFAULT_PORT)
        
        # Progress & Log console
        console_frame = tk.Frame(self.root, bg=self.bg_color)
        console_frame.pack(fill="x", padx=25, pady=10)
        
        self.progress_bar = ttk.Progressbar(console_frame, style="TProgressbar", mode="determinate")
        self.progress_bar.pack(fill="x", pady=5)
        
        self.console_txt = ScrolledText(
            console_frame, 
            height=8, 
            bg=self.frame_color, 
            fg="#a6e3a1", 
            insertbackground=self.fg_color,
            font=("Consolas", 9),
            bd=0
        )
        self.console_txt.pack(fill="x")
        self.console_txt.insert(tk.END, "Ready to start setup. Fill required fields (*) and click Install.\n")
        self.console_txt.configure(state="disabled")
        
        # Buttons
        btn_frame = tk.Frame(self.root, bg=self.bg_color)
        btn_frame.pack(fill="x", padx=25, pady=15)
        
        self.cancel_btn = tk.Button(
            btn_frame, 
            text="Cancel", 
            command=self.root.quit, 
            bg="#f38ba8", 
            fg=self.btn_fg, 
            activebackground="#eba0b2", 
            bd=0, 
            width=10, 
            font=("Inter", 10, "bold")
        )
        self.cancel_btn.pack(side="left")
        
        self.install_btn = tk.Button(
            btn_frame, 
            text="Install 🚀", 
            command=self.start_install_thread, 
            bg=self.btn_bg, 
            fg=self.btn_fg, 
            activebackground="#b4befe", 
            bd=0, 
            width=15, 
            font=("Inter", 10, "bold")
        )
        self.install_btn.pack(side="right")
        
    def write_log(self, text):
        self.console_txt.configure(state="normal")
        self.console_txt.insert(tk.END, text + "\n")
        self.console_txt.see(tk.END)
        self.console_txt.configure(state="disabled")
        
    def start_install_thread(self):
        token = self.token_ent.get().strip()
        user_id = self.user_id_ent.get().strip()
        username = self.username_ent.get().strip()
        client_id = self.client_id_ent.get().strip()
        client_secret = self.client_secret_ent.get().strip()
        gemini_key = self.gemini_key_ent.get().strip()
        port = self.port_ent.get().strip()
        
        if not token or not user_id:
            messagebox.showerror("Error", "Discord Bot Token and Discord User ID are required fields.")
            return
            
        self.install_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(10)
        
        t = threading.Thread(target=self.run_install_bg, args=(token, user_id, username, client_id, client_secret, gemini_key, port))
        t.daemon = True
        t.start()
        
    def run_install_bg(self, token, user_id, username, client_id, client_secret, gemini_key, port):
        success = perform_installation(
            token, user_id, username, client_id, client_secret, gemini_key, port, self.write_log
        )
        self.root.after(0, self.finish_installation, success)
        
    def finish_installation(self, success):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", value=100)
        self.install_btn.configure(state="normal")
        self.cancel_btn.configure(state="normal")
        
        if success:
            messagebox.showinfo("Success", f"{DISPLAY_NAME} has been successfully installed and registered!")
            self.root.quit()
        else:
            messagebox.showerror("Failed", "Installation encountered errors. Please check the console output log.")


def run_cli_installer():
    """
    Description:
        Terminal fallback wizard when Tkinter is not available.
    Usage:
        run_cli_installer()
    Usage Example:
        run_cli_installer()
    """
    print("==================================================")
    print(f"       {DISPLAY_NAME} CLI SETUP")
    print("==================================================")
    print("Acquire Discord Bot Token at: https://discord.com/developers/applications\n")
    
    token = input("Discord Bot Token *: ").strip()
    while not token:
        token = input("Discord Bot Token * (Required): ").strip()
        
    user_id = input("Discord User ID *: ").strip()
    while not user_id:
        user_id = input("Discord User ID * (Required): ").strip()
        
    username = input("Discord Username [Tig1]: ").strip() or "Tig1"
    client_id = input("Discord Client ID (Optional): ").strip()
    client_secret = input("Discord Client Secret (Optional): ").strip()
    
    print("\nAcquire Gemini API Key at: https://aistudio.google.com/app/apikey\n")
    gemini_key = input("Gemini API Key (Optional): ").strip()
    port = input(f"Liaison Web Port [{DEFAULT_PORT}]: ").strip() or DEFAULT_PORT
    
    print("\nStarting installation...")
    success = perform_installation(
        token, user_id, username, client_id, client_secret, gemini_key, port, print
    )
    if success:
        print("\n🎉 Setup completed successfully!")
    else:
        print("\n❌ Setup failed. Check output errors above.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        run_cli_installer()
    elif GUI_AVAILABLE:
        app = InstallerGUI()
        app.root.mainloop()
    else:
        print("Tkinter GUI not available. Falling back to CLI mode...")
        run_cli_installer()
