"""
File: dashboard.py
Description:
    Contains user interface builder and update routines for the Discord Liaison Bot dashboard.
    Implements dashboard UI formatting, project detail submenus, process termination, 
    and periodic update loops.
Author: Logan Kirkendall <Logan@LKAud.io>
"""

import os
import datetime
import time
import signal
import re
import sys
import discord

import state
import helpers
import discord_ui
import web_server


def _get_helper(name, default):
    """
    Resolves the given name from the bot module if present (for test mocking compatibility),
    falling back to the default implementation.
    """
    bot_mod = sys.modules.get('bot')
    if bot_mod and hasattr(bot_mod, name):
        return getattr(bot_mod, name)
    return default


def get_state():
    """
    Resolves the state module, prioritizing any mock state patched onto the bot module.
    """
    return _get_helper('state', state)


def discover_agent_sessions():
    return _get_helper('discover_agent_sessions', helpers.discover_agent_sessions)()


def scan_active_processes():
    return _get_helper('scan_active_processes', helpers.scan_active_processes)()


def get_latest_log_data_for_session(session):
    return _get_helper('get_latest_log_data_for_session', helpers.get_latest_log_data_for_session)(session)


def get_all_pending_items():
    return _get_helper('get_all_pending_items', helpers.get_all_pending_items)()


def get_session_project(convo_id):
    return _get_helper('get_session_project', helpers.get_session_project)(convo_id)


def get_last_completed_action(convo_id):
    return _get_helper('get_last_completed_action', helpers.get_last_completed_action)(convo_id)


def is_session_awaiting_approval(convo_id, pending_plans, pending_approvals, pending_interactions):
    return _get_helper('is_session_awaiting_approval', helpers.is_session_awaiting_approval)(
        convo_id, pending_plans, pending_approvals, pending_interactions
    )


def get_agent_emoji(goal_name, idx):
    return _get_helper('get_agent_emoji', helpers.get_agent_emoji)(goal_name, idx)


def get_agent_detail_view():
    return _get_helper('AgentDetailView', discord_ui.AgentDetailView)


def get_agent_spawn_modal():
    return _get_helper('AgentSpawnModal', discord_ui.AgentSpawnModal)


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


def build_dashboard_ui() -> tuple[discord.Embed, discord.ui.View]:
    """
    Description:
        Builds the main dashboard embed and project button views.
    Usage:
        embed, view = build_dashboard_ui()
    Usage Example:
        embed, view = build_dashboard_ui()
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
                get_state().dashboard_state["view"] = "project"
                get_state().dashboard_state["project"] = proj_name
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
    Usage:
        embed, view = build_project_menu_ui(project_name)
    Usage Example:
        embed, view = build_project_menu_ui("my-project")
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
                
                detail_view = get_agent_detail_view()(session_data['convo_id'], session_data['goal_name'], active_pids)
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
        modal = get_agent_spawn_modal()(project_name)
        await interaction.response.send_modal(modal)
    btn_spawn.callback = spawn_callback
    view.add_item(btn_spawn)

    btn_back = discord.ui.Button(label="Back 🔙", style=discord.ButtonStyle.primary, custom_id="dash_proj_back")
    async def back_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        get_state().dashboard_state["view"] = "main"
        get_state().dashboard_state["project"] = None
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
    cur_state = get_state()
    if not cur_state.bot or not cur_state.bot.is_ready():
        return
        
    try:
        DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
        
        # Check for #agent-dashboard channel first in any guild
        dashboard_channel = None
        for guild in cur_state.bot.guilds:
            for chan in guild.text_channels:
                if chan.name == "agent-dashboard" and chan.permissions_for(guild.me).send_messages:
                    dashboard_channel = chan
                    break
            if dashboard_channel:
                break
                
        if getattr(cur_state, "FORCE_SERVER_CHAT", False):
            if not dashboard_channel:
                for guild in cur_state.bot.guilds:
                    for name_opt in ["agent-updates", "agent-discussion"]:
                        for chan in guild.text_channels:
                            if chan.name == name_opt and chan.permissions_for(guild.me).send_messages:
                                dashboard_channel = chan
                                break
                        if dashboard_channel:
                            break
                    if dashboard_channel:
                        break
            if not dashboard_channel:
                for guild in cur_state.bot.guilds:
                    for chan in guild.text_channels:
                        if chan.permissions_for(guild.me).send_messages:
                            dashboard_channel = chan
                            break
                    if dashboard_channel:
                        break
            target_channel = dashboard_channel
        else:
            if dashboard_channel:
                target_channel = dashboard_channel
            else:
                if not DISCORD_USER_ID:
                    print("[Dashboard] No DISCORD_USER_ID to fallback to DM.")
                    return
                user = await cur_state.bot.fetch_user(int(DISCORD_USER_ID))
                target_channel = user.dm_channel or await user.create_dm()
            
        if not target_channel:
            print("[Dashboard] No suitable dashboard channel resolved.")
            return
        
        pinned_messages = []
        try:
            pinned_messages = await target_channel.pins()
        except Exception as pin_err:
            print(f"[Dashboard] Error fetching pinned messages: {pin_err}")

        pinned_dashboard = None
        for pm in pinned_messages:
            if pm.author.id == cur_state.bot.user.id and pm.embeds:
                title = pm.embeds[0].title or ""
                if isinstance(title, str) and ("Multi-Agent System Dashboard" in title or title.startswith("📁 Project:")):
                    if not pinned_dashboard:
                        pinned_dashboard = pm
                    else:
                        try:
                            await pm.unpin()
                        except Exception:
                            pass

        if not cur_state.dashboard_msg and pinned_dashboard:
            cur_state.dashboard_msg = pinned_dashboard
            print(f"[Dashboard] Found existing pinned dashboard {cur_state.dashboard_msg.id}")

        if cur_state.dashboard_state.get("view") == "project" and cur_state.dashboard_state.get("project"):
            embed, view = build_project_menu_ui(cur_state.dashboard_state["project"])
        else:
            embed, view = build_dashboard_ui()
        
        is_new_msg = False
        if cur_state.dashboard_msg:
            try:
                await cur_state.dashboard_msg.edit(embed=embed, view=view)
            except discord.NotFound:
                if pinned_dashboard:
                    cur_state.dashboard_msg = pinned_dashboard
                    await cur_state.dashboard_msg.edit(embed=embed, view=view)
                else:
                    cur_state.dashboard_msg = await target_channel.send(embed=embed, view=view)
                    is_new_msg = True
        else:
            cur_state.dashboard_msg = await target_channel.send(embed=embed, view=view)
            is_new_msg = True

        if is_new_msg:
            try:
                await cur_state.dashboard_msg.pin()
                print(f"[Dashboard] Pinned active dashboard message {cur_state.dashboard_msg.id}")
            except Exception as pin_err:
                print(f"[Dashboard] Error pinning dashboard: {pin_err}")
                
        try:
            async for msg in target_channel.history(limit=100):
                if msg.author.id == cur_state.bot.user.id and msg.embeds:
                    title = msg.embeds[0].title or ""
                    if isinstance(title, str) and ("Multi-Agent System Dashboard" in title or title.startswith("📁 Project:")):
                        if not cur_state.dashboard_msg or msg.id != cur_state.dashboard_msg.id:
                            try:
                                await msg.delete()
                                print(f"[Dashboard] Deleted obsolete dashboard message {msg.id}")
                            except Exception as del_err:
                                print(f"[Dashboard] Error deleting message {msg.id}: {del_err}")
        except Exception as hist_err:
            print(f"[Dashboard] Error cleaning history: {hist_err}")
    except Exception as e:
        print(f"[Dashboard] Error updating dashboard: {e}")
