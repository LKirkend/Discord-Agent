import os
import glob
import psutil
import datetime
import time
import json
import re
import urllib.parse
import socket
from typing import Dict, Optional, List, Tuple
import discord

import state

def extract_and_prepare_files(text: str, seen_paths: Optional[set] = None) -> Tuple[str, List[discord.File]]:
    """
    Description:
        Extracts local file paths referenced via file:// URLs or markdown links,
        creates discord.File attachments, and rewrites the URLs.
    Usage:
        text, files = extract_and_prepare_files(text, seen_paths)
    Usage Example:
        txt, file_list = extract_and_prepare_files("[task.md](file:///path/to/task.md)")
    """
    if not text:
        return text, []
    if seen_paths is None:
        seen_paths = set()
    files = []
    
    # 1. Match standard markdown links: [link text](file:///path/to/file)
    pattern_markdown = r'\[([^\]]+)\]\(file://([^\s\)]+)\)'
    
    def repl_markdown(match):
        text_content = match.group(1)
        file_path = match.group(2)
        decoded_path = urllib.parse.unquote(file_path)
        abs_path = os.path.abspath(os.path.expanduser(decoded_path))
        
        exists = False
        for _ in range(5):
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                exists = True
                break
            time.sleep(0.3)
            
        if exists:
            if abs_path not in seen_paths:
                seen_paths.add(abs_path)
                filename = os.path.basename(abs_path)
                files.append(discord.File(abs_path, filename=filename))
            return f"**{text_content} (Attached)**"
        else:
            return match.group(0)
            
    text = re.sub(pattern_markdown, repl_markdown, text)
    
    # 2. Match raw file URLs like file:///path/to/file
    pattern_raw = r'file://([^\s\)\>]+)'
    
    def repl_raw(match):
        file_path = match.group(1)
        decoded_path = urllib.parse.unquote(file_path)
        abs_path = os.path.abspath(os.path.expanduser(decoded_path))
        
        exists = False
        for _ in range(5):
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                exists = True
                break
            time.sleep(0.3)
            
        if exists:
            if abs_path not in seen_paths:
                seen_paths.add(abs_path)
                filename = os.path.basename(abs_path)
                files.append(discord.File(abs_path, filename=filename))
            return f"**{filename} (Attached)**"
        else:
            return match.group(0)
            
    text = re.sub(pattern_raw, repl_raw, text)
    return text, files

def extract_and_prepare_embed_files(embed: discord.Embed, seen_paths: Optional[set] = None) -> Tuple[discord.Embed, List[discord.File]]:
    """
    Description:
        Wrapper to extract files and rewrite paths from a Discord Embed object description and fields.
    Usage:
        embed, files = extract_and_prepare_embed_files(embed, seen_paths)
    Usage Example:
        emb, fls = extract_and_prepare_embed_files(my_embed, set())
    """
    if seen_paths is None:
        seen_paths = set()
    files = []
    if embed.description:
        desc, new_files = extract_and_prepare_files(embed.description, seen_paths)
        embed.description = desc
        files.extend(new_files)
    for idx, field in enumerate(embed.fields):
        val, new_files = extract_and_prepare_files(field.value, seen_paths)
        files.extend(new_files)
        embed.set_field_at(
            idx,
            name=field.name,
            value=val,
            inline=field.inline
        )
    return embed, files

def extract_files_from_dict_or_list(data, seen_paths: set) -> List[discord.File]:
    """
    Description:
        Recursively extracts local files referenced within data dicts/lists/strings.
    Usage:
        files = extract_files_from_dict_or_list(data, seen_paths)
    Usage Example:
        files = extract_files_from_dict_or_list({"TargetFile": "/path/to/file.txt"}, seen_paths)
    """
    files = []
    if isinstance(data, dict):
        for k, v in data.items():
            files.extend(extract_files_from_dict_or_list(v, seen_paths))
            if k in ["TargetFile", "AbsolutePath", "SearchPath"] or "path" in k.lower():
                if isinstance(v, str):
                    abs_path = os.path.abspath(os.path.expanduser(v))
                    if os.path.exists(abs_path) and os.path.isfile(abs_path) and abs_path not in seen_paths:
                        seen_paths.add(abs_path)
                        files.append(discord.File(abs_path, filename=os.path.basename(abs_path)))
    elif isinstance(data, list):
        for item in data:
            files.extend(extract_files_from_dict_or_list(item, seen_paths))
    elif isinstance(data, str):
        if data.startswith("file://"):
            p = data
            while p.startswith("file://"):
                p = p[7:]
            while p.startswith("/"):
                p = "/" + p.lstrip("/")
            decoded_path = urllib.parse.unquote(p)
            abs_path = os.path.abspath(os.path.expanduser(decoded_path))
            if os.path.exists(abs_path) and os.path.isfile(abs_path) and abs_path not in seen_paths:
                seen_paths.add(abs_path)
                files.append(discord.File(abs_path, filename=os.path.basename(abs_path)))
        elif os.path.isabs(data):
            abs_path = os.path.abspath(os.path.expanduser(data))
            if os.path.exists(abs_path) and os.path.isfile(abs_path) and abs_path not in seen_paths:
                seen_paths.add(abs_path)
                files.append(discord.File(abs_path, filename=os.path.basename(abs_path)))
    return files

def scan_active_processes() -> List[dict]:
    """
    Description:
        Scans running system processes for active Python model training processes.
    Usage:
        procs = scan_active_processes()
    Usage Example:
        active = scan_active_processes()
    """
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info.get('name') or ''
            if 'python' in name.lower():
                cmd = proc.cmdline()
                cmd_str = " ".join(cmd)
                if 'train_feedback_model.py' in cmd_str or 'train' in cmd_str:
                    processes.append({
                        'pid': proc.pid,
                        'cmd': cmd_str,
                        'cwd': proc.cwd()
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            continue
    return processes

def get_training_status_info() -> str:
    """
    Description:
        Formulates a markdown string status report of currently running training processes and logs.
    Usage:
        report = get_training_status_info()
    Usage Example:
        status_text = get_training_status_info()
    """
    processes = scan_active_processes()
    status_msg = ""
    if processes:
        status_msg += "🔥 **Active Training Processes:**\n"
        for idx, p in enumerate(processes, start=1):
            num_emoji = f"{idx}️⃣" if idx <= 10 else f"{idx}."
            status_msg += f"{num_emoji} **PID:** `{p['pid']}`\n  **Cmd:** `{p['cmd']}`\n  **CWD:** `{p['cwd']}`\n"
    else:
        status_msg += "💤 **No active python training processes found.**\n"

    brain_dir = state.BRAIN_DIR
    log_files = glob.glob(f"{brain_dir}/*/.system_generated/tasks/task-*.log")
    if log_files:
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        latest_log = log_files[0]
        mtime = os.path.getmtime(latest_log)
        dt = datetime.datetime.fromtimestamp(mtime)
        
        status_msg += f"\n📊 **Latest Task Log:** `{os.path.basename(latest_log)}` \n🕒 **Modified:** `{dt.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        
        try:
            with open(latest_log, 'r') as f:
                lines = f.readlines()
            last_lines = lines[-15:]
            log_snippet = "".join(last_lines)
            status_msg += f"```\n{log_snippet}\n```"
        except Exception as e:
            status_msg += f"\n❌ *Error reading log file:* {e}\n"
    else:
        status_msg += "\n📭 **No task log files found.**\n"
        
    return status_msg

def match_commands(cmd1: str, cmd2: str) -> bool:
    """
    Description:
        Robust matcher to check if two command lines are functionally similar.
    Usage:
        matches = match_commands(cmd1, cmd2)
    Usage Example:
        matches = match_commands("python train.py", "python3 train.py")
    """
    c1 = cmd1.strip().replace('"', '').replace("'", "")
    c2 = cmd2.strip().replace('"', '').replace("'", "")
    
    if c1 in c2 or c2 in c1:
        return True
        
    parts1 = c1.split()
    parts2 = c2.split()
    
    script1 = None
    for p in parts1:
        if p.endswith('.py') or p.endswith('.sh') or p.endswith('.js') or 'pytest' in p:
            script1 = os.path.basename(p)
            break
            
    script2 = None
    for p in parts2:
        if p.endswith('.py') or p.endswith('.sh') or p.endswith('.js') or 'pytest' in p:
            script2 = os.path.basename(p)
            break
            
    if script1 and script2 and script1 == script2:
        args1 = [os.path.basename(a) for a in parts1 if not a.startswith('-') and a != script1]
        args2 = [os.path.basename(a) for a in parts2 if not a.startswith('-') and a != script2]
        
        if not args1 and not args2:
            return True
        if set(args1) & set(args2):
            return True
            
    return False

def get_command_for_task(convo_id: str, task_num: int) -> str:
    """
    Description:
        Parses transcripts in search of the CommandLine run command executed for a given task step index.
    Usage:
        cmd = get_command_for_task(convo_id, task_num)
    Usage Example:
        cmd = get_command_for_task("abc-123", 5)
    """
    transcript_path = os.path.join(state.BRAIN_DIR, convo_id, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(transcript_path):
        return f"Task {task_num} (Command unknown)"
        
    try:
        with open(transcript_path, 'r', errors='ignore') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get('step_index') == task_num:
                        tool_calls = data.get('tool_calls', [])
                        if tool_calls and tool_calls[0].get('name') == 'run_command':
                            cmd = tool_calls[0]['args'].get('CommandLine', '')
                            if cmd.startswith('"') and cmd.endswith('"'):
                                cmd = cmd[1:-1]
                            return cmd
                except Exception:
                    continue
    except Exception as e:
        print(f"Error reading transcript file: {e}")
        
    return f"Task {task_num} (Command unknown)"

def get_commands_for_session(convo_id: str) -> Dict[int, str]:
    """
    Description:
        Scans a conversation transcript and maps step indices to run_command values.
    Usage:
        cmds = get_commands_for_session(convo_id)
    Usage Example:
        cmd_map = get_commands_for_session("abc-123")
    """
    commands_map = {}
    transcript_path = os.path.join(state.BRAIN_DIR, convo_id, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(transcript_path):
        return commands_map
        
    try:
        with open(transcript_path, 'r', errors='ignore') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    task_num = data.get('step_index')
                    if task_num is not None:
                        tool_calls = data.get('tool_calls', [])
                        if tool_calls and tool_calls[0].get('name') == 'run_command':
                            cmd = tool_calls[0]['args'].get('CommandLine', '')
                            if cmd.startswith('"') and cmd.endswith('"'):
                                cmd = cmd[1:-1]
                            commands_map[task_num] = cmd
                except Exception:
                    continue
    except Exception as e:
        print(f"Error reading transcript file: {e}")
    return commands_map

def get_active_tasks_for_session(convo_id: str, running_processes: List[dict]) -> List[dict]:
    """
    Description:
        Finds active task numbers and commands based on running system processes.
    Usage:
        tasks = get_active_tasks_for_session(convo_id, running_processes)
    Usage Example:
        active = get_active_tasks_for_session("abc-123", [{"pid": 12, "cmd_str": "python bot.py"}])
    """
    active_tasks = []
    tasks_dir = os.path.join(state.BRAIN_DIR, convo_id, ".system_generated", "tasks")
    
    if not os.path.exists(tasks_dir):
        return active_tasks
        
    log_files = glob.glob(os.path.join(tasks_dir, "task-*.log"))
    if not log_files:
        return active_tasks

    commands_map = get_commands_for_session(convo_id)

    for log_path in log_files:
        filename = os.path.basename(log_path)
        try:
            task_num = int(filename.split('-')[1].split('.')[0])
        except Exception:
            continue
            
        cmd_str = commands_map.get(task_num)
        if not cmd_str:
            continue
            
        for rp in running_processes:
            if match_commands(cmd_str, rp['cmd_str']):
                active_tasks.append({
                    'task_num': task_num,
                    'command': cmd_str,
                    'pid': rp['pid']
                })
                break
                
    return active_tasks

def discover_agent_sessions() -> List[dict]:
    """
    Description:
        Scans the application brain directory for active and historical agent sessions.
    Usage:
        sessions = discover_agent_sessions()
    Usage Example:
        session_list = discover_agent_sessions()
    """
    brain_dir = state.BRAIN_DIR
    sessions = []
    
    if not os.path.exists(brain_dir):
        return sessions
        
    running_processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info.get('name') or ''
            if 'python' in name.lower():
                cmd = proc.cmdline()
                if cmd:
                    running_processes.append({
                        'pid': proc.pid,
                        'cmd_str': " ".join(cmd).strip().replace('"', '').replace("'", ""),
                        'cwd': proc.cwd()
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            continue
            
    for entry in os.listdir(brain_dir):
        entry_path = os.path.join(brain_dir, entry)
        if not os.path.isdir(entry_path) or entry.startswith('.'):
            continue
            
        task_path = os.path.join(entry_path, "task.md")
        goal_name = "Agent Workspace Session"
        if os.path.exists(task_path):
            try:
                with open(task_path, 'r') as f:
                    first_line = f.readline().strip()
                if first_line.startswith('#'):
                     goal_name = first_line.lstrip('#').strip()
            except Exception:
                pass
                
        tasks_dir = os.path.join(entry_path, ".system_generated", "tasks")
        latest_log = None
        latest_mtime = 0
        log_files = []
        
        if os.path.exists(tasks_dir):
            log_files = glob.glob(os.path.join(tasks_dir, "task-*.log"))
            if log_files:
                log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                latest_log = log_files[0]
                latest_mtime = os.path.getmtime(latest_log)
                
        if not os.path.exists(task_path) and not log_files:
            continue
            
        active_tasks = get_active_tasks_for_session(entry, running_processes)
        status = "Idle"
        if active_tasks or (latest_log and (time.time() - latest_mtime < 900)):
            status = "Active"
            
        sessions.append({
            'convo_id': entry,
            'goal_name': goal_name,
            'latest_log': latest_log,
            'latest_mtime': latest_mtime,
            'status': status,
            'task_path': task_path if os.path.exists(task_path) else None,
            'active_tasks': active_tasks
        })
        
    sessions.sort(key=lambda x: (x['status'] == 'Active', x['latest_mtime']), reverse=True)
    return sessions

def get_all_pending_items() -> tuple[list[dict], list[dict], list[dict]]:
    """
    Description:
        Scans for all pending implementation plans and active approvals.
    Usage:
        plans, approvals, interactions = get_all_pending_items()
    Usage Example:
        p_plans, p_apps, p_ints = get_all_pending_items()
    """
    pending_plans = []
    brain_dir = state.BRAIN_DIR
    if os.path.exists(brain_dir):
        for entry in os.listdir(brain_dir):
            entry_path = os.path.join(brain_dir, entry)
            if not os.path.isdir(entry_path) or entry.startswith('.'):
                continue
            metadata_path = os.path.join(entry_path, "implementation_plan.md.metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        data = json.load(f)
                    if data.get("requestFeedback") is True:
                        project_name = get_session_project(entry)
                        pending_plans.append({
                            "convo_id": entry,
                            "project_name": project_name,
                            "summary": data.get("summary", "No summary provided")
                        })
                except Exception:
                    pass

    pending_approvals_list = []
    pending_interactions_list = []
    for item_id, item in list(state.active_pending_items.items()):
        if item.get("type") == "permission":
            pending_approvals_list.append(item)
        elif item.get("type") == "interaction":
            pending_interactions_list.append(item)
            
    return pending_plans, pending_approvals_list, pending_interactions_list

is_first_run = True

async def check_pending_notifications(is_launch: bool = False):
    """
    Description:
        Checks for outstanding approval requests/interactions and alerts the user on Discord via DM.
    Usage:
        await check_pending_notifications(is_launch)
    Usage Example:
        await check_pending_notifications(True)
    """
    if not state.bot or not state.bot.is_ready() or not os.getenv("DISCORD_USER_ID"):
        return
        
    try:
        user = await state.bot.fetch_user(int(os.getenv("DISCORD_USER_ID")))
    except Exception as e:
        print(f"[Pending Checker] Failed to fetch user: {e}")
        return

    pending_plans, pending_approvals_list, pending_interactions_list = get_all_pending_items()

    current_pending_keys = set()
    for p in pending_plans:
        current_pending_keys.add(f"plan_{p['convo_id']}")
    for a in pending_approvals_list:
        current_pending_keys.add(f"approve_{a['convo_id']}_{a['tool_name']}")
    for idx, i in enumerate(pending_interactions_list):
        current_pending_keys.add(f"interact_{i['convo_id']}_{idx}")

    state.notified_pending_keys = state.notified_pending_keys.intersection(current_pending_keys)
    new_pending_keys = current_pending_keys - state.notified_pending_keys
    should_notify = (is_launch and current_pending_keys) or new_pending_keys

    if should_notify:
        msg_lines = []
        if is_launch:
            msg_lines.append("⚡ **Antigravity Sidecar Launched!** Here is a summary of active conversations requiring your attention:\n")
        else:
            msg_lines.append("🔔 **Attention Required!** New action(s) needed in your conversations:\n")

        if pending_plans:
            msg_lines.append("📝 **Implementation Plans Waiting for Approval:**")
            for p in pending_plans:
                msg_lines.append(f"• **Project: `{p['project_name']}`** (Session `{p['convo_id'][:8]}`)\n  *Summary:* {p['summary']}")
            msg_lines.append("")

        if pending_approvals_list:
            msg_lines.append("🛡️ **Tools/Commands Waiting for Permission Approval:**")
            for a in pending_approvals_list:
                msg_lines.append(f"• **Project: `{a['project_name']}`** (Session `{a['convo_id'][:8]}`)\n  *Tool:* `{a['tool_name']}`")
            msg_lines.append("")

        if pending_interactions_list:
            msg_lines.append("❓ **Agent Questions Waiting for Input:**")
            for i in pending_interactions_list:
                questions_str = ", ".join([f'"{q}"' for q in i['questions']])
                msg_lines.append(f"• **Project: `{i['project_name']}`** (Session `{i['convo_id'][:8]}`)\n  *Question(s):* {questions_str}")
            msg_lines.append("")

        notification_text = "\n".join(msg_lines).strip()
        seen_paths = set()
        notification_text, notification_files = extract_and_prepare_files(notification_text, seen_paths)
        
        try:
            if len(notification_text) > 1900:
                chunks = [notification_text[i:i+1900] for i in range(0, len(notification_text), 1900)]
                await user.send(chunks[0], files=notification_files if notification_files else None)
                for chunk in chunks[1:]:
                    await user.send(chunk)
            else:
                await user.send(notification_text, files=notification_files if notification_files else None)
            state.notified_pending_keys.update(current_pending_keys)
        except Exception as e:
            print(f"[Pending Checker] Failed to send reminder DM: {e}")

def get_latest_log_data_for_session(session: dict) -> Optional[dict]:
    """
    Description:
        Extracts recent epoch statistics from the session's latest log file.
    Usage:
        info = get_latest_log_data_for_session(session)
    Usage Example:
        data = get_latest_log_data_for_session(session)
    """
    if not session['latest_log']:
        return None
    try:
        with open(session['latest_log'], 'r') as f:
            lines = f.readlines()
        
        epoch_str = "N/A"
        train_loss = "N/A"
        val_loss = "N/A"
        val_acc = "N/A"
        
        for line in reversed(lines):
            parts = line.split()
            if len(parts) >= 5 and parts[0].isdigit():
                epoch_str = parts[0]
                train_loss = parts[1]
                val_loss = parts[2]
                val_acc = parts[3]
                break

        return {
            'filename': os.path.basename(session['latest_log']),
            'epoch': epoch_str,
            'train_loss': train_loss,
            'val_loss': val_loss,
            'val_acc': val_acc
        }
    except Exception:
        return None

def get_agent_emoji(goal_name: str, index: int = 0) -> str:
    """
    Description:
        Selects a unique emoji identifier based on the hash of the agent's goal name.
    Usage:
        emoji = get_agent_emoji(goal_name, index)
    Usage Example:
        emoji = get_agent_emoji("Refactor code", 1)
    """
    emojis = ["🤖", "🧠", "💻", "🚀", "⚡", "🔥", "🛡️", "🛸", "👾", "🎯"]
    h = hash(goal_name + str(index))
    return emojis[h % len(emojis)]

# Cache for resolved project names to avoid re-scanning on every dashboard refresh
_project_cache: Dict[str, str] = {}

# Friendly name mapping for resolved folder names
PROJECT_MAP = {
    "jolly-lavoisier": "Discord-Agent",
    "Discord-Agent": "Discord-Agent",
    "discord-agent": "Discord-Agent",
    "CorrelationEngine": "DeCorrelationEngine",
    "Correlation-Engine": "DeCorrelationEngine",
    "DeCorrelationEngine": "DeCorrelationEngine",
    "research-stem-splitting-models": "OpenFeedbackRemover",
    "OpenFeedbackRemover": "OpenFeedbackRemover",
    "antigravity": "antigravity",
}

# Folders to exclude from project matching — infrastructure dirs, not projects
_EXCLUDED_FOLDERS = frozenset([
    "worktrees", "brain", "config", "logs", "plugins", "sidecars", "run",
    "ide", "agy2", ".gemini", ".git", ".venv", "__pycache__",
])

# System folders to ignore when matching /Users/<user>/<folder>
_EXCLUDED_USER_FOLDERS = frozenset([
    "Applications", "Library", "Documents", "Downloads", "Desktop",
    "Pictures", "config", "Brain", ".gemini",
])

# Regex patterns for extracting project folder candidates from transcript lines
_RE_WORKTREE = re.compile(r'/antigravity/worktrees/([^/\"\\\'\s\)]+)')
_RE_ANTI_SUB = re.compile(r'/antigravity/([^/\"\\\'\s\)]+)')
_RE_DOCS_ANTI = re.compile(r'/Documents/antigravity/([^/\"\\\'\s\)]+)')

def get_session_project(convo_id: str) -> str:
    """
    Description:
        Resolves the project name for a given conversation by scanning the
        transcript using frequency-weighted voting across the first 200 lines.
        Results are cached to avoid re-scanning on every dashboard refresh.

        The algorithm counts occurrences of candidate project folder paths,
        weighting USER_INPUT lines and tool_call arguments (TargetFile, Cwd,
        SearchPath) at 3x compared to ambient metadata mentions at 1x. The
        ADDITIONAL_METADATA block on line 1 (which lists the user's open
        editor tabs, NOT the session's target project) is explicitly skipped.

    Usage:
        project_name = get_session_project(convo_id)

    Usage Example:
        proj = get_session_project("134486bf-d5b8-496e-9194-94468af7f8b8")
    """
    if convo_id in _project_cache:
        return _project_cache[convo_id]

    brain_dir = state.BRAIN_DIR
    transcript_path = os.path.join(brain_dir, convo_id, '.system_generated', 'logs', 'transcript.jsonl')

    if not os.path.exists(transcript_path):
        return "Global"

    folder_scores: Dict[str, float] = {}
    max_lines = 200

    try:
        with open(transcript_path, 'r', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if line_num > max_lines:
                    break

                # Determine weight: USER_INPUT and tool_call lines get 3x weight
                weight = 1.0
                if '"type":"USER_INPUT"' in line:
                    weight = 3.0
                elif '"tool_calls"' in line:
                    weight = 2.0

                # Skip the ADDITIONAL_METADATA block content — it lists
                # the user's open editor tabs, not the session's target
                if "ADDITIONAL_METADATA" in line:
                    weight = 0.0

                if weight == 0.0:
                    continue

                # Extract ALL candidate folders from this line
                candidates_on_line = set()

                for m in _RE_WORKTREE.finditer(line):
                    folder = m.group(1)
                    if folder not in _EXCLUDED_FOLDERS:
                        candidates_on_line.add(folder)

                for m in _RE_ANTI_SUB.finditer(line):
                    folder = m.group(1)
                    if folder not in _EXCLUDED_FOLDERS:
                        candidates_on_line.add(folder)

                for m in _RE_DOCS_ANTI.finditer(line):
                    folder = m.group(1)
                    if folder not in _EXCLUDED_FOLDERS:
                        candidates_on_line.add(folder)

                # Accumulate weighted scores
                for folder in candidates_on_line:
                    folder_scores[folder] = folder_scores.get(folder, 0.0) + weight
    except Exception:
        pass

    if not folder_scores:
        _project_cache[convo_id] = "Global"
        return "Global"

    # Winner takes all — highest weighted score
    best_folder = max(folder_scores, key=folder_scores.get)
    project_name = PROJECT_MAP.get(best_folder, best_folder)
    _project_cache[convo_id] = project_name
    return project_name

def is_session_awaiting_approval(convo_id: str, pending_plans: list, pending_approvals: list, pending_interactions: list) -> bool:
    """
    Description:
        Determines whether a session is blocked on user approvals.
    Usage:
        blocked = is_session_awaiting_approval(convo_id, pending_plans, pending_approvals, pending_interactions)
    Usage Example:
        blocked = is_session_awaiting_approval("abc", [], [], [])
    """
    if any(p.get("convo_id") == convo_id for p in pending_plans):
        return True
    if any(a.get("convo_id") == convo_id for a in pending_approvals):
        return True
    if any(i.get("convo_id") == convo_id for i in pending_interactions):
        return True
    return False

def get_last_completed_action(convo_id: str) -> str:
    """
    Description:
        Finds the last executed tool or action from the conversation transcript,
        resolving action text details from the event types and arguments.
    Usage:
        action = get_last_completed_action(convo_id)
    Usage Example:
        act = get_last_completed_action("abc")
    """
    import json
    brain_dir = state.BRAIN_DIR
    transcript_path = os.path.join(brain_dir, convo_id, '.system_generated', 'logs', 'transcript.jsonl')
    if not os.path.exists(transcript_path):
        return "No actions recorded"
    try:
        with open(transcript_path, 'r', errors='ignore') as f:
            lines = f.readlines()
        if not lines:
            return "No actions recorded"
        
        # Iterate backwards to find the last meaningful action
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                ev_type = event.get("type", "")
                
                # Check for tool calls inside model planning/response
                if ev_type == "PLANNER_RESPONSE" and event.get("tool_calls"):
                    tc = event["tool_calls"][0]
                    args = tc.get("args", {})
                    action_text = args.get("toolAction") or args.get("toolSummary")
                    if action_text:
                        if isinstance(action_text, str):
                            action_text = action_text.strip('"\'')
                        return f"Calling: {action_text}"
                    return f"Running tool: {tc.get('name', 'unknown')}"
                
                # Check explicit tool result/execution events
                if ev_type == "RUN_COMMAND":
                    return "Executed terminal command"
                elif ev_type in ["REPLACE_FILE_CONTENT", "MULTI_REPLACE_FILE_CONTENT", "WRITE_TO_FILE"]:
                    return "Edited workspace file"
                elif ev_type == "VIEW_FILE":
                    return "Viewed file content"
                elif ev_type == "LIST_DIRECTORY":
                    return "Listed directory contents"
                elif ev_type == "ASK_QUESTION":
                    return "Awaiting user response"
                elif ev_type == "ASK_PERMISSION":
                    return "Requested permission for execution"
                elif ev_type == "BROWSER_SUBAGENT":
                    return "Executed browser subagent"
                elif ev_type == "GENERATE_IMAGE":
                    return "Generated image"
                elif ev_type == "USER_INPUT":
                    return "Received new request from user"
                elif ev_type == "PLANNER_RESPONSE":
                    content = event.get("content", "").strip()
                    if content:
                        first_line = content.split('\n')[0][:60]
                        if len(content) > 60:
                            first_line += "..."
                        return f"Planner response: {first_line}"
                    return "Analyzing task state"
            except Exception:
                continue
    except Exception as e:
        return f"Error reading transcript: {e}"
    return "Active"

def get_project_folder_path(project_name: str) -> Optional[str]:
    """
    Description:
        Finds the folder path for a project name inside ~/.gemini/config/projects/.
    Usage:
        path = get_project_folder_path(project_name)
    Usage Example:
        path = get_project_folder_path("antigravity")
    """
    config_dir = os.path.expanduser("~/.gemini/config/projects")
    if not os.path.exists(config_dir):
        return None
    for entry in os.listdir(config_dir):
        if not entry.endswith(".json"):
            continue
        path = os.path.join(config_dir, entry)
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if data.get("name") == project_name:
                resources = data.get("projectResources", {}).get("resources", [])
                for r in resources:
                    uri = r.get("folderUri") or r.get("gitFolder", {}).get("folderUri")
                    if uri and uri.startswith("file://"):
                        return uri.replace("file://", "")
        except Exception:
            pass
    return None

def _is_port_in_use(port: int) -> bool:
    """
    Description:
        Checks if a local TCP port is currently bound.
    Usage:
        in_use = _is_port_in_use(port)
    Usage Example:
        in_use = _is_port_in_use(18000)
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False
