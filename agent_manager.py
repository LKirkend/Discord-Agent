import os
import datetime
import json
import uuid
import time
import asyncio
import subprocess
import urllib.request
from typing import Optional, List, Tuple

import state
from helpers import get_project_folder_path

def execute_run_command(CommandLine: str, Cwd: Optional[str] = None) -> str:
    """
    Description:
        Runs a shell command on the local system inside a specific directory.
    Usage:
        result = execute_run_command(CommandLine, Cwd)
    Usage Example:
        res = execute_run_command("ls -la", "/Users/workspace")
    """
    try:
        res = subprocess.run(CommandLine, shell=True, cwd=Cwd, capture_output=True, text=True, timeout=300)
        return f"Stdout:\n{res.stdout}\nStderr:\n{res.stderr}\nExit Code: {res.returncode}"
    except Exception as e:
        return f"Error executing command: {e}"

def execute_list_dir(DirectoryPath: str) -> str:
    """
    Description:
        Lists files and folders inside a given directory.
    Usage:
        result = execute_list_dir(DirectoryPath)
    Usage Example:
        res = execute_list_dir("/Users/workspace")
    """
    try:
        items = os.listdir(DirectoryPath)
        res = []
        for item in items:
            p = os.path.join(DirectoryPath, item)
            is_dir = os.path.isdir(p)
            size = os.path.getsize(p) if not is_dir else 0
            res.append(f"{item} ({'dir' if is_dir else f'{size} bytes'})")
        return "\n".join(res)
    except Exception as e:
        return f"Error listing directory: {e}"

def execute_view_file(AbsolutePath: str, StartLine: int = 1, EndLine: Optional[int] = None) -> str:
    """
    Description:
        Views the content of a local file in a specified line range.
    Usage:
        result = execute_view_file(AbsolutePath, StartLine, EndLine)
    Usage Example:
        res = execute_view_file("/Users/workspace/file.txt", 10, 50)
    """
    try:
        with open(AbsolutePath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        start = max(0, StartLine - 1)
        end = len(lines) if EndLine is None else min(len(lines), EndLine)
        return "".join(lines[start:end])
    except Exception as e:
        return f"Error viewing file: {e}"

def execute_write_to_file(TargetFile: str, CodeContent: str, Overwrite: bool = False) -> str:
    """
    Description:
        Creates a new file or overwrites an existing one with contents.
    Usage:
        result = execute_write_to_file(TargetFile, CodeContent, Overwrite)
    Usage Example:
        res = execute_write_to_file("/Users/workspace/file.txt", "content", True)
    """
    try:
        if os.path.exists(TargetFile) and not Overwrite:
            return f"Error: File already exists and Overwrite is False."
        os.makedirs(os.path.dirname(TargetFile), exist_ok=True)
        with open(TargetFile, 'w', encoding='utf-8') as f:
            f.write(CodeContent)
        return "File written successfully."
    except Exception as e:
        return f"Error writing file: {e}"

def execute_replace_file_content(TargetFile: str, TargetContent: str, ReplacementContent: str) -> str:
    """
    Description:
        Edits an existing file by replacing a contiguous block of text.
    Usage:
        result = execute_replace_file_content(TargetFile, TargetContent, ReplacementContent)
    Usage Example:
        res = execute_replace_file_content("/Users/workspace/file.txt", "old", "new")
    """
    try:
        with open(TargetFile, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if TargetContent not in content:
            return f"Error: TargetContent not found in file."
        if content.count(TargetContent) > 1:
            return f"Error: Multiple occurrences of TargetContent found. Use more context."
        new_content = content.replace(TargetContent, ReplacementContent, 1)
        with open(TargetFile, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return "File replaced successfully."
    except Exception as e:
        return f"Error replacing file content: {e}"

def execute_grep_search(SearchPath: str, Query: str) -> str:
    """
    Description:
        Finds exact pattern matches within files or directories recursively.
    Usage:
        result = execute_grep_search(SearchPath, Query)
    Usage Example:
        res = execute_grep_search("/Users/workspace", "search query")
    """
    try:
        results = []
        if os.path.isfile(SearchPath):
            with open(SearchPath, 'r', encoding='utf-8', errors='ignore') as f:
                for idx, line in enumerate(f, 1):
                    if Query in line:
                        results.append(f"{SearchPath}:{idx}: {line.strip()}")
        else:
            for root, dirs, files in os.walk(SearchPath):
                for file in files:
                    fp = os.path.join(root, file)
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                            for idx, line in enumerate(f, 1):
                                if Query in line:
                                    results.append(f"{fp}:{idx}: {line.strip()}")
                                    if len(results) >= 50:
                                        break
                    except Exception:
                        continue
                    if len(results) >= 50:
                        break
                if len(results) >= 50:
                    break
        return "\n".join(results) if results else "No matches found."
    except Exception as e:
        return f"Error searching: {e}"

class OllamaChatResponse:
    """
    Description:
        Mock implementation of the Antigravity ChatResponse class.
    """
    def __init__(self, text_content: str):
        """
        Description:
            Initializer for OllamaChatResponse.
        Usage:
            resp = OllamaChatResponse(text_content)
        Usage Example:
            r = OllamaChatResponse("hello")
        """
        self._text = text_content
        
    async def text(self) -> str:
        """
        Description:
            Returns the text response.
        Usage:
            txt = await resp.text()
        Usage Example:
            t = await r.text()
        """
        return self._text

class OllamaAgent:
    """
    Description:
        Lightweight drop-in replacement Agent backend that executes tasks
        by calling a local Ollama instance (qwen2.5-coder:7b) and handling tools.
    """
    def __init__(self, config):
        """
        Description:
            Initializer for OllamaAgent.
        Usage:
            agent = OllamaAgent(config)
        Usage Example:
            a = OllamaAgent(config)
        """
        self._config = config
        self.conversation_id = config.conversation_id or str(uuid.uuid4())
        self.is_started = False
        self._history = []
        
    async def __aenter__(self):
        """
        Description:
            Enters agent context.
        """
        self.is_started = True
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Description:
            Exits agent context.
        """
        self.is_started = False
        
    async def chat(self, prompt: str) -> OllamaChatResponse:
        """
        Description:
            Sends a prompt to Ollama, receives tool calls or responses,
            executes tools after verifying permissions, and repeats until completion.
        Usage:
            response = await agent.chat(prompt)
        Usage Example:
            resp = await a.chat("do something")
        """
        self._history.append({"role": "user", "content": prompt})
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Execute a shell command on the local system.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "CommandLine": {"type": "string", "description": "The exact shell command to execute."},
                            "Cwd": {"type": "string", "description": "The directory to run the command in."}
                        },
                        "required": ["CommandLine"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "List the contents of a directory (files and subdirectories).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "DirectoryPath": {"type": "string", "description": "Absolute path to the directory."}
                        },
                        "required": ["DirectoryPath"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "view_file",
                    "description": "View the contents of a text file from the local filesystem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "AbsolutePath": {"type": "string", "description": "Absolute path to the file to view."},
                            "StartLine": {"type": "integer", "description": "1-indexed start line."},
                            "EndLine": {"type": "integer", "description": "1-indexed end line."}
                        },
                        "required": ["AbsolutePath"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_to_file",
                    "description": "Create a new file or overwrite an existing one with content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "TargetFile": {"type": "string", "description": "Absolute path to the target file."},
                            "CodeContent": {"type": "string", "description": "The contents to write."},
                            "Overwrite": {"type": "boolean", "description": "Whether to overwrite if file exists."}
                        },
                        "required": ["TargetFile", "CodeContent"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "replace_file_content",
                    "description": "Edit an existing file by replacing a contiguous block of text.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "TargetFile": {"type": "string", "description": "Absolute path to the target file."},
                            "TargetContent": {"type": "string", "description": "The exact string to be replaced."},
                            "ReplacementContent": {"type": "string", "description": "The replacement content."}
                        },
                        "required": ["TargetFile", "TargetContent", "ReplacementContent"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "grep_search",
                    "description": "Find exact pattern matches within files or directories.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "SearchPath": {"type": "string", "description": "The absolute path to search."},
                            "Query": {"type": "string", "description": "The search term or pattern."}
                        },
                        "required": ["SearchPath", "Query"]
                    }
                }
            }
        ]

        from discord_policy import check_persistent_permission, discord_approval_handler

        while True:
            url = f"{state.AGENT_ENDPOINT}/chat/completions"
            headers = {"Content-Type": "application/json"}
            data = {
                "model": state.LOCAL_MODEL_NAME,
                "messages": [
                    {"role": "system", "content": self._config.system_instructions or ""}
                ] + self._history,
                "tools": tools,
                "temperature": 0.2
            }
            
            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
            try:
                res_bytes = await asyncio.to_thread(self._send_request, req)
                res_data = json.loads(res_bytes.decode("utf-8"))
            except Exception as e:
                return OllamaChatResponse(f"Error communicating with local Ollama: {e}")
                
            choices = res_data.get("choices", [])
            if not choices:
                return OllamaChatResponse("Ollama returned an empty response.")
                
            message = choices[0].get("message", {})
            self._history.append(message)
            
            tool_calls = message.get("tool_calls", [])
            if not tool_calls:
                return OllamaChatResponse(message.get("content", ""))
                
            for tc in tool_calls:
                tc_id = tc.get("id")
                func = tc.get("function", {})
                name = func.get("name")
                args = json.loads(func.get("arguments", "{}"))
                
                tool_call_dict = {"name": name, "arguments": args}
                approved = check_persistent_permission(name, args)
                if not approved:
                    approved = await discord_approval_handler(tool_call_dict)
                    
                if not approved:
                    result_str = "Error: Tool execution denied by user policy."
                else:
                    if name == "run_command":
                        result_str = execute_run_command(**args)
                    elif name == "list_dir":
                        result_str = execute_list_dir(**args)
                    elif name == "view_file":
                        result_str = execute_view_file(**args)
                    elif name == "write_to_file":
                        result_str = execute_write_to_file(**args)
                    elif name == "replace_file_content":
                        result_str = execute_replace_file_content(**args)
                    elif name == "grep_search":
                        result_str = execute_grep_search(**args)
                    else:
                        result_str = f"Error: Unknown tool {name}"
                
                self._history.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": name,
                    "content": result_str
                })

    def _send_request(self, req) -> bytes:
        """Helper to send request using urllib."""
        with urllib.request.urlopen(req) as response:
            return response.read()

async def run_spawned_agent(prompt: str, channel, project_name: Optional[str] = None, convo_id: Optional[str] = None):
    """
    Description:
        Spawns a background agent turn using either Gemini or Ollama.
        Supports automatic fallback to Ollama on quota depletion.
    Usage:
        await run_spawned_agent(prompt, channel, project_name, convo_id)
    Usage Example:
        await run_spawned_agent("compile project", channel, "OpenFeedbackRemover", "session-id-123")
    """
    project_path = get_project_folder_path(project_name) if project_name else None
    
    old_cwd = os.getcwd()
    if project_path and os.path.exists(project_path):
        os.chdir(project_path)
        print(f"[Bot] Changed directory to {project_path} for project {project_name}")
        
    try:
        from google.antigravity import Agent, LocalAgentConfig
        import sys
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.append(script_dir)
        from discord_policy import get_discord_policies, get_discord_hooks
    except ImportError as e:
        await channel.send(f"❌ **Antigravity SDK is not available:** {e}")
        if project_path:
            os.chdir(old_cwd)
        return

    old_port = os.environ.get("ANTIGRAVITY_SIDECAR_WEB_PORT")
    old_agent_name = os.environ.get("ANTIGRAVITY_AGENT_NAME")
    old_convo_id = os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
    old_project_id = os.environ.get("ANTIGRAVITY_PROJECT_ID")
    
    os.environ["ANTIGRAVITY_SIDECAR_WEB_PORT"] = str(state.PORT)
    os.environ["ANTIGRAVITY_AGENT_NAME"] = "Liaison Agent"
    if "ANTIGRAVITY_CONVERSATION_ID" in os.environ:
        os.environ.pop("ANTIGRAVITY_CONVERSATION_ID")
        
    project_id = None
    if project_name:
        config_dir = os.path.expanduser("~/.gemini/config/projects")
        if os.path.exists(config_dir):
            for entry in os.listdir(config_dir):
                if entry.endswith(".json"):
                    try:
                        with open(os.path.join(config_dir, entry), "r") as f:
                            data = json.load(f)
                        if data.get("name") == project_name:
                            project_id = data.get("id")
                            break
                    except Exception:
                        pass
                        
    if project_id:
        os.environ["ANTIGRAVITY_PROJECT_ID"] = project_id

    status_msg = await channel.send(f"🤖 **Spawning background agent for `{project_name or 'Global'}`...**")
    
    config = LocalAgentConfig(
        system_instructions=(
            f"You are AGY2 Liaison Agent, a powerful pair-programming and command execution assistant. "
            f"Help the user execute commands, edit files, and solve tasks. "
            f"You are running in the workspace directory: {project_path or old_cwd} for project: {project_name or 'Global'}. "
            f"Since you are running persistently in the background, you communicate with the user via Discord DMs. "
            f"Always explain your actions and verify success. Use clean, professional markdown formatting."
        ),
        policies=get_discord_policies(),
        hooks=get_discord_hooks(),
        app_data_dir=state.APP_DATA_DIR,
    )
    
    convo_id = convo_id or str(uuid.uuid4())
    try:
        response = None
        os.environ["ANTIGRAVITY_CONVERSATION_ID"] = convo_id
        
        await status_msg.edit(content=f"🚀 **Agent active ({state.MODEL_PROVIDER}) and executing task...**\n• Project: `{project_name or 'Global'}`\n• Session ID: `{convo_id[:8]}`\n• Request: *{prompt}*")
        
        # 1. Attempt turn using current provider
        if state.MODEL_PROVIDER == "gemini":
            try:
                async with Agent(config) as agent:
                    raw_convo_id = getattr(agent, 'conversation_id', None)
                    if isinstance(raw_convo_id, str):
                        convo_id = raw_convo_id
                        os.environ["ANTIGRAVITY_CONVERSATION_ID"] = convo_id
                        await status_msg.edit(content=f"🚀 **Agent active (Gemini) and executing task...**\n• Project: `{project_name or 'Global'}`\n• Session ID: `{convo_id[:8]}`\n• Request: *{prompt}*")
                    response = await agent.chat(prompt)
            except Exception as e:
                err_msg = str(e)
                is_quota = any(q in err_msg.lower() for q in ["quota", "exhausted", "429", "rate limit", "resourceexhausted"])
                if state.AUTO_SWITCH_LOCAL and is_quota:
                    print(f"⚠️ Gemini quota exhausted. Automatically falling back to local model {state.LOCAL_MODEL_NAME}...")
                    state.MODEL_PROVIDER = "ollama"
                    await channel.send(f"⚠️ **Gemini API quota depleted (ResourceExhausted/429).** Automatically switching model provider to local model (`{state.LOCAL_MODEL_NAME}`) and retrying...")
                    # Let it fall through to the Ollama execution
                else:
                    raise e
                    
        if state.MODEL_PROVIDER == "ollama":
            async with OllamaAgent(config) as agent:
                convo_id = agent.conversation_id
                os.environ["ANTIGRAVITY_CONVERSATION_ID"] = convo_id
                await status_msg.edit(content=f"🚀 **Agent active (Ollama) and executing task...**\n• Project: `{project_name or 'Global'}`\n• Session ID: `{convo_id[:8]}`\n• Request: *{prompt}*")
                response = await agent.chat(prompt)

        text_val = None
        if response:
            text_val = response.text() if callable(response.text) else response.text
            import inspect
            if inspect.iscoroutine(text_val):
                text_val = await text_val

        await status_msg.edit(content=f"🏁 **Agent session `{convo_id[:8]}` concluded.**\n• Project: `{project_name or 'Global'}`\n• Request: *{prompt}*")
        
        if text_val:
            msg_to_send = f"🏆 **[Final Response - `{convo_id[:8]}`]**\n{text_val}"
            if len(msg_to_send) > 1900:
                chunks = [msg_to_send[i:i+1900] for i in range(0, len(msg_to_send), 1900)]
                for chunk in chunks:
                    await channel.send(chunk)
            else:
                await channel.send(msg_to_send)
        else:
            warning_msg = (
                f"⚠️ **[Warning - `{convo_id[:8]}`]** The agent completed the session but returned an empty response. "
                f"This may indicate an API quota limit (HTTP 429), block, or execution error. "
                f"Please check the local agent logs or try again."
            )
            await channel.send(warning_msg)
    except Exception as e:
        convo_id_display = convo_id[:8] if convo_id else "unknown"
        err_msg = f"❌ **Agent session `{convo_id_display}` failed:** {e}"
        if len(err_msg) > 1900:
            err_msg = err_msg[:1900] + "... (truncated)"
        await channel.send(err_msg)
    finally:
        if old_port is not None:
            os.environ["ANTIGRAVITY_SIDECAR_WEB_PORT"] = old_port
        else:
            os.environ.pop("ANTIGRAVITY_SIDECAR_WEB_PORT", None)
            
        if old_agent_name is not None:
            os.environ["ANTIGRAVITY_AGENT_NAME"] = old_agent_name
        else:
            os.environ.pop("ANTIGRAVITY_AGENT_NAME", None)
            
        if old_convo_id is not None:
            os.environ["ANTIGRAVITY_CONVERSATION_ID"] = old_convo_id
        else:
            os.environ.pop("ANTIGRAVITY_CONVERSATION_ID", None)
            
        if old_project_id is not None:
            os.environ["ANTIGRAVITY_PROJECT_ID"] = old_project_id
        else:
            os.environ.pop("ANTIGRAVITY_PROJECT_ID", None)
            
        os.chdir(old_cwd)

def send_agent_message(convo_id: str, message_content: str) -> bool:
    """
    Description:
        Delivers a chat message JSON file to an active agent conversation directory.
    Usage:
        success = send_agent_message(convo_id, message_content)
    Usage Example:
        success = send_agent_message("abc", "hello")
    """
    messages_dir = os.path.join(state.BRAIN_DIR, convo_id, ".system_generated", "messages")
    if not os.path.exists(messages_dir):
        try:
            os.makedirs(messages_dir, exist_ok=True)
        except Exception:
            return False
            
    msg_id = str(uuid.uuid4())
    msg_data = {
        "messageId": msg_id,
        "priority": "MESSAGE_PRIORITY_HIGH",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "renderDetails": {
            "messageTitle": "Message from User (via Discord)"
        },
        "content": message_content
    }
    
    msg_path = os.path.join(messages_dir, f"{msg_id}.json")
    try:
        with open(msg_path, 'w') as f:
            json.dump(msg_data, f)
        return True
    except Exception as e:
        print(f"Error writing message to agent: {e}")
        return False
