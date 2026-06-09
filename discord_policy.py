import sys
import glob
import os

# Dynamically locate the site-packages inside the local .venv of the root workspace
venv_lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv/lib")
if os.path.exists(venv_lib_dir):
    for d in glob.glob(os.path.join(venv_lib_dir, "python3.*/site-packages")):
        if d not in sys.path:
            sys.path.insert(0, d)

# pyrefly: ignore [missing-import]
import httpx
import uuid
import json
import re
from typing import Dict, Any, List

# pyrefly: ignore [missing-import]
from google.antigravity import types
# pyrefly: ignore [missing-import]
from google.antigravity.hooks import hooks, policy

# Target URL for the local Discord bot server
_resolved_port_cache = None

def resolve_sidecar_port() -> str:
    """Dynamically resolves the sidecar web port, checking environment then querying the Language Server."""
    global _resolved_port_cache
    if _resolved_port_cache:
        return _resolved_port_cache

    port = os.getenv("ANTIGRAVITY_SIDECAR_WEB_PORT")
    if port:
        _resolved_port_cache = port
        return port

    # Try to query the local Language Server if CSRF token is available
    csrf_token = os.getenv("ANTIGRAVITY_CSRF_TOKEN")
    if csrf_token:
        try:
            import urllib.request
            import json
            ls_address = os.getenv("ANTIGRAVITY_LS_ADDRESS", "127.0.0.1:65081")
            url = f"http://{ls_address}/exa.language_server_pb.LanguageServerService/GetSidecars"
            headers = {
                "Content-Type": "application/json",
                "x-codeium-csrf-token": csrf_token,
            }
            req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
            # Set a low timeout so we don't block tool execution if LS is unresponsive
            with urllib.request.urlopen(req, timeout=1.5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    for s in data.get("sidecars", []):
                        if s.get("sidecarId") in ["discord-liaison-ide", "discord-liaison"]:
                            web_port = s.get("webPort")
                            if web_port:
                                _resolved_port_cache = str(web_port)
                                return _resolved_port_cache
        except Exception:
            pass

    # Cache the default fallback as well to avoid repeated failing LS queries
    _resolved_port_cache = "18000"
    return "18000"

DISCORD_APPROVAL_URL = f"http://127.0.0.1:{resolve_sidecar_port()}/approve"

def command_matches_rule(command: str, rule: str) -> bool:
    cmd_clean = command.strip().replace('"', '').replace("'", "")
    rule_clean = rule.strip().replace('"', '').replace("'", "")
    
    # Standalone wildcard matches anything
    if rule_clean == "*":
        return True
        
    # Exact match
    if cmd_clean == rule_clean:
        return True
        
    # Token-prefix match (similar to platform)
    cmd_tokens = cmd_clean.split()
    rule_tokens = rule_clean.split()
    if len(rule_tokens) > len(cmd_tokens):
        return False
    for c, r in zip(cmd_tokens, rule_tokens):
        if c != r:
            return False
    return True

def check_persistent_permission(tool_name: str, arguments: dict) -> bool:
    """
    Checks if a tool call matches a persistently approved rule.
    Project rules: .antigravity_permissions.json searching recursively upwards from the CWD.
    Global rules: Both ~/.gemini/antigravity/permissions.json and ~/.gemini/antigravity-ide/permissions.json.
    """
    # 1. Traverse recursively up from current directory to find all .antigravity_permissions.json files
    project_perms_paths = []
    current_dir = os.path.abspath(os.getcwd())
    while True:
        candidate = os.path.join(current_dir, ".antigravity_permissions.json")
        if os.path.exists(candidate):
            project_perms_paths.append(candidate)
        parent = os.path.dirname(current_dir)
        if parent == current_dir:
            break
        current_dir = parent

    # 2. Global permissions files
    global_perms_paths = [
        os.path.expanduser("~/.gemini/antigravity/permissions.json"),
        os.path.expanduser("~/.gemini/antigravity-ide/permissions.json")
    ]

    # 3. Check all matching paths
    for path in (project_perms_paths + global_perms_paths):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r") as f:
                perms = json.load(f)
            
            allowed_rules = perms.get(tool_name, [])
            if not allowed_rules:
                continue
            
            if tool_name == "run_command":
                cmd = arguments.get("CommandLine", "")
                for rule in allowed_rules:
                    if rule == "*" or rule is True:
                        return True
                    if command_matches_rule(cmd, rule):
                        return True
            elif tool_name in ["write_to_file", "replace_file_content", "multi_replace_file_content", "create_file", "edit_file"]:
                # Check target file path
                target_file = arguments.get("TargetFile", "") or arguments.get("AbsolutePath", "")
                if not target_file:
                    continue
                target_file = os.path.abspath(target_file)
                for rule in allowed_rules:
                    rule_path = os.path.abspath(os.path.expanduser(rule))
                    if target_file == rule_path or target_file.startswith(rule_path + os.sep):
                        return True
            else:
                for rule in allowed_rules:
                    if rule == "*" or rule is True:
                        return True
        except Exception as e:
            print(f"[Discord Policy] Error reading permission file {path}: {e}")
            
    return False

async def discord_approval_handler(tool_call) -> bool:
    """
    A custom approval handler for Google Antigravity safety policies.
    It intercepts tool execution, sends an HTTP request to the local Discord bot,
    and blocks until the user responds on Discord.

    NOTE: This handler is only reached for tool calls that are NOT already
    approved by the native policy.allow() rules in get_discord_policies().
    Pre-approved commands are auto-approved at a higher priority level and
    never reach this function.
    """
    # Extract tool details defensively
    tool_name = getattr(tool_call, "name", None) or getattr(tool_call, "tool_name", None)
    if not tool_name and isinstance(tool_call, dict):
        tool_name = tool_call.get("name") or tool_call.get("tool_name")
    tool_name = tool_name or "unknown"

    arguments = getattr(tool_call, "arguments", None)
    if not arguments and isinstance(tool_call, dict):
        arguments = tool_call.get("arguments")
    arguments = arguments or {}

    # Extract agent context (if available, e.g. from environment)
    agent_name = os.getenv("ANTIGRAVITY_AGENT_NAME", "ActiveAgent")
    conversation_id = os.getenv("ANTIGRAVITY_CONVERSATION_ID", str(uuid.uuid4()))

    payload = {
        "request_id": str(uuid.uuid4()),
        "agent_name": agent_name,
        "conversation_id": conversation_id,
        "tool_name": tool_name,
        "arguments": arguments,
        "ls_address": os.getenv("ANTIGRAVITY_LS_ADDRESS"),
        "ls_token": os.getenv("ANTIGRAVITY_CSRF_TOKEN")
    }

    port = resolve_sidecar_port()
    approval_url = f"http://127.0.0.1:{port}/approve"

    print(f"[Discord Policy] 🚀 Forwarding approval request to Discord for tool: {tool_name} (URL: {approval_url})")
    try:
        async with httpx.AsyncClient(timeout=305.0) as client:
            response = await client.post(approval_url, json=payload)
            if response.status_code == 200:
                data = response.json()
                approved = data.get("approved", False)
                result_str = "✅ APPROVED" if approved else "❌ DENIED"
                print(f"[Discord Policy] 🏁 Discord user response: {result_str}")
                return approved
            else:
                print(f"[Discord Policy] ⚠️ Server returned error: {response.status_code}")
                return False
    except Exception as e:
        print(f"[Discord Policy] ❌ Connection error: {e}")
        # Default to False (fail-safe close) in case of connection errors
        return False

class DiscordInteractionHook(hooks.OnInteractionHook):
    """
    Hook invoked when the agent needs user interaction (e.g. AskQuestion).
    It forwards the request to the Discord sidecar daemon and awaits user response.
    """
    async def run(self, context: hooks.HookContext, data: types.AskQuestionInteractionSpec) -> types.QuestionHookResult:
        agent_name = os.getenv("ANTIGRAVITY_AGENT_NAME", "ActiveAgent")
        conversation_id = os.getenv("ANTIGRAVITY_CONVERSATION_ID", str(uuid.uuid4()))

        questions_data = []
        for q in data.questions:
            opts = []
            for opt in q.options:
                opts.append({
                    "id": opt.id,
                    "text": opt.text
                })
            questions_data.append({
                "question": q.question,
                "options": opts,
                "is_multi_select": q.is_multi_select
            })

        payload = {
            "request_id": str(uuid.uuid4()),
            "agent_name": agent_name,
            "conversation_id": conversation_id,
            "questions": questions_data
        }

        port = resolve_sidecar_port()
        interaction_url = f"http://127.0.0.1:{port}/interaction"

        print(f"[Discord Policy] 🚀 Forwarding interaction request to Discord (URL: {interaction_url})")
        try:
            async with httpx.AsyncClient(timeout=305.0) as client:
                response = await client.post(interaction_url, json=payload)
                if response.status_code == 200:
                    res_data = response.json()
                    cancelled = res_data.get("cancelled", False)
                    responses = []
                    for r in res_data.get("responses", []):
                        responses.append(types.QuestionResponse(
                            selected_option_ids=r.get("selected_option_ids"),
                            freeform_response=r.get("freeform_response", ""),
                            skipped=r.get("skipped", False)
                        ))
                    return types.QuestionHookResult(responses=responses, cancelled=cancelled)
                else:
                    print(f"[Discord Policy] ⚠️ Server returned interaction error: {response.status_code}")
                    return types.QuestionHookResult(responses=[types.QuestionResponse(skipped=True)], cancelled=True)
        except Exception as e:
            print(f"[Discord Policy] ❌ Interaction connection error: {e}")
            return types.QuestionHookResult(responses=[types.QuestionResponse(skipped=True)], cancelled=True)

# Tools that require Discord approval when not pre-approved in IDE settings
_APPROVAL_TOOLS = [
    "run_command",
    "create_file",
    "edit_file",
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "generate_image",
    "start_subagent",
    "ask_permission",
]


def _make_allow_predicate(tool_name: str):
    """
    Returns a predicate function compatible with policy.allow(when=...) that
    returns True when the tool call is already approved in the IDE's native
    permission settings (global ~/.gemini/antigravity-ide/permissions.json,
    workspace .antigravity_permissions.json, or the AGY2 global file).

    Using policy.allow(when=predicate) rather than checking inside the
    discord_approval_handler ensures the native policy engine short-circuits
    at the highest-priority APPROVE bucket — the agent never pauses, Discord
    is never pinged, and no approval dialog is shown for pre-approved items.
    """
    def predicate(tool_call) -> bool:
        # tool_call is a ToolCall pydantic model; args is a dict
        args = {}
        if hasattr(tool_call, "args"):
            args = dict(tool_call.args) if tool_call.args else {}
        elif isinstance(tool_call, dict):
            args = tool_call.get("args", tool_call.get("arguments", {}))
        allowed = check_persistent_permission(tool_name, args)
        if allowed:
            print(f"[Discord Policy] ✅ Native pre-approval matched for: {tool_name}")
        return allowed
    predicate.__name__ = f"_is_natively_approved_{tool_name}"
    return predicate


def get_discord_policies():
    """
    Helper function to return the policy configuration list for the agent config.

    Policy evaluation order (highest priority first):
    1. policy.allow(tool, when=natively_approved)  — Auto-approve if already in IDE
       saved settings. No Discord ping, no dialog, fully transparent.
    2. policy.ask_user(tool, handler=discord_approval_handler)  — Route to Discord
       for anything not already pre-approved.

    This ensures Discord acts as a supplement to the IDE's native permission
    system, not a replacement for it.
    """
    # pyrefly: ignore [missing-import]
    from google.antigravity.hooks import policy
    policies = []
    for tool in _APPROVAL_TOOLS:
        # High-priority: auto-approve if in native IDE permission settings
        policies.append(
            policy.allow(tool, when=_make_allow_predicate(tool),
                         name=f"native-pre-approved-{tool}")
        )
        # Lower-priority fallback: send to Discord for manual approval
        policies.append(
            policy.ask_user(tool, handler=discord_approval_handler)
        )
    return policies

def get_discord_hooks():
    """
    Helper function to return the custom hooks for the agent config.
    Registers interaction handlers to route questions to Discord.
    """
    return [
        DiscordInteractionHook()
    ]

def send_discord_message(content: str, title: str = None, description: str = None) -> bool:
    """
    Helper to send a message or status update back to the Discord user's DM.
    """
    port = resolve_sidecar_port()
    url = f"http://127.0.0.1:{port}/message"
    payload = {
        "content": content,
        "embed_title": title,
        "embed_description": description
    }
    try:
        import requests
        response = requests.post(url, json=payload, timeout=10.0)
        return response.status_code == 200
    except Exception as e:
        print(f"[Discord Policy] Failed to send message to bot: {e}")
        return False
