"""
File: bot.py
Description:
    Discord Liaison Bot logic. Listens for user inputs, posts agent dashboards,
    manages approval and interaction threads, routes user requests to running
    agents, and coordinates states.
Author: Logan Kirkendall <Logan@LKAud.io>
"""

import os
import sys
import glob
import psutil
import datetime
import asyncio
import time
import json
import signal
from typing import Dict, Optional, List, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import discord
from discord.ext import commands, tasks

import state
import helpers
import discord_ui
import agent_manager
import web_server
import dashboard

# FastAPI app reference
app = web_server.app

# Expose sub-modules for backward compatibility
extract_and_prepare_files = helpers.extract_and_prepare_files
extract_and_prepare_embed_files = helpers.extract_and_prepare_embed_files
extract_files_from_dict_or_list = helpers.extract_files_from_dict_or_list
scan_active_processes = helpers.scan_active_processes
get_training_status_info = helpers.get_training_status_info
match_commands = helpers.match_commands
get_command_for_task = helpers.get_command_for_task
get_commands_for_session = helpers.get_commands_for_session
get_active_tasks_for_session = helpers.get_active_tasks_for_session
discover_agent_sessions = helpers.discover_agent_sessions
get_all_pending_items = helpers.get_all_pending_items
get_latest_log_data_for_session = helpers.get_latest_log_data_for_session
get_session_project = helpers.get_session_project
is_session_awaiting_approval = helpers.is_session_awaiting_approval
get_last_completed_action = helpers.get_last_completed_action
get_agent_emoji = helpers.get_agent_emoji
get_project_folder_path = helpers.get_project_folder_path
_is_port_in_use = helpers._is_port_in_use
check_pending_notifications = helpers.check_pending_notifications
is_dangerous_command = web_server.is_dangerous_command
update_env_file = web_server.update_env_file
poll_ls_for_approval = web_server.poll_ls_for_approval

ApprovalRequest = web_server.ApprovalRequest
ApprovalResponse = web_server.ApprovalResponse
MessageRequest = web_server.MessageRequest
InteractionRequest = web_server.InteractionRequest
InteractionResponse = web_server.InteractionResponse
TextInputModal = discord_ui.TextInputModal
DiscordInteractionView = discord_ui.DiscordInteractionView
DiscordFreeformInteractionView = discord_ui.DiscordFreeformInteractionView
DiscordApprovalView = discord_ui.DiscordApprovalView
DiscordPlanApprovalView = discord_ui.DiscordPlanApprovalView
AgentMessageModal = discord_ui.AgentMessageModal
AgentDetailView = discord_ui.AgentDetailView
AgentSpawnModal = discord_ui.AgentSpawnModal

run_spawned_agent = agent_manager.run_spawned_agent
send_agent_message = agent_manager.send_agent_message

# Module-level getters and setters for global variables redirecting to state.py
from types import ModuleType

class DynamicModule(ModuleType):
    """
    Description:
        Custom module class to dynamically redirect attribute reads and writes
        on the bot module to state.py, supporting unittest.mock.patch.
    Usage:
        sys.modules[__name__].__class__ = DynamicModule
    Usage Example:
        DynamicModule(__name__)
    """
    def __getattr__(self, name: str):
        if hasattr(state, name):
            return getattr(state, name)
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value):
        if name in [
            "bot", "pending_approvals", "pending_interactions", "active_text_prompts", 
            "active_pending_items", "START_TIME", "has_message_content", "dashboard_msg", 
            "dashboard_state", "IS_PAUSED", "PORT", "BRAIN_DIR", "REMOVER_DIR", 
            "MODEL_PROVIDER", "AUTO_SWITCH_LOCAL", "DISCORD_USER_ID", "DISCORD_BOT_TOKEN",
            "DISCORD_BOT_PERMISSIONS", "notified_pending_keys",
            "CLAUDE_API_KEY", "CLAUDE_MODEL_NAME",
            "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL_NAME",
            "GROQ_API_KEY", "GROQ_MODEL_NAME",
            "OPENROUTER_API_KEY", "OPENROUTER_MODEL_NAME",
            "TOGETHER_API_KEY", "TOGETHER_MODEL_NAME",
            "HF_API_KEY", "HF_MODEL_NAME",
            "OPENAI_API_KEY", "OPENAI_MODEL_NAME",
            "AGENT_ENDPOINT", "FORWARD_ENDPOINT", "LOCAL_ENDPOINT", "REMOTE_ENDPOINT",
            "AGENT_API_KEY", "FORWARD_API_KEY", "REMOTE_API_KEY",
            "AGENT_PROVIDER", "AGENT_MODEL_NAME", "LOCAL_MODEL_NAME"
        ]:
            setattr(state, name, value)
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name: str):
        try:
            if name in [
                "bot", "pending_approvals", "pending_interactions", "active_text_prompts", 
                "active_pending_items", "START_TIME", "has_message_content", "dashboard_msg", 
                "dashboard_state", "IS_PAUSED", "PORT", "BRAIN_DIR", "REMOVER_DIR", 
                "MODEL_PROVIDER", "AUTO_SWITCH_LOCAL", "DISCORD_USER_ID", "DISCORD_BOT_TOKEN",
                "DISCORD_BOT_PERMISSIONS", "notified_pending_keys",
                "CLAUDE_API_KEY", "CLAUDE_MODEL_NAME",
                "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL_NAME",
                "GROQ_API_KEY", "GROQ_MODEL_NAME",
                "OPENROUTER_API_KEY", "OPENROUTER_MODEL_NAME",
                "TOGETHER_API_KEY", "TOGETHER_MODEL_NAME",
                "HF_API_KEY", "HF_MODEL_NAME",
                "OPENAI_API_KEY", "OPENAI_MODEL_NAME",
                "AGENT_ENDPOINT", "FORWARD_ENDPOINT", "LOCAL_ENDPOINT", "REMOTE_ENDPOINT",
                "AGENT_API_KEY", "FORWARD_API_KEY", "REMOTE_API_KEY",
                "AGENT_PROVIDER", "AGENT_MODEL_NAME", "LOCAL_MODEL_NAME"
            ]:
                if hasattr(state, name):
                    delattr(state, name)
            else:
                super().__delattr__(name)
        except AttributeError:
            pass

sys.modules[__name__].__class__ = DynamicModule

# Background task to refresh the dashboard every 10 seconds
@tasks.loop(seconds=10.0)
async def dashboard_updater():
    """
    Description:
        Background loop task to update the dashboard periodically.
    """
    await update_dashboard()

# Background task to monitor the active agent's transcript and forward responses to Discord
@tasks.loop(seconds=2.0)
async def transcript_monitor():
    """
    Description:
        Background loop task to monitor active agent transcripts and route updates to #agent-updates or DMs.
    Usage:
        transcript_monitor.start()
    Usage Example:
        if not transcript_monitor.is_running():
            transcript_monitor.start()
    """
    global last_processed_steps, notified_plan_sessions
    if not state.bot or not state.bot.is_ready() or not os.getenv("DISCORD_USER_ID"):
        return
        
    try:
        sessions = discover_agent_sessions()
        if not sessions:
            return
            
        brain_dir = state.BRAIN_DIR
        DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")

        # Clean up stale notified plan sessions
        active_pending_plan_sessions = set()
        for s in sessions:
            c_id = s['convo_id']
            m_path = os.path.join(brain_dir, c_id, "implementation_plan.md.metadata.json")
            if os.path.exists(m_path):
                try:
                    with open(m_path, 'r') as f:
                        meta = json.load(f)
                    if meta.get("requestFeedback") is True:
                        active_pending_plan_sessions.add(c_id)
                except Exception:
                    pass
        notified_plan_sessions = notified_plan_sessions.intersection(active_pending_plan_sessions)

        # Check for pending implementation plans to prompt user via Discord buttons
        for s in sessions:
            c_id = s['convo_id']
            m_path = os.path.join(brain_dir, c_id, "implementation_plan.md.metadata.json")
            p_path = os.path.join(brain_dir, c_id, "implementation_plan.md")
            
            if os.path.exists(m_path) and os.path.exists(p_path):
                try:
                    with open(m_path, 'r') as f:
                        meta = json.load(f)
                    if meta.get("requestFeedback") is True:
                        if c_id not in notified_plan_sessions:
                            target = await web_server.get_discord_target()
                            if target:
                                embed = discord.Embed(
                                    title="📝 Implementation Plan Ready for Review",
                                    description=f"Agent in session `{c_id[:8]}` has generated an implementation plan for your approval.",
                                    color=discord.Color.from_rgb(245, 158, 11),
                                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                                )
                                embed.add_field(name="💼 Project", value=f"`{get_session_project(c_id)}`", inline=True)
                                embed.add_field(name="💬 Session ID", value=f"`{c_id[:8]}`", inline=True)
                                embed.add_field(name="📋 Summary", value=meta.get("summary", "No summary provided"), inline=False)
                                
                                file_to_attach = None
                                if os.path.exists(p_path) and os.path.isfile(p_path):
                                    file_to_attach = discord.File(p_path, filename=os.path.basename(p_path))
                                
                                view = DiscordPlanApprovalView(convo_id=c_id, metadata_path=m_path, plan_path=p_path)
                                await target.send(
                                    content=f"<@{DISCORD_USER_ID}> ⚠️ **Plan Approval Required!**",
                                    embed=embed,
                                    view=view,
                                    file=file_to_attach
                                )
                                
                                notified_plan_sessions.add(c_id)
                except Exception as plan_err:
                    print(f"[Transcript Monitor] Error checking plan for {c_id[:8]}: {plan_err}")
            
        for session in sessions:
            convo_id = session['convo_id']
            transcript_path = os.path.join(brain_dir, convo_id, ".system_generated", "logs", "transcript.jsonl")
            
            if not os.path.exists(transcript_path):
                continue
                
            try:
                with open(transcript_path, "r", errors="ignore") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"[Transcript Monitor] Error reading transcript for {convo_id[:8]}: {e}")
                continue
                
            if convo_id not in last_processed_steps:
                max_idx = -1
                for line in lines:
                    try:
                        data = json.loads(line)
                        step_idx = data.get('step_index')
                        if step_idx is not None and step_idx > max_idx:
                            max_idx = step_idx
                    except Exception:
                        continue
                last_processed_steps[convo_id] = max_idx
                print(f"[Transcript Monitor] Initialized tracking for session {convo_id[:8]} at step {max_idx}")
                continue
                
            last_idx = last_processed_steps[convo_id]
            new_steps = []
            max_step_in_file = last_idx
            
            for line in lines:
                try:
                    data = json.loads(line)
                    step_idx = data.get('step_index')
                    if step_idx is not None:
                        if step_idx > max_step_in_file:
                            max_step_in_file = step_idx
                        if step_idx > last_idx:
                            if data.get('source') == 'MODEL' and data.get('type') == 'PLANNER_RESPONSE':
                                tool_calls = data.get('tool_calls', [])
                                if not tool_calls:
                                    content = data.get('content', '')
                                    if not is_verbose_action_message(content):
                                        new_steps.append(data)
                except Exception:
                    continue
                    
            if new_steps:
                target = await web_server.get_discord_target()
                if target:
                    history_channel = target
                    if hasattr(target, "dm_channel"):
                        try:
                            history_channel = target.dm_channel or await target.create_dm()
                        except Exception as dm_err:
                            print(f"[Transcript Monitor] Error resolving target DM channel for history: {dm_err}")
                    
                    last_msg = None
                    try:
                        async for msg in history_channel.history(limit=5):
                            if msg.author == state.bot.user:
                                last_msg = msg
                                break
                    except Exception as e:
                        print(f"[Transcript Monitor] Failed to fetch history: {e}")
                    
                    for step in new_steps:
                        content = step.get('content', '').strip()
                        if not content:
                            continue
                        seen_paths = set()
                        content, content_files = extract_and_prepare_files(content, seen_paths)
                        
                        prefix = f"💬 **[Agent `{convo_id[:8]}`]**"
                        if not content_files and last_msg and last_msg.content.startswith(prefix):
                            potential_content = last_msg.content + "\n\n" + content
                            if len(potential_content) <= 1950:
                                try:
                                    await last_msg.edit(content=potential_content)
                                    last_msg.content = potential_content
                                    continue
                                except Exception:
                                    pass
                        
                        msg_to_send = f"{prefix}\n{content}"
                        if len(msg_to_send) > 1900:
                            chunks = [msg_to_send[i:i+1900] for i in range(0, len(msg_to_send), 1900)]
                            last_msg = await target.send(chunks[0], files=content_files if content_files else None)
                            for chunk in chunks[1:]:
                                last_msg = await target.send(chunk)
                        else:
                            last_msg = await target.send(msg_to_send, files=content_files if content_files else None)
                            
            if max_step_in_file > last_idx:
                last_processed_steps[convo_id] = max_step_in_file
    except Exception as e:
        print(f"[Transcript Monitor] Error in background monitor loop: {e}")

# Global tracking state for transcript monitor
last_processed_steps: Dict[str, int] = {}
notified_plan_sessions = set()

is_verbose_action_message = dashboard.is_verbose_action_message

import re

# Helper to scan for pending plans/approvals/interactions
@tasks.loop(minutes=5)
async def check_pending_loop():
    """
    Description:
        Background loop task checking for pending approvals.
    """
    await helpers.check_pending_notifications(is_launch=False)

build_dashboard_ui = dashboard.build_dashboard_ui
build_project_menu_ui = dashboard.build_project_menu_ui
update_dashboard = dashboard.update_dashboard
def create_bot(use_message_content: bool):
    """
    Description:
        Instantiates the Discord Client Bot and maps commands and event callbacks.
    """
    intents = discord.Intents.default()
    intents.message_content = use_message_content
    new_bot = commands.Bot(command_prefix="!", intents=intents)

    @new_bot.event
    async def on_ready():
        print(f"✅ Discord bot logged in as {new_bot.user} (ID: {new_bot.user.id})")
        invite_url = f"https://discord.com/oauth2/authorize?client_id={new_bot.user.id}&permissions={state.DISCORD_BOT_PERMISSIONS}&scope=bot%20applications.commands"
        print(f"🔗 Bot Invite URL: {invite_url}")
        
        DISCORD_USER_NAME = os.getenv("DISCORD_USER_NAME")
        if DISCORD_USER_NAME:
            for u in new_bot.users:
                if u.name.lower() == DISCORD_USER_NAME.lower():
                    print(f"🎯 Auto-detected user {DISCORD_USER_NAME} in cache! ID: {u.id}")
                    state.DISCORD_USER_ID = str(u.id)
                    web_server.update_env_file(state.DISCORD_USER_ID)
                    break
        
        DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
        if DISCORD_USER_ID and not getattr(state, "FORCE_SERVER_CHAT", False):
            try:
                user = await new_bot.fetch_user(int(DISCORD_USER_ID))
                dm_channel = user.dm_channel or await user.create_dm()
                print(f"[Bot] Cleaning up DM history with {user.name}...")
                async for msg in dm_channel.history(limit=100):
                    if msg.author == new_bot.user:
                        try:
                            await msg.delete()
                        except Exception:
                            pass
            except Exception as e:
                print(f"[Bot] Error purging DM history: {e}")

        if not dashboard_updater.is_running():
            dashboard_updater.start()
        if not transcript_monitor.is_running():
            transcript_monitor.start()
        if not check_pending_loop.is_running():
            check_pending_loop.start()

    @new_bot.event
    async def on_message(message):
        """
        Description:
            Event listener triggered on every incoming Discord message.
            Handles registration, user prompts routing, and command execution.
        Usage:
            Triggered automatically by discord.py.
        Usage Example:
            await on_message(message)
        """
        if message.author.bot:
            return

        # Restrict guild message processing: channel name must be "agent-discussion" or a thread parented by it
        if message.guild is not None:
            is_discussion = False
            if isinstance(message.channel, discord.Thread):
                parent_channel = message.channel.parent
                if parent_channel and parent_channel.name == "agent-discussion":
                    is_discussion = True
            elif message.channel.name == "agent-discussion":
                is_discussion = True
            
            if not is_discussion:
                return

        DISCORD_USER_NAME = os.getenv("DISCORD_USER_NAME")
        if DISCORD_USER_NAME and message.author.name.lower() == DISCORD_USER_NAME.lower():
            author_id = str(message.author.id)
            if os.getenv("DISCORD_USER_ID") != author_id:
                print(f"[Bot] Auto-registering user {DISCORD_USER_NAME} with ID: {author_id}")
                web_server.update_env_file(author_id)
                os.environ["DISCORD_USER_ID"] = author_id
                state.DISCORD_USER_ID = author_id
                try:
                    await message.channel.send(f"🎯 **Registered!** Hello {DISCORD_USER_NAME}, I have linked your Discord account (ID: `{author_id}`) for agent approvals.")
                    if not dashboard_updater.is_running():
                        dashboard_updater.start()
                    if not transcript_monitor.is_running():
                        transcript_monitor.start()
                    if not check_pending_loop.is_running():
                        check_pending_loop.start()
                except Exception as e:
                    print(f"Error confirmation registration: {e}")

        # Enforce registered user constraints
        registered_id = os.getenv("DISCORD_USER_ID")
        author_id = str(message.author.id)
        if not registered_id or author_id != registered_id:
            return

        if author_id in state.active_text_prompts:
            fut = state.active_text_prompts.pop(author_id)
            if not fut.done():
                fut.set_result({
                    "selected_option_ids": [],
                    "freeform_response": message.content,
                    "skipped": False
                })
            try:
                await message.channel.send("✅ Response recorded.")
            except Exception:
                pass
            return

        if not message.content.startswith("!"):
            import uuid
            # Check if this is a guild text channel (server)
            if message.guild is not None:
                # Case A: Message is already inside a thread
                if isinstance(message.channel, discord.Thread):
                    thread_name = message.channel.name
                    convo_id = None
                    if "session-" in thread_name:
                        short_id = thread_name.split("session-")[-1].strip()
                        sessions = discover_agent_sessions()
                        for s in sessions:
                            if s["convo_id"].startswith(short_id):
                                convo_id = s["convo_id"]
                                break
                    
                    if convo_id:
                        sessions = discover_agent_sessions()
                        active_sessions = [s for s in sessions if s.get('status') == 'Active' and s['convo_id'] == convo_id]
                        if active_sessions:
                            # Route to the active thread session
                            success = send_agent_message(convo_id, message.content)
                            if success:
                                await message.channel.send(f"📬 **Prompt routed to active thread agent:** {message.content}")
                                return
                        # If the session went idle/stopped, spawn another run using the SAME conversation ID to continue
                        asyncio.create_task(run_spawned_agent(message.content, message.channel, convo_id=convo_id))
                    else:
                        # Fallback: spawn new session in this thread
                        new_convo_id = str(uuid.uuid4())
                        asyncio.create_task(run_spawned_agent(message.content, message.channel, convo_id=new_convo_id))
                
                # Case B: Message is in a normal text channel -> create a new thread
                else:
                    new_convo_id = str(uuid.uuid4())
                    try:
                        # Create a public thread started from the message
                        thread = await message.create_thread(name=f"🤖 session-{new_convo_id[:8]}", auto_archive_duration=60)
                        await thread.send(f"🚀 **Started new agent session** (`{new_convo_id[:8]}`). Executing agent...")
                        asyncio.create_task(run_spawned_agent(message.content, thread, convo_id=new_convo_id))
                    except Exception as e:
                        # Fallback to normal execution in current channel
                        print(f"[Bot] Failed to create thread: {e}")
                        asyncio.create_task(run_spawned_agent(message.content, message.channel, convo_id=new_convo_id))
            
            # Case C: DM Channel
            else:
                sessions = discover_agent_sessions()
                active_sessions = [s for s in sessions if s.get('status') == 'Active']
                if active_sessions:
                    target_session = active_sessions[0]
                    convo_id = target_session['convo_id']
                    goal_name = target_session['goal_name']
                    success = send_agent_message(convo_id, message.content)
                    if success:
                        await message.channel.send(f"📬 **Prompt routed to active agent `{convo_id[:8]}` ({goal_name[:30]}):** {message.content}")
                    else:
                        await message.channel.send(f"❌ Failed to route prompt to active agent `{convo_id[:8]}`. Spawning new session instead...")
                        asyncio.create_task(run_spawned_agent(message.content, message.channel))
                else:
                    asyncio.create_task(run_spawned_agent(message.content, message.channel))

        await new_bot.process_commands(message)

    if use_message_content:
        @new_bot.command(name="status")
        async def status_command(ctx):
            await ctx.send("🔍 Fetching status details...")
            status_msg = get_training_status_info()
            if len(status_msg) > 2000:
                await ctx.send(status_msg[:1990] + "\n...")
            else:
                await ctx.send(status_msg)

        @new_bot.command(name="updates")
        async def updates_command(ctx):
            now = time.time()
            remover_dir = state.REMOVER_DIR
            recent_files = []
            if os.path.exists(remover_dir):
                for root, dirs, files in os.walk(remover_dir):
                    if ".venv" in root or ".git" in root or "build" in root or "__pycache__" in root:
                        continue
                    for f in files:
                        fpath = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(fpath)
                            if now - mtime < 7200:
                                rel = os.path.relpath(fpath, remover_dir)
                                recent_files.append((rel, mtime))
                        except Exception:
                            continue
                            
            msg = "📂 **Recent Updates in OpenFeedbackRemover (Last 2 hours):**\n"
            if recent_files:
                recent_files.sort(key=lambda x: x[1], reverse=True)
                for name, mtime in recent_files[:15]:
                    dt = datetime.datetime.fromtimestamp(mtime)
                    msg += f"• `{name}` — {dt.strftime('%H:%M:%S')}\n"
            else:
                msg += "No files modified in the last 2 hours.\n"
            await ctx.send(msg)

        @new_bot.command(name="spawn")
        async def spawn_command(ctx, *, prompt: str):
            asyncio.create_task(run_spawned_agent(prompt, ctx.channel))

        @new_bot.command(name="clear")
        async def clear_command(ctx):
            """
            Description:
                Deletes previous messages in the current text channel.
                Uses purge for guild channels, and deletes bot-sent messages individually for DM channels.
            Usage:
                !clear
            Usage Example:
                !clear
            """
            status_msg = await ctx.send("🧹 **Clearing message history...**")
            
            if hasattr(ctx.channel, "purge"):
                try:
                    def check_not_dashboard(m):
                        if state.dashboard_msg and m.id == state.dashboard_msg.id:
                            return False
                        if m.id == status_msg.id:
                            return False
                        return True
                    await ctx.channel.purge(limit=100, check=check_not_dashboard)
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                    return
                except Exception as e:
                    print(f"[Bot] Purge failed: {e}")
            
            try:
                async for msg in ctx.channel.history(limit=100):
                    if msg.id == status_msg.id:
                        continue
                    if state.dashboard_msg and msg.id == state.dashboard_msg.id:
                        continue
                    if msg.author.id == new_bot.user.id:
                        try:
                            await msg.delete()
                        except Exception:
                            pass
                try:
                    await status_msg.delete()
                except Exception:
                    pass
            except Exception as e:
                print(f"[Bot] DM clear failed: {e}")

        @new_bot.command(name="commands")
        async def help_command(ctx):
            embed = discord.Embed(
                title="🤖 Antigravity Bot Commands",
                description="Here are the commands you can run over Discord:",
                color=discord.Color.blue()
            )
            embed.add_field(name="`!spawn <prompt>`", value="Spawns a new background agent to execute the given prompt.", inline=False)
            embed.add_field(name="`!status`", value="Checks active training processes and outputs the latest training epoch logs.", inline=False)
            embed.add_field(name="`!updates`", value="Lists any files in OpenFeedbackRemover modified in the last 2 hours.", inline=False)
            embed.add_field(name="`!clear`", value="Clears previous bot messages in this channel.", inline=False)
            embed.add_field(name="`!commands`", value="Shows this help menu.", inline=False)
            await ctx.send(embed=embed)

    return new_bot

def check_single_instance():
    """
    Description:
        Checks if another python process running bot.py is already active on the system.
        If another instance is found, print an error and exit with code 1.
    Usage:
        check_single_instance()
    Usage Example:
        check_single_instance()
    """
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.pid == current_pid:
                continue
            name = proc.info.get('name') or ''
            if 'python' in name.lower():
                cmd = proc.cmdline()
                if any(arg.endswith('bot.py') for arg in cmd):
                    print(f"❌ Error: Another instance of the Discord Liaison Bot is already running (PID: {proc.pid}).")
                    print("Ensure only one daemon instance is active at a time to prevent token session conflicts.")
                    sys.exit(1)
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            continue

async def main():
    """
    Description:
        Main entry point to launch the web status server and the Discord Bot client.
    """
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN environment variable not set.")
        return

    server_task = None
    ssl_server_task = None
    if _is_port_in_use(state.PORT):
        print(f"⚠️ [Bot] Port {state.PORT} already in use — running in secondary-client mode (Discord-only, no HTTP server).")
    else:
        config = uvicorn.Config(app, host="127.0.0.1", port=state.PORT, log_level="info")
        server = uvicorn.Server(config)
        print(f"🚀 Starting FastAPI server on http://127.0.0.1:{state.PORT}")
        server_task = asyncio.create_task(server.serve())
    
        cert_dir = state.APP_DATA_DIR
        cert_path = os.path.join(cert_dir, "cert.pem")
        key_path = os.path.join(cert_dir, "key.pem")
        
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            import subprocess
            try:
                os.makedirs(cert_dir, exist_ok=True)
                subprocess.run([
                    "openssl", "req", "-x509", "-newkey", "rsa:2048", 
                    "-keyout", key_path, "-out", cert_path, "-sha256", 
                    "-days", "365", "-nodes", "-subj", "/CN=localhost"
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("[Bot] Generated self-signed SSL certificate.")
            except Exception as e:
                print(f"[Bot] Failed to generate SSL certificate: {e}")
                
        if os.path.exists(cert_path) and os.path.exists(key_path):
            if _is_port_in_use(state.PORT + 1):
                print(f"⚠️ [Bot] HTTPS port {state.PORT + 1} already in use — not starting HTTPS server.")
            else:
                try:
                    ssl_config = uvicorn.Config(
                        app, host="127.0.0.1", port=state.PORT + 1, 
                        ssl_keyfile=key_path, ssl_certfile=cert_path, 
                        log_level="info"
                    )
                    ssl_server = uvicorn.Server(ssl_config)
                    ssl_server_task = asyncio.create_task(ssl_server.serve())
                    print(f"🚀 Starting HTTPS server on https://127.0.0.1:{state.PORT + 1}")
                except Exception as e:
                    print(f"[Bot] Failed to start HTTPS server: {e}")

    print("🔌 Connecting Discord bot...")
    
    try:
        state.bot = create_bot(use_message_content=True)
        await state.bot.start(DISCORD_BOT_TOKEN)
    except discord.errors.PrivilegedIntentsRequired:
        print("\n⚠️ PRIVILEGED INTENT ERROR: Message Content Intent is not enabled on the Discord Developer Portal.")
        print("Attempting to connect with fallback intents (no message content)...")
        
        state.has_message_content = False
        state.bot = create_bot(use_message_content=False)
        await state.bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    try:
        check_single_instance()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down servers...")
