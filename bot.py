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
            "notified_pending_keys",
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
                "notified_pending_keys",
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

def is_verbose_action_message(content: str) -> bool:
    """
    Description:
        Determines if an agent planner response is a verbose background command description.
    Usage:
        verbose = is_verbose_action_message(content)
    Usage Example:
        v = is_verbose_action_message("I will run command...")
    """
    if not content:
        return True
    c_lower = content.lower()
    if re.match(r"^\s*i\s+will\s+(?:view|run|check|execute|call|list|search|replace|write|pause|wait|commit|stage|merge|tag|pytest|attempt|be)\b", c_lower):
        return True
    patterns = [
        "schedule", "timer", "reminder", "polling", "monitoring",
        "checking progress", "wait for", "waiting for", "check if", 
        "will run", "running command", "going to check", "will now check",
        "let's wait", "sleeping", "sleep for", "polling loop",
        "background task", "checking the status", "completed execution",
        "implementation plan", "please review", "let me know if you approve",
        "i will pause", "i will wait", "pause and wait", "tool call",
        "only call", "first tool call", "let's call", "no other calls",
        "schedule anything", "wake me up", "let's do it"
    ]
    clear_verbose_indicators = [
        "scheduled a", "timer to monitor", "training progress", "evaluation script",
        "background task", "polling loop", "once training is complete",
        "i will pause", "i will wait", "pause and wait", "tool call",
        "only call", "first tool call", "let's call", "no other calls",
        "schedule anything", "wake me up", "let's do it", "i will view",
        "i will check", "i will run", "i will list", "i will search",
        "i will replace", "i will write", "i will execute", "i will attempt"
    ]
    for ind in clear_verbose_indicators:
        if ind in c_lower:
            return True
    if len(content) > 250:
        return False
    for pat in patterns:
        if pat in c_lower:
            return True
    return False

import re

# Helper to scan for pending plans/approvals/interactions
@tasks.loop(minutes=5)
async def check_pending_loop():
    """
    Description:
        Background loop task checking for pending approvals.
    """
    await helpers.check_pending_notifications(is_launch=False)

def build_dashboard_ui() -> tuple[discord.Embed, discord.ui.View]:
    """
    Description:
        Builds the main dashboard embed and project button views.
    """
    sessions = discover_agent_sessions()
    processes = scan_active_processes()
    feedback_session = None
    for s in sessions:
        if "Phase Stability" in s['goal_name'] or "Feedback" in s['goal_name']:
            feedback_session = s
            break
            
    log_data = get_latest_log_data_for_session(feedback_session) if feedback_session else None
    pending_plans, pending_approvals_list, pending_interactions_list = get_all_pending_items()
    awaiting_count = len(pending_plans) + len(pending_approvals_list) + len(pending_interactions_list)
    desc = "Real-time status of running tasks and executing agents across all projects."
    color = discord.Color.from_rgb(99, 102, 241)
    if awaiting_count > 0:
        desc = f"⚠️ **Attention: {awaiting_count} agent(s) actively awaiting user approval!**\n\n" + desc
        color = discord.Color.from_rgb(245, 158, 11)

    embed = discord.Embed(
        title="🖥️ Multi-Agent System Dashboard",
        description=desc,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    if processes:
        proc_lines = []
        for idx, p in enumerate(processes, start=1):
            num_emoji = f"{idx}️⃣" if idx <= 10 else f"{idx}."
            proc_lines.append(f"{num_emoji} **PID `{p['pid']}`**: `{os.path.basename(p['cmd'].split()[-1])}`")
        embed.add_field(name="🔥 Active Shell Processes (Tasks)", value="\n".join(proc_lines), inline=False)
        
        if log_data and log_data['epoch'] != "N/A":
            embed.add_field(name="📈 Training Progress (OpenFeedbackRemover)", value=(
                f"• **Epoch:** `{log_data['epoch']}/60`\n"
                f"• **Train Loss:** `{log_data['train_loss']}`\n"
                f"• **Val Loss:** `{log_data['val_loss']}`\n"
                f"• **Val Acc:** `{log_data['val_acc']}`"
            ), inline=False)
            
    last_update_text = "No recent updates"
    if sessions:
        sorted_sessions = sorted(sessions, key=lambda s: s.get('latest_mtime', 0), reverse=True)
        most_recent = sorted_sessions[0]
        convo_id = most_recent['convo_id']
        proj = get_session_project(convo_id)
        action = get_last_completed_action(convo_id)
        last_update_text = f"**Project `{proj}`** (Session `{convo_id[:8]}`):\n└─ {action}"
    embed.add_field(name="🕒 Last Update", value=last_update_text, inline=False)

    if pending_plans or pending_approvals_list or pending_interactions_list:
        pending_lines = []
        for p in pending_plans:
            pending_lines.append(f"• 📝 **Plan**: `{p['project_name']}` (Session `{p['convo_id'][:8]}`) - *{p['summary']}*")
        for a in pending_approvals_list:
            pending_lines.append(f"• 🛡️ **Perm**: `{a['project_name']}` (Session `{a['convo_id'][:8]}`) - Approval required for `{a['tool_name']}`")
        for i in pending_interactions_list:
            questions_str = ", ".join([f'"{q}"' for q in i['questions']])
            pending_lines.append(f"• ❓ **Input**: `{i['project_name']}` (Session `{i['convo_id'][:8]}`) - Interaction: {questions_str}")
        
        pending_val = "\n".join(pending_lines)
        if len(pending_val) > 1000:
            pending_val = pending_val[:1000] + "\n... (truncated)"
        embed.add_field(name="⚠️ Actions Required (Waiting for User)", value=pending_val, inline=False)

    project_sessions = {}
    for s in sessions:
        proj = get_session_project(s['convo_id'])
        if proj not in project_sessions:
            project_sessions[proj] = []
        project_sessions[proj].append(s)
        
    agents_text = ""
    sorted_projects = sorted(project_sessions.keys(), key=lambda p: (p == "Global", p))
    for proj in sorted_projects:
        proj_s = project_sessions[proj]
        active_count = sum(1 for s in proj_s if s['status'] == 'Active')
        idle_count = sum(1 for s in proj_s if s['status'] == 'Idle')
        agents_text += f"📁 **Project: {proj}** ({active_count} active, {idle_count} idle)\n"
        for idx, s in enumerate(proj_s[:5]):
            person_emoji = get_agent_emoji(s['goal_name'], idx)
            awaiting_str = " ⚠️ *(Awaiting user approval)*" if is_session_awaiting_approval(s['convo_id'], pending_plans, pending_approvals_list, pending_interactions_list) else ""
            if s['status'] == 'Active':
                elapsed = int(time.time() - s['latest_mtime'])
                agents_text += f"  🟢 **Session `{s['convo_id'][:8]}`**: {s['goal_name']} *(Active {elapsed}s ago)*{awaiting_str}\n"
            else:
                dt = datetime.datetime.fromtimestamp(s['latest_mtime']) if s['latest_mtime'] else None
                time_str = dt.strftime('%m-%d %H:%M') if dt else "Never"
                agents_text += f"  💤 **Session `{s['convo_id'][:8]}`**: {s['goal_name']} *(Last active: {time_str})*{awaiting_str}\n"
        if len(proj_s) > 5:
            agents_text += f"  *...and {len(proj_s) - 5} more sessions. Click button below to view.*\n"
        agents_text += "\n"
            
    if not agents_text:
        agents_text = "No agent sessions found."
    if len(agents_text) > 1000:
        agents_text = agents_text[:1000] + "\n... (truncated)"
    embed.add_field(name="🤖 Agent Statuses", value=agents_text, inline=False)
    embed.set_footer(text="Dashboard auto-updates every 10s | Click project button below to view sessions")

    view = discord.ui.View(timeout=None)
    for i, proj in enumerate(sorted_projects):
        if i >= 23:
            break
        btn_label = proj[:20] + "..." if len(proj) > 20 else proj
        btn = discord.ui.Button(
            label=f"📁 {btn_label}", 
            style=discord.ButtonStyle.secondary, 
            custom_id=f"dash_proj_{proj[:20]}"
        )
        
        def make_proj_callback(proj_name):
            async def callback(interaction: discord.Interaction):
                await interaction.response.defer()
                state.dashboard_state["view"] = "project"
                state.dashboard_state["project"] = proj_name
                await update_dashboard()
            return callback
            
        btn.callback = make_proj_callback(proj)
        view.add_item(btn)
        
    if processes:
        btn_kill = discord.ui.Button(label="Stop Active Task 🛑", style=discord.ButtonStyle.danger, custom_id="dash_proj_kill")
        async def kill_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            procs = scan_active_processes()
            if procs:
                pid = procs[0]['pid']
                try:
                    os.kill(pid, signal.SIGTERM)
                    await interaction.followup.send(content=f"✅ Process `{pid}` terminated successfully.", ephemeral=True)
                    await update_dashboard()
                except Exception as e:
                    await interaction.followup.send(content=f"❌ Failed to terminate process: {e}", ephemeral=True)
            else:
                await interaction.followup.send(content="❌ No active processes found to stop.", ephemeral=True)
        btn_kill.callback = kill_callback
        view.add_item(btn_kill)
        
    btn_refresh = discord.ui.Button(label="Refresh 🔄", style=discord.ButtonStyle.primary, custom_id="dash_proj_refresh")
    async def refresh_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        await update_dashboard()
    btn_refresh.callback = refresh_callback
    view.add_item(btn_refresh)
    
    return embed, view

def build_project_menu_ui(project_name: str) -> tuple[discord.Embed, discord.ui.View]:
    """
    Description:
        Builds the project-specific submenu embed and button views.
    """
    sessions = discover_agent_sessions()
    processes = scan_active_processes()
    
    feedback_session = None
    for s in sessions:
        if get_session_project(s['convo_id']) == project_name:
            if "Phase Stability" in s['goal_name'] or "Feedback" in s['goal_name']:
                feedback_session = s
                break
                
    log_data = get_latest_log_data_for_session(feedback_session) if feedback_session else None
    embed = discord.Embed(
        title=f"📁 Project: {project_name}",
        description="Select an agent session/conversation to view detailed status, logs, or interact.",
        color=discord.Color.from_rgb(99, 102, 241),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    if processes:
        proc_lines = []
        for idx, p in enumerate(processes, start=1):
            num_emoji = f"{idx}️⃣" if idx <= 10 else f"{idx}."
            proc_lines.append(f"{num_emoji} **PID `{p['pid']}`**: `{os.path.basename(p['cmd'].split()[-1])}`")
        embed.add_field(name="🔥 Active Shell Processes (Tasks)", value="\n".join(proc_lines), inline=False)
        
        if log_data and log_data['epoch'] != "N/A":
            embed.add_field(name="📈 Training Progress (OpenFeedbackRemover)", value=(
                f"• **Epoch:** `{log_data['epoch']}/60`\n"
                f"• **Train Loss:** `{log_data['train_loss']}`\n"
                f"• **Val Loss:** `{log_data['val_loss']}`\n"
                f"• **Val Acc:** `{log_data['val_acc']}`"
            ), inline=False)
            
    pending_plans, pending_approvals_list, pending_interactions_list = get_all_pending_items()
    project_pending_plans = [p for p in pending_plans if p['project_name'] == project_name]
    project_pending_approvals = [a for a in pending_approvals_list if a['project_name'] == project_name]
    project_pending_interactions = [i for i in pending_interactions_list if i['project_name'] == project_name]
    
    if project_pending_plans or project_pending_approvals or project_pending_interactions:
        pending_lines = []
        for p in project_pending_plans:
            pending_lines.append(f"• 📝 **Plan**: Session `{p['convo_id'][:8]}` - *{p['summary']}*")
        for a in project_pending_approvals:
            pending_lines.append(f"• 🛡️ **Perm**: Session `{a['convo_id'][:8]}` - Approval required for `{a['tool_name']}`")
        for i in project_pending_interactions:
            questions_str = ", ".join([f'"{q}"' for q in i['questions']])
            pending_lines.append(f"• ❓ **Input**: Session `{i['convo_id'][:8]}` - Interaction: {questions_str}")
        
        pending_val = "\n".join(pending_lines)
        if len(pending_val) > 1000:
            pending_val = pending_val[:1000] + "\n... (truncated)"
        embed.add_field(name="⚠️ Actions Required (Waiting for User)", value=pending_val, inline=False)

    project_sessions = [s for s in sessions if get_session_project(s['convo_id']) == project_name]
    active_agents = [s for s in project_sessions if s['status'] == "Active"]
    idle_agents = [s for s in project_sessions if s['status'] == "Idle"]
    
    agents_text = ""
    if active_agents:
        agents_text += "**🟢 Executing Agents:**\n"
        for idx, a in enumerate(active_agents):
            person_emoji = get_agent_emoji(a['goal_name'], idx)
            elapsed = int(time.time() - a['latest_mtime'])
            awaiting_str = " ⚠️ *(Awaiting user approval)*" if is_session_awaiting_approval(a['convo_id'], pending_plans, pending_approvals_list, pending_interactions_list) else ""
            agents_text += f"{person_emoji} **Session `{a['convo_id'][:8]}`**: {a['goal_name']} *(Active {elapsed}s ago)*{awaiting_str}\n"
            
    if idle_agents:
        if agents_text:
            agents_text += "\n"
        agents_text += "**💤 Idle/Past Agents:**\n"
        for idx, a in enumerate(idle_agents):
            person_emoji = get_agent_emoji(a['goal_name'], idx + len(active_agents))
            dt = datetime.datetime.fromtimestamp(a['latest_mtime']) if a['latest_mtime'] else None
            time_str = dt.strftime('%m-%d %H:%M') if dt else "Never"
            awaiting_str = " ⚠️ *(Awaiting user approval)*" if is_session_awaiting_approval(a['convo_id'], pending_plans, pending_approvals_list, pending_interactions_list) else ""
            agents_text += f"{person_emoji} **Session `{a['convo_id'][:8]}`**: {a['goal_name']} *(Last active: {time_str})*{awaiting_str}\n"
            
    if not agents_text:
        agents_text = "No agent sessions found in this project."
    if len(agents_text) > 1000:
        agents_text = agents_text[:1000] + "\n... (truncated)"
    embed.add_field(name="🤖 Agent Statuses", value=agents_text, inline=False)
    embed.set_footer(text="Dashboard auto-updates every 10s | Click session button below to view details")

    view = discord.ui.View(timeout=None)
    for i, s in enumerate(project_sessions):
        if i >= 21:
            break
        person_emoji = get_agent_emoji(s['goal_name'], i)
        label = s['goal_name'][:20] + "..." if len(s['goal_name']) > 20 else s['goal_name']
        btn = discord.ui.Button(
            label=f"{i+1}. {person_emoji} {label}", 
            style=discord.ButtonStyle.secondary, 
            custom_id=f"dash_sess_{s['convo_id'][:8]}"
        )
        
        def make_callback(convo_id):
            async def callback(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                refreshed_sessions = discover_agent_sessions()
                session_data = None
                for rs in refreshed_sessions:
                    if rs['convo_id'] == convo_id:
                        session_data = rs
                        break
                        
                if not session_data:
                    await interaction.followup.send(content="❌ Session no longer exists.", ephemeral=True)
                    return
                
                embed_info = discord.Embed(
                    title=f"🤖 Agent Session: {session_data['convo_id'][:8]}",
                    description=f"**Goal:** {session_data['goal_name']}",
                    color=discord.Color.blue()
                )
                
                active_tasks = session_data.get('active_tasks', [])
                active_pids = [at['pid'] for at in active_tasks]
                
                tasks_text = ""
                if active_tasks:
                    for at in active_tasks:
                        tasks_text += f"• **Task {at['task_num']} (PID `{at['pid']}`):** `{at['command']}`\n"
                else:
                    tasks_text = "*No active background processes/tasks running.*"
                embed_info.add_field(name="🔥 Current Running Tasks", value=tasks_text, inline=False)
                
                task_content = "No task list found."
                if session_data['task_path']:
                    try:
                        with open(session_data['task_path'], 'r') as f:
                            lines = f.readlines()
                        checklist_lines = []
                        for line in lines:
                            if any(prefix in line for prefix in ['- [ ]', '- [x]', '- [/]', '#']):
                                checklist_lines.append(line.strip())
                        if checklist_lines:
                            task_content = "\n".join(checklist_lines[:15])
                            if len(checklist_lines) > 15:
                                task_content += "\n*(truncated...)*"
                    except Exception as e:
                        task_content = f"Error reading task list: {e}"
                embed_info.add_field(name="📋 Current Checklist", value=task_content, inline=False)
                
                log_content = "No logs found."
                if session_data['latest_log']:
                    try:
                        with open(session_data['latest_log'], 'r') as f:
                            log_lines = f.readlines()
                        log_content = "".join(log_lines[-12:])
                    except Exception as e:
                        log_content = f"Error reading logs: {e}"
                embed_info.add_field(name="📄 Latest Logs Snippet", value=f"```\n{log_content}\n```", inline=False)
                
                detail_view = AgentDetailView(session_data['convo_id'], session_data['goal_name'], active_pids)
                await interaction.followup.send(embed=embed_info, view=detail_view, ephemeral=True)
            return callback
            
        btn.callback = make_callback(s['convo_id'])
        view.add_item(btn)
        
    if processes:
        btn_kill = discord.ui.Button(label="Stop Active Task 🛑", style=discord.ButtonStyle.danger, custom_id="dash_proj_kill")
        async def kill_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            procs = scan_active_processes()
            if procs:
                pid = procs[0]['pid']
                try:
                    os.kill(pid, signal.SIGTERM)
                    await interaction.followup.send(content=f"✅ Process `{pid}` terminated successfully.", ephemeral=True)
                    await update_dashboard()
                except Exception as e:
                    await interaction.followup.send(content=f"❌ Failed to terminate process: {e}", ephemeral=True)
            else:
                await interaction.followup.send(content="❌ No active processes found to stop.", ephemeral=True)
        btn_kill.callback = kill_callback
        view.add_item(btn_kill)
        
    btn_refresh = discord.ui.Button(label="Refresh 🔄", style=discord.ButtonStyle.primary, custom_id="dash_proj_refresh")
    async def refresh_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        await update_dashboard()
    btn_refresh.callback = refresh_callback
    view.add_item(btn_refresh)

    btn_spawn = discord.ui.Button(label="Spawn Agent 🚀", style=discord.ButtonStyle.success, custom_id="dash_proj_spawn")
    async def spawn_callback(interaction: discord.Interaction):
        modal = AgentSpawnModal(project_name)
        await interaction.response.send_modal(modal)
    btn_spawn.callback = spawn_callback
    view.add_item(btn_spawn)

    btn_back = discord.ui.Button(label="Back 🔙", style=discord.ButtonStyle.primary, custom_id="dash_proj_back")
    async def back_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        state.dashboard_state["view"] = "main"
        state.dashboard_state["project"] = None
        await update_dashboard()
    btn_back.callback = back_callback
    view.add_item(btn_back)
    
    return embed, view

async def update_dashboard():
    """
    Description:
        Edits or sends and pins the active multi-agent system dashboard message.
    Usage:
        await update_dashboard()
    Usage Example:
        await update_dashboard()
    """
    if not state.bot or not state.bot.is_ready() or not os.getenv("DISCORD_USER_ID"):
        return
        
    try:
        DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
        user = await state.bot.fetch_user(int(DISCORD_USER_ID))
        
        # Check for #agent-dashboard channel first in any guild
        dashboard_channel = None
        for guild in state.bot.guilds:
            for chan in guild.text_channels:
                if chan.name == "agent-dashboard" and chan.permissions_for(guild.me).send_messages:
                    dashboard_channel = chan
                    break
            if dashboard_channel:
                break
                
        target_channel = dashboard_channel if dashboard_channel else (user.dm_channel or await user.create_dm())
        
        pinned_messages = []
        try:
            pinned_messages = await target_channel.pins()
        except Exception as pin_err:
            print(f"[Dashboard] Error fetching pinned messages: {pin_err}")

        pinned_dashboard = None
        for pm in pinned_messages:
            if pm.author.id == state.bot.user.id and pm.embeds:
                title = pm.embeds[0].title or ""
                if isinstance(title, str) and ("Multi-Agent System Dashboard" in title or title.startswith("📁 Project:")):
                    if not pinned_dashboard:
                        pinned_dashboard = pm
                    else:
                        try:
                            await pm.unpin()
                        except Exception:
                            pass

        if not state.dashboard_msg and pinned_dashboard:
            state.dashboard_msg = pinned_dashboard
            print(f"[Dashboard] Found existing pinned dashboard {state.dashboard_msg.id}")

        if state.dashboard_state.get("view") == "project" and state.dashboard_state.get("project"):
            embed, view = build_project_menu_ui(state.dashboard_state["project"])
        else:
            embed, view = build_dashboard_ui()
        
        is_new_msg = False
        if state.dashboard_msg:
            try:
                await state.dashboard_msg.edit(embed=embed, view=view)
            except discord.NotFound:
                if pinned_dashboard:
                    state.dashboard_msg = pinned_dashboard
                    await state.dashboard_msg.edit(embed=embed, view=view)
                else:
                    state.dashboard_msg = await target_channel.send(embed=embed, view=view)
                    is_new_msg = True
        else:
            state.dashboard_msg = await target_channel.send(embed=embed, view=view)
            is_new_msg = True

        if is_new_msg:
            try:
                await state.dashboard_msg.pin()
                print(f"[Dashboard] Pinned active dashboard message {state.dashboard_msg.id}")
            except Exception as pin_err:
                print(f"[Dashboard] Error pinning dashboard: {pin_err}")
                
        try:
            async for msg in target_channel.history(limit=100):
                if msg.author.id == state.bot.user.id and msg.embeds:
                    title = msg.embeds[0].title or ""
                    if isinstance(title, str) and ("Multi-Agent System Dashboard" in title or title.startswith("📁 Project:")):
                        if not state.dashboard_msg or msg.id != state.dashboard_msg.id:
                            try:
                                await msg.delete()
                                print(f"[Dashboard] Deleted obsolete dashboard message {msg.id}")
                            except Exception as del_err:
                                print(f"[Dashboard] Error deleting message {msg.id}: {del_err}")
        except Exception as hist_err:
            print(f"[Dashboard] Error cleaning history: {hist_err}")
    except Exception as e:
        print(f"[Dashboard] Error updating dashboard: {e}")

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
        if DISCORD_USER_ID:
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
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down servers...")
