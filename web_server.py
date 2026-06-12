import os
import time
import uuid
import json
import datetime
import asyncio
from typing import Dict, Optional, List, Tuple
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import discord
import httpx

import state
import helpers
from proxy_routes import resolve_target_and_payload, translate_claude_response_to_openai

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

from schemas import ApprovalRequest, ApprovalResponse, MessageRequest, InteractionRequest, InteractionResponse, SettingsRequest

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
        "display_name": "Discord Liaison",
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
        "discord_bot_permissions": state.DISCORD_BOT_PERMISSIONS,
        "force_server_chat": int(state.FORCE_SERVER_CHAT)
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
    if req.model_provider is not None:
        state.MODEL_PROVIDER = req.model_provider
    if req.agent_provider is not None:
        state.AGENT_PROVIDER = req.agent_provider
    if req.auto_switch_local is not None:
        state.AUTO_SWITCH_LOCAL = req.auto_switch_local
    if req.discord_bot_permissions is not None:
        state.DISCORD_BOT_PERMISSIONS = req.discord_bot_permissions
    if req.force_server_chat is not None:
        state.FORCE_SERVER_CHAT = bool(req.force_server_chat)
    if req.force_only_server is not None:
        state.FORCE_SERVER_CHAT = bool(req.force_only_server)
    
    # Dynamically apply settings properties to state module
    for key in [
        "claude_api_key", "claude_model_name",
        "deepseek_api_key", "deepseek_model_name",
        "groq_api_key", "groq_model_name",
        "openrouter_api_key", "openrouter_model_name",
        "together_api_key", "together_model_name",
        "hf_api_key", "hf_model_name",
        "openai_api_key", "openai_model_name",
        "custom_api_key", "custom_model_name", "custom_endpoint",
        "agent_endpoint", "forward_endpoint", "agent_api_key", "forward_api_key",
        "agent_provider", "agent_model_name", "local_model_name", "force_server_chat", "force_only_server"
    ]:
        val = getattr(req, key)
        if val is not None:
            if key in ("force_server_chat", "force_only_server"):
                state.FORCE_SERVER_CHAT = bool(val)
            else:
                setattr(state, key.upper(), val)
            
    update_settings_in_env(req)
    print(f"[API] Settings updated: provider={state.MODEL_PROVIDER}, auto_switch={state.AUTO_SWITCH_LOCAL}, permissions={state.DISCORD_BOT_PERMISSIONS}, force_server_chat={state.FORCE_SERVER_CHAT}")
    return {
        "status": "success", 
        "model_provider": state.MODEL_PROVIDER, 
        "auto_switch_local": state.AUTO_SWITCH_LOCAL,
        "discord_bot_permissions": state.DISCORD_BOT_PERMISSIONS,
        "force_server_chat": int(state.FORCE_SERVER_CHAT),
        "force_only_server": int(state.FORCE_SERVER_CHAT)
    }

@app.post("/api/restart-daemon")
async def post_restart_daemon(background_tasks: BackgroundTasks):
    """
    Description:
        Endpoint to restart the Discord liaison daemon process. Exits the process,
        allowing the process supervisor (like launchd or Docker) to restart it automatically.
    Usage:
        res = await post_restart_daemon(background_tasks)
    Usage Example:
        res = await post_restart_daemon(background_tasks)
    """
    print("[API] Daemon restart requested. Exiting in 1 second...")
    def shutdown():
        time.sleep(1.0)
        os._exit(0)
    background_tasks.add_task(shutdown)
    return {"status": "success", "message": "Restarting daemon..."}

@app.get("/status")
async def get_status_ui():
    """
    Description:
        FastAPI endpoint to render the HTML status dashboard page by delegating to status_ui module.
    Usage:
        res = await get_status_ui()
    Usage Example:
        res = await get_status_ui()
    """
    import status_ui
    return await status_ui.get_status_ui()

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

def update_settings_in_env(req: SettingsRequest):
    """
    Description:
        Updates the config.json and .env files with the Model Provider, Auto Switch Local, Bot Permissions settings,
        and all individual provider API keys, model names, and endpoints.
    Usage:
        update_settings_in_env(req)
    Usage Example:
        update_settings_in_env(req)
    """
    # 1. Update config.json
    config_path = state.CONFIG_PATH
    try:
        config_data = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = json.load(f)
        if req.model_provider is not None:
            config_data["model_provider"] = req.model_provider
        if req.auto_switch_local is not None:
            config_data["auto_switch_local"] = req.auto_switch_local
        if req.discord_bot_permissions is not None:
            config_data["discord_bot_permissions"] = req.discord_bot_permissions
        
        # Set all provider configs in config.json
        for key in [
            "claude_api_key", "claude_model_name",
            "deepseek_api_key", "deepseek_model_name",
            "groq_api_key", "groq_model_name",
            "openrouter_api_key", "openrouter_model_name",
            "together_api_key", "together_model_name",
            "hf_api_key", "hf_model_name",
            "openai_api_key", "openai_model_name",
            "custom_api_key", "custom_model_name", "custom_endpoint",
            "agent_endpoint", "forward_endpoint", "agent_api_key", "forward_api_key",
            "agent_provider", "agent_model_name", "local_model_name", "force_server_chat", "force_only_server"
        ]:
            val = getattr(req, key)
            if val is not None:
                config_data[key] = val
                
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        print(f"[Bot] Successfully updated config.json with all provider settings")
    except Exception as e:
        print(f"[Bot] Failed to update config.json: {e}")

    # 2. Update .env file
    env_path = state.ENV_PATH
    try:
        env_dict = {}
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        env_dict[k.strip()] = v.strip()
                        
        if req.model_provider is not None:
            env_dict["MODEL_PROVIDER"] = req.model_provider
        if req.agent_provider is not None:
            env_dict["AGENT_PROVIDER"] = req.agent_provider
        if req.auto_switch_local is not None:
            env_dict["AUTO_SWITCH_LOCAL"] = str(req.auto_switch_local)
        if req.discord_bot_permissions is not None:
            env_dict["DISCORD_BOT_PERMISSIONS"] = req.discord_bot_permissions
        
        # Map to uppercase keys in .env
        for key in [
            "claude_api_key", "claude_model_name",
            "deepseek_api_key", "deepseek_model_name",
            "groq_api_key", "groq_model_name",
            "openrouter_api_key", "openrouter_model_name",
            "together_api_key", "together_model_name",
            "hf_api_key", "hf_model_name",
            "openai_api_key", "openai_model_name",
            "custom_api_key", "custom_model_name", "custom_endpoint",
            "agent_endpoint", "forward_endpoint", "agent_api_key", "forward_api_key",
            "agent_provider", "agent_model_name", "local_model_name", "force_server_chat", "force_only_server"
        ]:
            val = getattr(req, key)
            if val is not None:
                if key == "force_only_server":
                    env_dict["FORCE_ONLY_SERVER"] = str(val)
                else:
                    env_dict[key.upper()] = val
                
        new_lines = []
        for k, v in env_dict.items():
            new_lines.append(f"{k}={v}")
            
        with open(env_path, "w") as f:
            f.write("\n".join(new_lines) + "\n")
        print(f"[Bot] Successfully updated .env file with all provider settings")
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
    
    if not getattr(state, "FORCE_SERVER_CHAT", False):
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
            for name_opt in ["agent-updates", "agent-discussion"]:
                for chan in guild.text_channels:
                    if chan.name == name_opt and chan.permissions_for(guild.me).send_messages:
                        target = chan
                        target_type = "channel"
                        break
                if target:
                    break
            if target:
                break

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
    
    if not getattr(state, "FORCE_SERVER_CHAT", False):
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
            for name_opt in ["agent-updates", "agent-discussion"]:
                for chan in guild.text_channels:
                    if chan.name == name_opt and chan.permissions_for(guild.me).send_messages:
                        target = chan
                        target_type = "channel"
                        break
                if target:
                    break
            if target:
                break

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
    
    # Skip DM targets if forcing server chat only
    if not getattr(state, "FORCE_SERVER_CHAT", False):
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
                if chan.name == "agent-discussion" and chan.permissions_for(guild.me).send_messages:
                    target = chan
                    break
            if target:
                break

    if not target:
        for guild in state.bot.guilds:
            for chan in guild.text_channels:
                if chan.permissions_for(guild.me).send_messages:
                    target = chan
                    break
            if target:
                break
    return target




import proxy_routes
app.include_router(proxy_routes.router)
