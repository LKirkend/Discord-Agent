import os
import time
import uuid
import json
import datetime
import asyncio
from typing import Dict, Optional, List, Tuple
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import discord
import httpx

import state
import helpers

def discover_agent_sessions(*args, **kwargs):
    """
    Description:
        Wrapper to dynamically delegate to bot.discover_agent_sessions.
    Usage:
        sessions = discover_agent_sessions()
    Usage Example:
        sessions = discover_agent_sessions()
    """
    import bot
    return bot.discover_agent_sessions(*args, **kwargs)

def get_session_project(*args, **kwargs):
    """
    Description:
        Wrapper to dynamically delegate to bot.get_session_project.
    Usage:
        proj = get_session_project(convo_id)
    Usage Example:
        proj = get_session_project("convo123")
    """
    import bot
    return bot.get_session_project(*args, **kwargs)

def get_all_pending_items(*args, **kwargs):
    """
    Description:
        Wrapper to dynamically delegate to bot.get_all_pending_items.
    Usage:
        plans, apps, ints = get_all_pending_items()
    Usage Example:
        plans, apps, ints = get_all_pending_items()
    """
    import bot
    return bot.get_all_pending_items(*args, **kwargs)

def is_session_awaiting_approval(*args, **kwargs):
    """
    Description:
        Wrapper to dynamically delegate to bot.is_session_awaiting_approval.
    Usage:
        res = is_session_awaiting_approval(convo_id, p, a, i)
    Usage Example:
        res = is_session_awaiting_approval("convo123", [], [], [])
    """
    import bot
    return bot.is_session_awaiting_approval(*args, **kwargs)

def extract_and_prepare_files(*args, **kwargs):
    """
    Description:
        Wrapper to dynamically delegate to bot.extract_and_prepare_files.
    Usage:
        txt, files = extract_and_prepare_files(txt, seen)
    Usage Example:
        txt, files = extract_and_prepare_files("hello", set())
    """
    import bot
    return bot.extract_and_prepare_files(*args, **kwargs)

def extract_and_prepare_embed_files(*args, **kwargs):
    """
    Description:
        Wrapper to dynamically delegate to bot.extract_and_prepare_embed_files.
    Usage:
        emb, files = extract_and_prepare_embed_files(emb, seen)
    Usage Example:
        emb, files = extract_and_prepare_embed_files(my_emb, set())
    """
    import bot
    return bot.extract_and_prepare_embed_files(*args, **kwargs)

def extract_files_from_dict_or_list(*args, **kwargs):
    """
    Description:
        Wrapper to dynamically delegate to bot.extract_files_from_dict_or_list.
    Usage:
        files = extract_files_from_dict_or_list(data, seen)
    Usage Example:
        files = extract_files_from_dict_or_list({"path": "file.txt"}, set())
    """
    import bot
    return bot.extract_files_from_dict_or_list(*args, **kwargs)
from discord_ui import DiscordApprovalView, DiscordInteractionView, DiscordFreeformInteractionView

app = FastAPI(title="Antigravity Discord Approval Server")

class ApprovalRequest(BaseModel):
    request_id: Optional[str] = None
    agent_name: str
    conversation_id: str
    tool_name: str
    arguments: dict
    ls_address: Optional[str] = None
    ls_token: Optional[str] = None

class ApprovalResponse(BaseModel):
    approved: bool
    reason: Optional[str] = None

class MessageRequest(BaseModel):
    content: str
    embed_title: Optional[str] = None
    embed_description: Optional[str] = None

class InteractionRequest(BaseModel):
    request_id: Optional[str] = None
    agent_name: str
    conversation_id: str
    questions: List[dict]

class InteractionResponse(BaseModel):
    responses: List[dict]
    cancelled: bool

class SettingsRequest(BaseModel):
    model_provider: str
    auto_switch_local: bool
    discord_bot_permissions: str

def is_dangerous_command(command: str) -> bool:
    """
    Description:
        Checks if a command contains dangerous destructive patterns like rm, kill, etc.
    Usage:
        danger = is_dangerous_command(command)
    Usage Example:
        danger = is_dangerous_command("rm -rf /")
    """
    cmd_lower = command.lower()
    dangerous_words = ['rm', 'rmdir', 'kill', 'dd', 'mkfs', 'format']
    for word in dangerous_words:
        if re.search(rf'\b{word}\b', cmd_lower) or re.search(rf'\b{word}\s', cmd_lower):
            return True
    return False

import re

def save_persistent_permission(scope: str, tool_name: str, arguments: dict):
    """
    Description:
        Saves a tool permission rule persistently to the workspace or global permissions JSON file.
    Usage:
        save_persistent_permission(scope, tool_name, arguments)
    Usage Example:
        save_persistent_permission("global", "run_command", {"CommandLine": "ls"})
    """
    if scope == "project":
        perms_path = os.path.join(os.getcwd(), ".antigravity_permissions.json")
    else:
        perms_path = os.path.join(state.APP_DATA_DIR, "permissions.json")
        
    os.makedirs(os.path.dirname(perms_path), exist_ok=True)
    
    perms = {}
    if os.path.exists(perms_path):
        try:
            with open(perms_path, "r") as f:
                perms = json.load(f)
        except Exception as e:
            print(f"Error loading perms: {e}")
            
    if tool_name not in perms:
        perms[tool_name] = []
        
    rule = None
    if tool_name == "run_command":
        rule = arguments.get("CommandLine", "")
    elif tool_name in ["write_to_file", "replace_file_content", "multi_replace_file_content", "create_file", "edit_file"]:
        target_file = arguments.get("TargetFile", "") or arguments.get("AbsolutePath", "")
        if target_file:
            rule = os.path.dirname(os.path.abspath(target_file))
    else:
        rule = "*"
        
    if rule and rule not in perms[tool_name]:
        perms[tool_name].append(rule)
        try:
            with open(perms_path, "w") as f:
                json.dump(perms, f, indent=2)
            print(f"Saved persistent permission ({scope}): {tool_name} -> {rule}")
        except Exception as e:
            print(f"Error saving perms: {e}")

async def poll_ls_for_approval(ls_address: str, ls_token: str, convo_id: str, tool_name: str, arguments: dict, fut: asyncio.Future):
    """
    Description:
        Wrapper to dynamically call mock or real poll_ls_for_approval.
    Usage:
        await poll_ls_for_approval(ls_address, ls_token, convo_id, tool_name, arguments, fut)
    Usage Example:
        await poll_ls_for_approval("127.0.0.1", "tok", "convo", "run_command", {}, fut)
    """
    import bot
    if hasattr(bot, 'poll_ls_for_approval') and bot.poll_ls_for_approval is not poll_ls_for_approval:
        res = bot.poll_ls_for_approval(ls_address, ls_token, convo_id, tool_name, arguments, fut)
        if asyncio.iscoroutine(res):
            return await res
        return res
    else:
        return await _real_poll_ls_for_approval(ls_address, ls_token, convo_id, tool_name, arguments, fut)

async def _real_poll_ls_for_approval(ls_address: str, ls_token: str, convo_id: str, tool_name: str, arguments: dict, fut: asyncio.Future):
    """
    Description:
        Polls the Language Server to find if the user has approved the action in the IDE.
    Usage:
        await _real_poll_ls_for_approval(ls_address, ls_token, convo_id, tool_name, arguments, fut)
    Usage Example:
        await _real_poll_ls_for_approval("127.0.0.1:65081", "token", "convo_id", "run_command", {}, fut)
    """
    import httpx
    url = f"http://{ls_address}/exa.language_server_pb.LanguageServerService/GetCascadeTrajectory"
    headers = {
        "Content-Type": "application/json",
        "x-codeium-csrf-token": ls_token,
    }
    payload = {
        "cascade_id": convo_id,
        "trajectory_verbosity": 2
    }
    
    while not fut.done():
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    traj = data.get("trajectory", {})
                    steps = traj.get("steps", [])
                    
                    for step in reversed(steps):
                        step_type = step.get("type", "")
                        cleaned_type = step_type.replace("CORTEX_STEP_TYPE_", "").lower().replace("_", "")
                        cleaned_tool = tool_name.lower().replace("_", "")
                        
                        type_matches = False
                        if cleaned_type == cleaned_tool:
                            type_matches = True
                        elif cleaned_tool == "replacefilecontent" and (cleaned_type == "editfile" or cleaned_type == "codeaction"):
                            type_matches = True
                        elif cleaned_tool == "multireplacefilecontent" and (cleaned_type == "editfile" or cleaned_type == "codeaction"):
                            type_matches = True
                        elif cleaned_tool == "writetofile" and (cleaned_type == "createfile" or cleaned_type == "codeaction"):
                            type_matches = True
                        
                        if type_matches:
                            args_match = False
                            if tool_name == "run_command":
                                cmd = arguments.get("CommandLine", "")
                                step_cmd = step.get("runCommand", {}).get("commandLine", "")
                                if cmd.strip() == step_cmd.strip():
                                    args_match = True
                            elif tool_name in ["replace_file_content", "multi_replace_file_content", "edit_file"]:
                                target_file = arguments.get("TargetFile", "")
                                step_file = step.get("editFile", {}).get("filePath", "")
                                if not step_file:
                                    step_file = step.get("codeAction", {}).get("actionSpec", {}).get("command", {}).get("file", {}).get("absoluteUri", "")
                                if step_file.startswith("file://"):
                                    step_file = step_file[7:]
                                if target_file.startswith("file://"):
                                    target_file = target_file[7:]
                                if step_file and os.path.basename(target_file) == os.path.basename(step_file):
                                    args_match = True
                            elif tool_name in ["write_to_file", "create_file"]:
                                target_file = arguments.get("TargetFile", "")
                                step_file = step.get("createFile", {}).get("filePath", "")
                                if not step_file:
                                    step_file = step.get("codeAction", {}).get("actionSpec", {}).get("createFile", {}).get("path", {}).get("absoluteUri", "")
                                if step_file.startswith("file://"):
                                    step_file = step_file[7:]
                                if target_file.startswith("file://"):
                                    target_file = target_file[7:]
                                if step_file and os.path.basename(target_file) == os.path.basename(step_file):
                                    args_match = True
                            else:
                                args_match = True
                                
                            if args_match:
                                for ci in step.get("completedInteractions", []):
                                    resp_obj = ci.get("response", {})
                                    if "permission" in resp_obj:
                                        allow = resp_obj.get("permission", {}).get("allow", False)
                                        if not fut.done():
                                            print(f"[LS Poller] Found completed interaction response in LS: allow={allow}")
                                            fut.set_result("approve_ide" if allow else "deny_ide")
                                        return
        except Exception:
            pass
        await asyncio.sleep(1.0)

@app.get("/config")
async def get_ui_config():
    """
    Description:
        FastAPI endpoint to return status bar UI details to the Language Server / IDE.
    Usage:
        res = await get_ui_config()
    Usage Example:
        res = await get_ui_config()
    """
    base_url = f"https://localhost:{state.PORT + 1}"
    return {
        "display_name": "Liaison Status",
        "views": [
            {
                "entrypoint": 2,
                "path": "/status",
                "url": f"{base_url}/status"
            }
        ]
    }

@app.get("/api/status")
async def get_status_api():
    """
    Description:
        Endpoint to retrieve the JSON status metrics, LLM provider, and auto-switch settings.
    Usage:
        res = await get_status_api()
    Usage Example:
        res = await get_status_api()
    """
    uptime_seconds = int(time.time() - state.START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    try:
        sessions = discover_agent_sessions()
        active_sessions = len(sessions)
    except Exception:
        active_sessions = "Error"
        
    import bot
    DISCORD_BOT_TOKEN = bot.DISCORD_BOT_TOKEN
    DISCORD_USER_ID = bot.DISCORD_USER_ID
    DISCORD_USER_NAME = os.getenv("DISCORD_USER_NAME", "Tig1")
    
    bot_permissions = 0
    if state.bot and state.bot.is_ready():
        for guild in state.bot.guilds:
            if guild.me:
                bot_permissions = max(bot_permissions, guild.me.guild_permissions.value)
                
    if not DISCORD_BOT_TOKEN:
        status_label = "Config Warning"
        status_color = "#f59e0b"
        status_rgb = "245, 158, 11"
    elif state.bot and state.bot.is_ready():
        status_label = "Active"
        status_color = "#10b981"
        status_rgb = "16, 185, 129"
    else:
        if uptime_seconds < 30:
            status_label = "Connecting"
            status_color = "#f59e0b"
            status_rgb = "245, 158, 11"
        else:
            status_label = "Disconnected"
            status_color = "#ef4444"
            status_rgb = "239, 68, 68"
            
    return {
        "uptime": uptime_str,
        "active_sessions": active_sessions,
        "status_label": status_label,
        "status_color": status_color,
        "status_rgb": status_rgb,
        "discord_user": f"{DISCORD_USER_NAME} (ID: {DISCORD_USER_ID})" if DISCORD_USER_ID else "Unlinked",
        "paused": state.IS_PAUSED,
        "model_provider": state.MODEL_PROVIDER,
        "auto_switch_local": state.AUTO_SWITCH_LOCAL,
        "bot_permissions": bot_permissions,
        "discord_bot_permissions": state.DISCORD_BOT_PERMISSIONS
    }

@app.post("/api/pause")
async def post_pause():
    """
    Description:
        Endpoint to pause the Discord liaisonbot (commands auto-approved).
    Usage:
        res = await post_pause()
    Usage Example:
        res = await post_pause()
    """
    state.IS_PAUSED = True
    print("[API] Liaison PAUSED")
    return {"status": "success", "paused": True}

@app.post("/api/resume")
async def post_resume():
    """
    Description:
        Endpoint to resume the Discord liaison bot.
    Usage:
        res = await post_resume()
    Usage Example:
        res = await post_resume()
    """
    state.IS_PAUSED = False
    print("[API] Liaison RESUMED")
    return {"status": "success", "paused": False}

@app.post("/api/toggle-pause")
async def post_toggle_pause():
    """
    Description:
        Endpoint to toggle between paused and resumed states.
    Usage:
        res = await post_toggle_pause()
    Usage Example:
        res = await post_toggle_pause()
    """
    state.IS_PAUSED = not state.IS_PAUSED
    status_str = "PAUSED" if state.IS_PAUSED else "RESUMED"
    print(f"[API] Liaison toggled to {status_str}")
    return {"status": "success", "paused": state.IS_PAUSED}

@app.post("/api/settings")
async def post_settings(req: SettingsRequest):
    """
    Description:
        Endpoint to update model provider settings dynamically.
    Usage:
        res = await post_settings(settings_request)
    Usage Example:
        res = await post_settings(SettingsRequest(model_provider="ollama", auto_switch_local=True, discord_bot_permissions="8471182706732241"))
    """
    state.MODEL_PROVIDER = req.model_provider
    state.AUTO_SWITCH_LOCAL = req.auto_switch_local
    state.DISCORD_BOT_PERMISSIONS = req.discord_bot_permissions
    update_settings_in_env(req.model_provider, req.auto_switch_local, req.discord_bot_permissions)
    print(f"[API] Settings updated: provider={state.MODEL_PROVIDER}, auto_switch={state.AUTO_SWITCH_LOCAL}, permissions={state.DISCORD_BOT_PERMISSIONS}")
    return {
        "status": "success", 
        "model_provider": state.MODEL_PROVIDER, 
        "auto_switch_local": state.AUTO_SWITCH_LOCAL,
        "discord_bot_permissions": state.DISCORD_BOT_PERMISSIONS
    }

@app.get("/status")
async def get_status_ui():
    """
    Description:
        FastAPI endpoint to render the main HTML Status Page.
    Usage:
        res = await get_status_ui()
    Usage Example:
        res = await get_status_ui()
    """
    uptime_seconds = int(time.time() - state.START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    try:
        sessions = discover_agent_sessions()
        active_sessions = len(sessions)
    except Exception:
        active_sessions = "Error"
        
    bot_name = "AGY2 Liaison Bot"
    import bot
    DISCORD_BOT_TOKEN = bot.DISCORD_BOT_TOKEN
    DISCORD_USER_ID = bot.DISCORD_USER_ID
    DISCORD_USER_NAME = os.getenv("DISCORD_USER_NAME", "Tig1")
    DISCORD_BOT_PERMISSIONS = getattr(state, "DISCORD_BOT_PERMISSIONS", "8471182706732241")
    
    bot_permissions = 0
    if state.bot and state.bot.is_ready():
        for guild in state.bot.guilds:
            if guild.me:
                bot_permissions = max(bot_permissions, guild.me.guild_permissions.value)
                
    if not DISCORD_BOT_TOKEN:
        status_label = "Config Warning"
        status_color = "#f59e0b"
        status_rgb = "245, 158, 11"
    elif state.bot and state.bot.is_ready():
        status_label = "Active"
        status_color = "#10b981"
        status_rgb = "16, 185, 129"
    else:
        if uptime_seconds < 30:
            status_label = "Connecting"
            status_color = "#f59e0b"
            status_rgb = "245, 158, 11"
        else:
            status_label = "Disconnected"
            status_color = "#ef4444"
            status_rgb = "239, 68, 68"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Antigravity Liaison Bot Status</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-color: #0b0f19;
                --card-bg: rgba(17, 24, 39, 0.7);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
                --primary: #6366f1; /* Indigo */
                --success: #10b981; /* Emerald */
                --warning: #f59e0b; /* Amber */
                --danger: #ef4444; /* Rose */
                --pulse-rgb: {status_rgb};
            }}
            body {{
                font-family: 'Inter', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-main);
                margin: 0;
                padding: 24px;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 90vh;
            }}
            .container {{
                width: 100%;
                max-width: 480px;
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 20px;
                backdrop-filter: blur(16px);
                padding: 32px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                animation: fadeIn 0.8s ease-out;
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 24px;
                border-bottom: 1px solid var(--card-border);
                padding-bottom: 16px;
            }}
            .title {{
                font-size: 20px;
                font-weight: 600;
                color: var(--text-main);
                margin: 0;
            }}
            .status-badge-container {{
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .status-badge {{
                display: flex;
                align-items: center;
                gap: 8px;
                background: rgba({status_rgb}, 0.05);
                border: 1px solid rgba({status_rgb}, 0.1);
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 500;
                color: {status_color};
            }}
            .dot {{
                width: 8px;
                height: 8px;
                background-color: {status_color};
                border-radius: 50%;
                display: inline-block;
                box-shadow: 0 0 8px {status_color};
                animation: pulse 2s infinite;
            }}
            @keyframes pulse {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(var(--pulse-rgb), 0.7); }}
                70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(var(--pulse-rgb), 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(var(--pulse-rgb), 0); }}
            }}
            .metric-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
                margin-bottom: 24px;
            }}
            .metric-card {{
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid var(--card-border);
                border-radius: 12px;
                padding: 16px;
                transition: all 0.3s ease;
            }}
            .metric-card:hover {{
                background: rgba(255, 255, 255, 0.05);
                border-color: var(--primary);
                transform: translateY(-2px);
            }}
            .metric-label {{
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--text-muted);
                margin-bottom: 4px;
            }}
            .metric-value {{
                font-size: 16px;
                font-weight: 600;
                color: var(--text-main);
            }}
            .info-list {{
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}
            .info-item {{
                display: flex;
                justify-content: space-between;
                font-size: 13px;
                padding: 10px 14px;
                background: rgba(255, 255, 255, 0.01);
                border: 1px solid var(--card-border);
                border-radius: 10px;
            }}
            .info-key {{
                color: var(--text-muted);
            }}
            .info-val {{
                font-weight: 500;
                color: var(--text-main);
            }}
            .pause-btn {{
                width: 100%;
                background: var(--primary);
                border: none;
                border-radius: 12px;
                color: white;
                padding: 12px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 24px;
                box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
            }}
            .pause-btn:hover {{
                background: #4f46e5;
                transform: translateY(-1px);
            }}
            .pause-btn.paused {{
                background: var(--warning);
                box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
            }}
            .pause-btn.paused:hover {{
                background: #d97706;
            }}
            .footer {{
                margin-top: 24px;
                text-align: center;
                font-size: 11px;
                color: var(--text-muted);
            }}
            /* Toggle Switch */
            .switch {{
                position: relative;
                display: inline-block;
                width: 40px;
                height: 20px;
            }}
            .switch input {{
                opacity: 0;
                width: 0;
                height: 0;
            }}
            .slider {{
                position: absolute;
                cursor: pointer;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: rgba(255,255,255,0.1);
                transition: .3s;
                border-radius: 20px;
                border: 1px solid var(--card-border);
            }}
            .slider:before {{
                position: absolute;
                content: "";
                height: 12px;
                width: 12px;
                left: 3px;
                bottom: 3px;
                background-color: var(--text-main);
                transition: .3s;
                border-radius: 50%;
            }}
            input:checked + .slider {{
                background-color: var(--success);
            }}
            input:checked + .slider:before {{
                transform: translateX(20px);
            }}
            .provider-select-btn {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid var(--card-border);
                color: var(--text-muted);
                padding: 6px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
                font-weight: 500;
                transition: all 0.2s;
            }}
            .provider-select-btn.active {{
                background: var(--primary);
                color: white;
                border-color: var(--primary);
                box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
            }}
            /* Modal Overlay */
            .modal-overlay {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(4px);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s ease;
            }}
            .modal-overlay.show {{
                opacity: 1;
                pointer-events: auto;
            }}
            .modal-content {{
                background: #111827;
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 24px;
                width: 320px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
                text-align: left;
                transform: scale(0.95);
                transition: transform 0.2s ease;
            }}
            .modal-overlay.show .modal-content {{
                transform: scale(1);
            }}
            /* Toast notification */
            .toast {{
                position: fixed;
                bottom: 24px;
                right: 24px;
                background: var(--success);
                color: white;
                padding: 12px 20px;
                border-radius: 10px;
                box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
                font-size: 13px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
                z-index: 1001;
                opacity: 0;
                transform: translateY(20px);
                transition: all 0.3s ease;
                pointer-events: none;
            }}
            .toast.show {{
                opacity: 1;
                transform: translateY(0);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 class="title">🤖 Discord Liaison</h1>
                <div class="status-badge-container">
                    <div class="status-badge" id="status-badge">
                        <span class="dot" id="status-dot"></span>
                        <span id="status-text">{status_label}</span>
                    </div>
                    <div class="status-badge" id="paused-badge" style="display: {'flex' if state.IS_PAUSED else 'none'}; background: rgba(245, 158, 11, 0.05); border: 1px solid rgba(245, 158, 11, 0.1); color: #f59e0b; gap: 8px;">
                        <span class="dot" style="background-color: #f59e0b; box-shadow: 0 0 8px #f59e0b;"></span>
                        <span>Paused</span>
                    </div>
                </div>
            </div>
            
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-label">Port</div>
                    <div class="metric-value">{state.PORT}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Process ID</div>
                    <div class="metric-value">{os.getpid()}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Liaison Bot</div>
                    <div class="metric-value">{bot_name}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Uptime</div>
                    <div class="metric-value" id="uptime-val">{uptime_str}</div>
                </div>
                
                <!-- Model Switcher Card -->
                <div class="metric-card" style="grid-column: span 2;">
                    <div class="metric-label" style="margin-bottom: 12px; font-weight: 600;">LLM Provider Setup</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span class="info-key" style="font-size: 13px;">Provider</span>
                        <div style="display: flex; gap: 8px;">
                            <button id="btn-gemini" class="provider-select-btn">Gemini</button>
                            <button id="btn-ollama" class="provider-select-btn">Ollama (Local)</button>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="info-key" style="font-size: 13px;">Auto-switch to local upon quota depletion</span>
                        <label class="switch">
                            <input type="checkbox" id="chk-auto-switch">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
            </div>
            
            <div class="info-list">
                <div class="info-item">
                    <span class="info-key">Registered User</span>
                    <span class="info-val" id="user-val">{DISCORD_USER_NAME} (ID: {DISCORD_USER_ID or "N/A"})</span>
                </div>
                <div class="info-item">
                    <span class="info-key">Active Sessions</span>
                    <span class="info-val" id="sessions-val">{active_sessions}</span>
                </div>
                <div class="info-item">
                    <span class="info-key">Active Permissions</span>
                    <span class="info-val" id="permissions-val">{bot_permissions}</span>
                </div>
                <div class="info-item" style="align-items: center; justify-content: space-between; display: flex;">
                    <span class="info-key">Invite Permissions</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <input type="text" id="txt-permissions" value="{DISCORD_BOT_PERMISSIONS}" style="background: rgba(255,255,255,0.05); border: 1px solid var(--card-border); border-radius: 6px; color: var(--text-main); font-size: 13px; padding: 4px 8px; width: 140px; text-align: right; outline: none; font-family: monospace;" />
                        <button id="btn-save-permissions" style="background: var(--primary); border: none; border-radius: 6px; color: white; padding: 4px 10px; font-size: 12px; font-weight: 600; cursor: pointer; transition: background 0.2s;">Save</button>
                    </div>
                </div>
                <div class="info-item">
                    <span class="info-key">System Integrations</span>
                    <span class="info-val">FastAPI + Discord.py</span>
                </div>
            </div>
            
            <button id="toggle-pause-btn" class="pause-btn {'paused' if state.IS_PAUSED else ''}">
                {"Resume Liaison" if state.IS_PAUSED else "Pause Liaison"}
            </button>
            
            <div class="footer">
                Antigravity Platform Extension | Real-Time Updates
            </div>
        </div>

        <!-- Confirmation Modal -->
        <div id="confirm-modal" class="modal-overlay">
            <div class="modal-content">
                <h3 style="margin-top: 0; margin-bottom: 12px; font-size: 16px; font-weight: 600; color: var(--text-main);">Save Changes?</h3>
                <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 20px; line-height: 1.5;">Are you sure you want to update the bot permissions integer to <span id="new-perms-display" style="font-weight: 600; color: var(--primary);"></span>?</p>
                <div style="display: flex; justify-content: flex-end; gap: 10px;">
                    <button id="btn-confirm-cancel" style="background: rgba(255,255,255,0.05); border: 1px solid var(--card-border); border-radius: 8px; color: var(--text-main); padding: 8px 16px; font-size: 13px; cursor: pointer; font-weight: 500;">Cancel</button>
                    <button id="btn-confirm-save" style="background: var(--primary); border: none; border-radius: 8px; color: white; padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer;">Confirm</button>
                </div>
            </div>
        </div>

        <!-- Success Toast -->
        <div id="success-toast" class="toast">
            <span>💾</span>
            <span>Settings saved successfully!</span>
        </div>

        <script>
            let currentProvider = "";
            let currentAutoSwitch = false;
            let currentPermissions = "{DISCORD_BOT_PERMISSIONS}";
            const txtPerms = document.getElementById('txt-permissions');

            async function updateStatus() {{
                try {{
                    const response = await fetch('/api/status');
                    if (!response.ok) return;
                    const data = await response.json();
                    
                    document.getElementById('uptime-val').textContent = data.uptime;
                    document.getElementById('sessions-val').textContent = data.active_sessions;
                    document.getElementById('user-val').textContent = data.discord_user;
                    document.getElementById('permissions-val').textContent = data.bot_permissions;
                    
                    if (document.activeElement !== txtPerms) {{
                        txtPerms.value = data.discord_bot_permissions;
                        currentPermissions = data.discord_bot_permissions;
                    }}
                    
                    const badge = document.getElementById('status-badge');
                    const badgeText = document.getElementById('status-text');
                    const dot = document.getElementById('status-dot');
                    
                    badgeText.textContent = data.status_label;
                    badgeText.style.color = data.status_color;
                    badge.style.background = `rgba(${{data.status_rgb}}, 0.05)`;
                    badge.style.borderColor = `rgba(${{data.status_rgb}}, 0.1)`;
                    badge.style.color = data.status_color;
                    
                    dot.style.backgroundColor = data.status_color;
                    dot.style.boxShadow = `0 0 8px ${{data.status_color}}`;
                    
                    updatePauseUI(data.paused);
                    updateSettingsUI(data.model_provider, data.auto_switch_local);
                    
                    document.documentElement.style.setProperty('--pulse-rgb', data.status_rgb);
                }} catch (e) {{
                    console.error("Failed to fetch status:", e);
                }}
            }}
            
            function updatePauseUI(isPaused) {{
                const pausedBadge = document.getElementById('paused-badge');
                const toggleBtn = document.getElementById('toggle-pause-btn');
                if (isPaused) {{
                    pausedBadge.style.display = 'flex';
                    toggleBtn.textContent = 'Resume Liaison';
                    toggleBtn.classList.add('paused');
                }} else {{
                    pausedBadge.style.display = 'none';
                    toggleBtn.textContent = 'Pause Liaison';
                    toggleBtn.classList.remove('paused');
                }}
            }}

            function updateSettingsUI(provider, autoSwitch) {{
                currentProvider = provider;
                currentAutoSwitch = autoSwitch;
                
                const btnGemini = document.getElementById('btn-gemini');
                const btnOllama = document.getElementById('btn-ollama');
                const chkAutoSwitch = document.getElementById('chk-auto-switch');
                
                if (provider === "gemini") {{
                    btnGemini.classList.add('active');
                    btnOllama.classList.remove('active');
                }} else {{
                    btnGemini.classList.remove('active');
                    btnOllama.classList.add('active');
                }}
                
                chkAutoSwitch.checked = autoSwitch;
            }}

            async function saveSettings(provider, autoSwitch) {{
                try {{
                    const res = await fetch('/api/settings', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ 
                            model_provider: provider, 
                            auto_switch_local: autoSwitch,
                            discord_bot_permissions: currentPermissions
                        }})
                    }});
                    if (res.ok) {{
                        const data = await res.json();
                        updateSettingsUI(data.model_provider, data.auto_switch_local);
                    }}
                }} catch (e) {{
                    console.error("Failed to save settings:", e);
                }}
            }}
            
            document.getElementById('btn-gemini').addEventListener('click', () => saveSettings('gemini', currentAutoSwitch));
            document.getElementById('btn-ollama').addEventListener('click', () => saveSettings('ollama', currentAutoSwitch));
            document.getElementById('chk-auto-switch').addEventListener('change', (e) => saveSettings(currentProvider, e.target.checked));

            const savePermsBtn = document.getElementById('btn-save-permissions');
            const confirmModal = document.getElementById('confirm-modal');
            const newPermsDisplay = document.getElementById('new-perms-display');
            const confirmCancelBtn = document.getElementById('btn-confirm-cancel');
            const confirmSaveBtn = document.getElementById('btn-confirm-save');
            const successToast = document.getElementById('success-toast');

            let pendingPermissions = "";

            savePermsBtn.addEventListener('click', () => {{
                pendingPermissions = txtPerms.value.trim();
                if (!pendingPermissions) return;
                newPermsDisplay.textContent = pendingPermissions;
                confirmModal.classList.add('show');
            }});

            confirmCancelBtn.addEventListener('click', () => {{
                confirmModal.classList.remove('show');
            }});

            confirmSaveBtn.addEventListener('click', async () => {{
                confirmModal.classList.remove('show');
                try {{
                    const res = await fetch('/api/settings', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ 
                            model_provider: currentProvider, 
                            auto_switch_local: currentAutoSwitch,
                            discord_bot_permissions: pendingPermissions
                        }})
                    }});
                    if (res.ok) {{
                        const data = await res.json();
                        currentPermissions = data.discord_bot_permissions;
                        txtPerms.value = currentPermissions;
                        
                        // Show success toast
                        successToast.classList.add('show');
                        setTimeout(() => {{
                            successToast.classList.remove('show');
                        }}, 3000);
                    }}
                }} catch (e) {{
                    console.error("Failed to save permissions settings:", e);
                }}
            }});
            
            const toggleBtn = document.getElementById('toggle-pause-btn');
            toggleBtn.addEventListener('click', async () => {{
                try {{
                    const res = await fetch('/api/toggle-pause', {{ method: 'POST' }});
                    if (res.ok) {{
                        const data = await res.json();
                        updatePauseUI(data.paused);
                    }}
                }} catch (e) {{
                    console.error("Failed to toggle pause:", e);
                }}
            }});
            
            setInterval(updateStatus, 2000);
            updateStatus();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/message")
async def post_message(req: MessageRequest):
    """
    Description:
        Endpoint to post a text message or update DM.
    Usage:
        res = await post_message(message_request)
    Usage Example:
        res = await post_message(req)
    """
    if not state.bot or not state.bot.is_ready():
        raise HTTPException(status_code=503, detail="Discord bot is not ready")
    target = await get_discord_target()
    if not target:
        raise HTTPException(status_code=500, detail="No suitable destination found")
        
    content = req.content
    seen_paths = set()
    content, all_files = extract_and_prepare_files(content, seen_paths)
    
    embed_title = req.embed_title
    embed_description = req.embed_description
    if embed_description:
        embed_description, new_files = extract_and_prepare_files(embed_description, seen_paths)
        all_files.extend(new_files)
        
    try:
        if len(content) > 1900:
            chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
            if embed_title or embed_description:
                embed = discord.Embed(
                    title=embed_title,
                    description=embed_description,
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                if all_files:
                    await target.send(content=chunks[0], embed=embed, files=all_files)
                else:
                    await target.send(content=chunks[0], embed=embed)
                for chunk in chunks[1:]:
                    await target.send(content=chunk)
            else:
                if all_files:
                    await target.send(content=chunks[0], files=all_files)
                else:
                    await target.send(content=chunks[0])
                for chunk in chunks[1:]:
                    await target.send(content=chunk)
        else:
            if embed_title or embed_description:
                embed = discord.Embed(
                    title=embed_title,
                    description=embed_description,
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                if all_files:
                    await target.send(content=content, embed=embed, files=all_files)
                else:
                    await target.send(content=content, embed=embed)
            else:
                if all_files:
                    await target.send(content=content, files=all_files)
                else:
                    await target.send(content=content)
        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to send Discord message: {e}")

def update_settings_in_env(model_provider: str, auto_switch_local: bool, discord_bot_permissions: str):
    """
    Description:
        Updates the config.json and .env files with the Model Provider, Auto Switch Local, and Bot Permissions settings.
    Usage:
        update_settings_in_env(model_provider, auto_switch_local, discord_bot_permissions)
    Usage Example:
        update_settings_in_env("ollama", True, "8471182706732241")
    """
    # 1. Update config.json
    config_path = state.CONFIG_PATH
    try:
        config_data = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = json.load(f)
        config_data["model_provider"] = model_provider
        config_data["auto_switch_local"] = auto_switch_local
        config_data["discord_bot_permissions"] = discord_bot_permissions
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        print(f"[Bot] Successfully updated config.json with model_provider={model_provider}, auto_switch_local={auto_switch_local}, discord_bot_permissions={discord_bot_permissions}")
    except Exception as e:
        print(f"[Bot] Failed to update config.json: {e}")

    # 2. Update .env file
    env_path = state.ENV_PATH
    try:
        new_content = []
        provider_found = False
        autoswitch_found = False
        permissions_found = False
        
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
            for line in lines:
                line_stripped = line.strip()
                if line_stripped.startswith("MODEL_PROVIDER="):
                    new_content.append(f"MODEL_PROVIDER={model_provider}")
                    provider_found = True
                elif line_stripped.startswith("AUTO_SWITCH_LOCAL="):
                    new_content.append(f"AUTO_SWITCH_LOCAL={str(auto_switch_local)}")
                    autoswitch_found = True
                elif line_stripped.startswith("DISCORD_BOT_PERMISSIONS="):
                    new_content.append(f"DISCORD_BOT_PERMISSIONS={discord_bot_permissions}")
                    permissions_found = True
                else:
                    new_content.append(line.rstrip("\r\n"))
                    
        if not provider_found:
            new_content.append(f"MODEL_PROVIDER={model_provider}")
        if not autoswitch_found:
            new_content.append(f"AUTO_SWITCH_LOCAL={str(auto_switch_local)}")
        if not permissions_found:
            new_content.append(f"DISCORD_BOT_PERMISSIONS={discord_bot_permissions}")
            
        with open(env_path, "w") as f:
            f.write("\n".join(new_content) + "\n")
        print(f"[Bot] Successfully updated .env file with MODEL_PROVIDER={model_provider}, AUTO_SWITCH_LOCAL={auto_switch_local}, DISCORD_BOT_PERMISSIONS={discord_bot_permissions}")
    except Exception as e:
        print(f"[Bot] Failed to update .env settings: {e}")


def update_env_file(user_id: str):
    """
    Description:
        Updates the .env file with the resolved Discord User ID.
    Usage:
        update_env_file(user_id)
    Usage Example:
        update_env_file("123456789")
    """
    env_path = state.ENV_PATH
    try:
        new_content = []
        found = False
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
            for line in lines:
                if line.strip().startswith("DISCORD_USER_ID="):
                    new_content.append(f"DISCORD_USER_ID={user_id}")
                    found = True
                else:
                    new_content.append(line.rstrip("\r\n"))
        if not found:
            new_content.append(f"DISCORD_USER_ID={user_id}")
        
        with open(env_path, "w") as f:
            f.write("\n".join(new_content) + "\n")
        print(f"[Bot] Successfully updated .env file with DISCORD_USER_ID={user_id}")
    except Exception as e:
        print(f"[Bot] Failed to update .env file: {e}")

@app.post("/approve", response_model=ApprovalResponse)
async def post_approve(req: ApprovalRequest):
    """
    Description:
        Handles approval requests from the active agent by sending buttons to the user on Discord.
    Usage:
        res = await post_approve(approval_request)
    Usage Example:
        res = await post_approve(req)
    """
    if state.IS_PAUSED:
        print(f"[API] Auto-approving because Liaison is paused: {req.tool_name}")
        return ApprovalResponse(approved=True, reason="Liaison is paused")

    if not state.bot or not state.bot.is_ready():
        raise HTTPException(status_code=503, detail="Discord bot is not ready")

    import bot
    DISCORD_USER_ID = bot.DISCORD_USER_ID
    DISCORD_USER_NAME = os.getenv("DISCORD_USER_NAME", "Tig1")
    DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
    
    target = None
    target_type = "channel"
    
    if DISCORD_USER_ID:
        try:
            target = await state.bot.fetch_user(int(DISCORD_USER_ID))
            target_type = "user"
        except Exception as e:
            target = None

    if not target and DISCORD_USER_NAME:
        for u in state.bot.users:
            if u.name.lower() == DISCORD_USER_NAME.lower():
                target = u
                target_type = "user"
                DISCORD_USER_ID = str(u.id)
                update_env_file(DISCORD_USER_ID)
                break

    if not target and DISCORD_CHANNEL_ID:
        try:
            target = state.bot.get_channel(int(DISCORD_CHANNEL_ID))
            target_type = "channel"
        except Exception:
            target = None

    if not target:
        for guild in state.bot.guilds:
            for chan in guild.text_channels:
                if chan.permissions_for(guild.me).send_messages:
                    target = chan
                    target_type = "channel"
                    break
            if target:
                break
    
    if not target:
        raise HTTPException(
            status_code=500, 
            detail="No suitable Discord destination found."
        )

    request_id = req.request_id or str(uuid.uuid4())
    fut = asyncio.Future()
    state.pending_approvals[request_id] = fut
    state.active_pending_items[request_id] = {
        "type": "permission",
        "convo_id": req.conversation_id,
        "project_name": get_session_project(req.conversation_id),
        "tool_name": req.tool_name,
        "arguments": req.arguments,
        "agent_name": req.agent_name,
        "timestamp": time.time()
    }

    ping_str = f"<@{DISCORD_USER_ID}> " if DISCORD_USER_ID else ""

    embed = discord.Embed(
        title="🔔 Approval Required by Working Agent",
        description=f"Agent **{req.agent_name}** needs authorization to proceed.",
        color=discord.Color.from_rgb(99, 102, 241),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="💼 Agent Name", value=req.agent_name, inline=True)
    embed.add_field(name="💬 Conversation ID", value=f"`{req.conversation_id}`", inline=True)
    embed.add_field(name="🔧 Tool to Execute", value=f"`{req.tool_name}`", inline=False)
    
    args_json = json.dumps(req.arguments, indent=2)
    if len(args_json) > 1000:
        args_json = args_json[:997] + "..."
    embed.add_field(name="📦 Arguments", value=f"```json\n{args_json}\n```", inline=False)
    embed.set_footer(text="Antigravity Agent Management System")

    show_always_allow = True
    if req.tool_name == "run_command":
        cmd = req.arguments.get("CommandLine", "")
        if is_dangerous_command(cmd):
            show_always_allow = False

    seen_paths = set()
    embed, embed_files = extract_and_prepare_embed_files(embed, seen_paths)
    arg_files = extract_files_from_dict_or_list(req.arguments, seen_paths)
    all_files = embed_files + arg_files

    view = DiscordApprovalView(request_id=request_id, show_always_allow=show_always_allow)

    try:
        if all_files:
            msg = await target.send(content=f"{ping_str}⚠️ **Action Required!**", embed=embed, view=view, files=all_files)
        else:
            msg = await target.send(content=f"{ping_str}⚠️ **Action Required!**", embed=embed, view=view)
    except Exception as e:
        del state.pending_approvals[request_id]
        raise HTTPException(status_code=500, detail=f"Failed to send Discord message: {e}")

    polling_task = None
    if req.ls_address and req.ls_token:
        polling_task = asyncio.create_task(
            poll_ls_for_approval(
                ls_address=req.ls_address,
                ls_token=req.ls_token,
                convo_id=req.conversation_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                fut=fut
            )
        )

    try:
        await asyncio.wait(
            [asyncio.create_task(view.wait()), fut],
            return_when=asyncio.FIRST_COMPLETED
        )
        view.stop()

        decision = "deny"
        if fut.done():
            res = fut.result()
            if res is True:
                decision = "approve"
            elif res is False:
                decision = "deny"
            else:
                decision = res
        
        approved = decision in ["approve", "approve_ide", "allow_project", "always_allow"]
        
        if decision == "allow_project":
            save_persistent_permission("project", req.tool_name, req.arguments)
        elif decision == "always_allow":
            save_persistent_permission("global", req.tool_name, req.arguments)
            
        status_color = discord.Color.green() if approved else discord.Color.red()
        
        status_map = {
            "approve": "✅ Approved (Once)",
            "approve_ide": "✅ Approved in IDE",
            "allow_project": "📁 Allowed for Project",
            "always_allow": "🌐 Always Allowed",
            "deny": "❌ Denied",
            "deny_ide": "❌ Denied in IDE"
        }
        status_text = status_map.get(decision, "❌ Denied")
        
        updated_embed = embed.copy()
        updated_embed.color = status_color
        updated_embed.add_field(name="🏁 Decision", value=f"**{status_text}**", inline=False)
        
        await msg.edit(content=f"**Decision Recorded:** {status_text}", embed=updated_embed, view=None)

        async def delete_msg_after_delay(message, delay=3.0):
            await asyncio.sleep(delay)
            try:
                await message.delete()
            except Exception:
                pass
                
        asyncio.create_task(delete_msg_after_delay(msg))
        return ApprovalResponse(approved=approved)

    except Exception as e:
        return ApprovalResponse(approved=False, reason=str(e))
    finally:
        if polling_task and not polling_task.done():
            polling_task.cancel()
        if request_id in state.pending_approvals:
            del state.pending_approvals[request_id]
        state.active_pending_items.pop(request_id, None)

@app.post("/interaction", response_model=InteractionResponse)
async def post_interaction(req: InteractionRequest):
    """
    Description:
        Handles user interactions/questions from the agent.
    Usage:
        res = await post_interaction(interaction_request)
    Usage Example:
        res = await post_interaction(req)
    """
    if not state.bot or not state.bot.is_ready():
        raise HTTPException(status_code=503, detail="Discord bot is not ready")

    import bot
    DISCORD_USER_ID = bot.DISCORD_USER_ID
    DISCORD_USER_NAME = os.getenv("DISCORD_USER_NAME", "Tig1")
    DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
    
    target = None
    target_type = "channel"
    
    if DISCORD_USER_ID:
        try:
            target = await state.bot.fetch_user(int(DISCORD_USER_ID))
            target_type = "user"
        except Exception:
            target = None

    if not target and DISCORD_USER_NAME:
        for u in state.bot.users:
            if u.name.lower() == DISCORD_USER_NAME.lower():
                target = u
                target_type = "user"
                DISCORD_USER_ID = str(u.id)
                update_env_file(DISCORD_USER_ID)
                break

    if not target and DISCORD_CHANNEL_ID:
        try:
            target = state.bot.get_channel(int(DISCORD_CHANNEL_ID))
            target_type = "channel"
        except Exception:
            target = None

    if not target:
        for guild in state.bot.guilds:
            for chan in guild.text_channels:
                if chan.permissions_for(guild.me).send_messages:
                    target = chan
                    target_type = "channel"
                    break
            if target:
                break
    
    if not target:
        raise HTTPException(status_code=500, detail="No suitable Discord destination found.")

    ping_str = f"<@{DISCORD_USER_ID}> " if DISCORD_USER_ID else ""
    interaction_id = req.request_id or str(uuid.uuid4())
    state.active_pending_items[interaction_id] = {
        "type": "interaction",
        "convo_id": req.conversation_id,
        "project_name": get_session_project(req.conversation_id),
        "agent_name": req.agent_name,
        "timestamp": time.time(),
        "questions": [q.get("question", "") for q in req.questions]
    }

    try:
        responses = []
        cancelled = False
        
        for idx, q_data in enumerate(req.questions):
            question_text = q_data.get("question", "")
            options = q_data.get("options", [])
            is_multi_select = q_data.get("is_multi_select", False)
            
            request_id = f"{req.request_id or str(uuid.uuid4())}_{idx}"
            fut = asyncio.Future()
            state.pending_interactions[request_id] = fut
            
            if not options and DISCORD_USER_ID:
                state.active_text_prompts[DISCORD_USER_ID] = fut
                
            embed = discord.Embed(
                title="❓ Question from Working Agent",
                description=f"Agent **{req.agent_name}** needs input to proceed.",
                color=discord.Color.from_rgb(99, 102, 241),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="💬 Conversation ID", value=f"`{req.conversation_id}`", inline=True)
            embed.add_field(name="📝 Question", value=question_text, inline=False)
            
            if options:
                opts_text = ""
                for opt in options:
                    opts_text += f"• **{opt['id']}**: {opt['text']}\n"
                embed.add_field(name="📋 Options", value=opts_text, inline=False)
                view = DiscordInteractionView(request_id=request_id, question_idx=idx, options=options, is_multi_select=is_multi_select)
            else:
                embed.add_field(name="💬 Response Required", value="Please click **Type Answer** below or reply directly to this chat.", inline=False)
                view = DiscordFreeformInteractionView(request_id=request_id)
            seen_paths = set()
            embed, embed_files = extract_and_prepare_embed_files(embed, seen_paths)
                
            try:
                if embed_files:
                    msg = await target.send(content=f"{ping_str}⚠️ **Interaction Required!**", embed=embed, view=view, files=embed_files)
                else:
                    msg = await target.send(content=f"{ping_str}⚠️ **Interaction Required!**", embed=embed, view=view)
            except Exception as e:
                if request_id in state.pending_interactions:
                    del state.pending_interactions[request_id]
                if DISCORD_USER_ID in state.active_text_prompts:
                    del state.active_text_prompts[DISCORD_USER_ID]
                raise HTTPException(status_code=500, detail=f"Failed to send Discord message: {e}")
                
            try:
                await fut
                res = fut.result()
                
                if DISCORD_USER_ID in state.active_text_prompts:
                    state.active_text_prompts.pop(DISCORD_USER_ID, None)
                    
                skipped = res.get("skipped", False)
                selected_ids = res.get("selected_option_ids", [])
                freeform = res.get("freeform_response", "")
                
                updated_embed = embed.copy()
                updated_embed.color = discord.Color.green() if not skipped else discord.Color.greyple()
                
                if skipped:
                    ans_text = "Skipped"
                elif selected_ids:
                    selected_opts = [opt['text'] for opt in options if opt['id'] in selected_ids]
                    ans_text = ", ".join(selected_opts)
                else:
                    ans_text = freeform
                    
                updated_embed.add_field(name="🏁 Response Recorded", value=f"**{ans_text}**", inline=False)
                await msg.edit(content="**Interaction Recorded**", embed=updated_embed, view=None)

                async def delete_msg_after_delay(message, delay=3.0):
                    await asyncio.sleep(delay)
                    try:
                        await message.delete()
                    except Exception:
                        pass
                        
                asyncio.create_task(delete_msg_after_delay(msg))
                
                responses.append({
                    "selected_option_ids": selected_ids,
                    "freeform_response": freeform,
                    "skipped": skipped
                })
            except Exception:
                responses.append({"selected_option_ids": [], "freeform_response": "", "skipped": True})
            finally:
                if request_id in state.pending_interactions:
                    del state.pending_interactions[request_id]
                    
        return InteractionResponse(responses=responses, cancelled=cancelled)
    finally:
        state.active_pending_items.pop(interaction_id, None)


async def get_discord_target() -> Optional[discord.abc.Messageable]:
    """
    Description:
        Resolves and returns the target Discord user or channel destination.
        Attempts to resolve #agent-updates channel first, then user DM, then channel/guild text fallbacks.
    Usage:
        target = await get_discord_target()
    Usage Example:
        target = await get_discord_target()
    """
    if not state.bot or not state.bot.is_ready():
        return None
        
    # Prioritize #agent-updates channel if present in any guild
    for guild in state.bot.guilds:
        for chan in guild.text_channels:
            if chan.name == "agent-updates" and chan.permissions_for(guild.me).send_messages:
                return chan

    import bot
    discord_user_id = bot.DISCORD_USER_ID or os.getenv("DISCORD_USER_ID")
    discord_username = os.getenv("DISCORD_USER_NAME", "Tig1")
    discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
    
    target = None
    if discord_user_id:
        try:
            target = await state.bot.fetch_user(int(discord_user_id))
        except Exception:
            target = None
            
    if not target and discord_username:
        for u in state.bot.users:
            if u.name.lower() == discord_username.lower():
                target = u
                # Helper imports locally to avoid circular dependencies
                from web_server import update_env_file
                update_env_file(str(u.id))
                break
                
    if not target and discord_channel_id:
        try:
            target = state.bot.get_channel(int(discord_channel_id))
        except Exception:
            target = None
            
    if not target:
        for guild in state.bot.guilds:
            for chan in guild.text_channels:
                if chan.permissions_for(guild.me).send_messages:
                    target = chan
                    break
            if target:
                break
                
    return target


def resolve_target_and_payload(raw_request: dict) -> Tuple[str, dict, dict]:
    """
    Description:
        Resolves target URL, payload, and headers based on active state configurations
        (MODEL_PROVIDER, LOCAL_ENDPOINT, LOCAL_MODEL_NAME, etc.).
    Usage:
        target_url, payload, headers = resolve_target_and_payload(raw_request)
    Usage Example:
        url, pay, head = resolve_target_and_payload({"messages": []})
    """
    headers = {"Content-Type": "application/json"}
    
    if state.MODEL_PROVIDER == "ollama":
        base_url = state.LOCAL_ENDPOINT.rstrip("/")
        if not base_url.endswith("/chat/completions"):
            target_url = f"{base_url}/chat/completions"
        else:
            target_url = base_url
            
        payload = dict(raw_request)
        payload["model"] = state.LOCAL_MODEL_NAME
        
    else:  # gemini or any other remote/custom
        remote_base = state.REMOTE_ENDPOINT.strip() if state.REMOTE_ENDPOINT else "https://generativelanguage.googleapis.com/v1beta/openai"
        remote_base = remote_base.rstrip("/")
        if not remote_base.endswith("/chat/completions"):
            target_url = f"{remote_base}/chat/completions"
        else:
            target_url = remote_base
            
        payload = dict(raw_request)
        req_model = payload.get("model", "")
        if not req_model or (not req_model.startswith("gemini") and not state.REMOTE_ENDPOINT):
            payload["model"] = "gemini-2.5-flash"
            
        api_key = state.REMOTE_API_KEY.strip() if state.REMOTE_API_KEY else os.getenv("REMOTE_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            if "generativelanguage.googleapis.com" in target_url and "?" not in target_url:
                target_url = f"{target_url}?key={api_key}"
                
    return target_url, payload, headers


async def send_prompt_to_discord(convo_id: str, prompt: str):
    """
    Description:
        Sends the user's proxy prompt to the Discord target.
    Usage:
        await send_prompt_to_discord(convo_id, prompt)
    Usage Example:
        await send_prompt_to_discord("convo-123", "hello")
    """
    target = await get_discord_target()
    if not target:
        print("[API Proxy] No Discord target resolved to send prompt notification.")
        return
    
    seen_paths = set()
    cleaned_prompt, all_files = extract_and_prepare_files(prompt, seen_paths)
    
    convo_short = convo_id[:8] if convo_id else "unknown"
    header = f"💬 **[Proxy Prompt - `{convo_short}`]**\n"
    content = header + cleaned_prompt
    
    try:
        if len(content) > 1900:
            chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
            if all_files:
                await target.send(content=chunks[0], files=all_files)
            else:
                await target.send(content=chunks[0])
            for chunk in chunks[1:]:
                await target.send(content=chunk)
        else:
            if all_files:
                await target.send(content=content, files=all_files)
            else:
                await target.send(content=content)
    except Exception as e:
        print(f"[API Proxy] Failed to send prompt to Discord: {e}")


async def send_response_to_discord(convo_id: str, response_text: str):
    """
    Description:
        Sends the model's proxy response to the Discord target.
    Usage:
        await send_response_to_discord(convo_id, response_text)
    Usage Example:
        await send_response_to_discord("convo-123", "here is the response")
    """
    if not response_text.strip():
        return
        
    target = await get_discord_target()
    if not target:
        print("[API Proxy] No Discord target resolved to send response notification.")
        return
        
    seen_paths = set()
    cleaned_text, all_files = extract_and_prepare_files(response_text, seen_paths)
    
    convo_short = convo_id[:8] if convo_id else "unknown"
    header = f"🏆 **[Proxy Response - `{convo_short}`]**\n"
    content = header + cleaned_text
    
    try:
        if len(content) > 1900:
            chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
            if all_files:
                await target.send(content=chunks[0], files=all_files)
            else:
                await target.send(content=chunks[0])
            for chunk in chunks[1:]:
                await target.send(content=chunk)
        else:
            if all_files:
                await target.send(content=content, files=all_files)
            else:
                await target.send(content=content)
    except Exception as e:
        print(f"[API Proxy] Failed to send response to Discord: {e}")


@app.post("/v1/chat/completions")
async def chat_completions(raw_request: dict, request: Request):
    """
    Description:
        OpenAI-compatible chat completions proxy endpoint. Forwards request to local
        or remote LLM endpoints based on configuration and broadcasts prompt/response
        to the user's Discord channel.
    Usage:
        res = await chat_completions(raw_request, request)
    Usage Example:
        res = await chat_completions({"messages": []}, request)
    """
    convo_id = request.headers.get("x-conversation-id") or request.headers.get("x-session-id")
    if not convo_id:
        convo_id = raw_request.get("user")
    if not convo_id:
        convo_id = f"proxy-{uuid.uuid4()}"

    target_url, payload, headers = resolve_target_and_payload(raw_request)
    
    # Extract last user message and post to Discord
    user_msgs = [m for m in payload.get("messages", []) if m.get("role") == "user"]
    if user_msgs:
        last_user_prompt = user_msgs[-1].get("content")
        if last_user_prompt:
            asyncio.create_task(send_prompt_to_discord(convo_id, last_user_prompt))

    is_stream = payload.get("stream", False)
    
    if is_stream:
        async def stream_generator():
            accumulated_content = []
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    async with client.stream("POST", target_url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            err_text = await response.aread()
                            yield f"data: {json.dumps({'error': err_text.decode('utf-8', errors='ignore')})}\n\n".encode("utf-8")
                            return
                        
                        buffer = ""
                        async for chunk in response.aiter_bytes():
                            yield chunk
                            
                            buffer += chunk.decode("utf-8", errors="ignore")
                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                line = line.strip()
                                if line.startswith("data:"):
                                    data_content = line[5:].strip()
                                    if data_content == "[DONE]":
                                        continue
                                    try:
                                        parsed = json.loads(data_content)
                                        choices = parsed.get("choices", [])
                                        if choices:
                                            delta = choices[0].get("delta", {})
                                            content = delta.get("content")
                                            if content:
                                                accumulated_content.append(content)
                                    except Exception:
                                        pass
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n".encode("utf-8")
                finally:
                    # After stream concludes, dispatch the full response to Discord
                    final_response_text = "".join(accumulated_content)
                    if final_response_text:
                        asyncio.create_task(send_response_to_discord(convo_id, final_response_text))
                        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
        
    else:
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(target_url, json=payload, headers=headers)
                res_data = response.json()
                
                # Try to extract message content to notify Discord
                choices = res_data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    if content:
                        asyncio.create_task(send_response_to_discord(convo_id, content))
                        
                return JSONResponse(content=res_data, status_code=response.status_code)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to communicate with LLM provider: {e}")


@app.get("/v1/models")
async def list_models():
    """
    Description:
        OpenAI-compatible models list endpoint.
    Usage:
        res = await list_models()
    Usage Example:
        res = await list_models()
    """
    created_time = int(time.time())
    
    if state.MODEL_PROVIDER == "ollama":
        base_url = state.LOCAL_ENDPOINT.rstrip("/")
        if base_url.endswith("/v1"):
            models_url = f"{base_url}/models"
        else:
            models_url = f"{base_url}/v1/models"
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(models_url)
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
            
        return {
            "object": "list",
            "data": [
                {
                    "id": state.LOCAL_MODEL_NAME,
                    "object": "model",
                    "created": created_time,
                    "owned_by": "ollama"
                }
            ]
        }
    else:
        return {
            "object": "list",
            "data": [
                {
                    "id": "gemini-2.5-flash",
                    "object": "model",
                    "created": created_time,
                    "owned_by": "google"
                },
                {
                    "id": "gemini-2.5-pro",
                    "object": "model",
                    "created": created_time,
                    "owned_by": "google"
                }
            ]
        }
