import os
import sys
import unittest
import asyncio
import time
import warnings
import pytest
from unittest.mock import MagicMock, patch, mock_open

# Suppress third-party dependency warnings to keep test output clean
warnings.filterwarnings("ignore")
pytestmark = pytest.mark.filterwarnings("ignore")

# Ensure local imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Configure mock environment before importing bot.py
os.environ["DISCORD_BOT_TOKEN"] = "mock_token"
os.environ["DISCORD_USER_NAME"] = "Tig1"
os.environ["DISCORD_USER_ID"] = "12345"

import bot
from fastapi.testclient import TestClient

client = TestClient(bot.app)


class TestDiscordApprovalServerBot(unittest.TestCase):
    """
    Description:
        OOP test suite class for TestDiscordApprovalServerBot.
    """
    @classmethod
    def setUpClass(cls):
        # Set up a default event loop in the main thread so asyncio.Future() works
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()

    def setUp(self):
        bot.state.MODEL_PROVIDER = "gemini"
        bot.state.AGENT_PROVIDER = "gemini"
        bot.state.AUTO_SWITCH_LOCAL = False

    @patch("bot.bot")
    @patch("psutil.process_iter")
    def test_get_training_status_info_no_process(self, mock_process_iter, mock_bot):
        """Test status checks when no training processes exist."""
        mock_process_iter.return_value = []
        
        # Test get_training_status_info logic
        with patch("glob.glob", return_value=[]):
            status = bot.get_training_status_info()
            self.assertIn("No active python training processes found", status)
            self.assertIn("No task log files found", status)

    @patch("bot.bot")
    @patch("psutil.process_iter")
    def test_get_training_status_info_with_process(self, mock_process_iter, mock_bot):
        """Test status checks when training process is active."""
        # Setup mock process
        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 9999,
            'name': 'python3'
        }
        mock_proc.pid = 9999
        mock_proc.cmdline.return_value = ['python', 'scripts/train_feedback_model.py', '--epochs', '60']
        mock_proc.cwd.return_value = '/Users/logankirkendall/Documents/antigravity/OpenFeedbackRemover'
        mock_process_iter.return_value = [mock_proc]

        with patch("glob.glob", return_value=[]):
            status = bot.get_training_status_info()
            self.assertIn("Active Training Processes", status)
            self.assertIn("9999", status)
            self.assertIn("train_feedback_model.py", status)

    @patch("bot.bot")
    @patch("glob.glob")
    @patch("os.path.getmtime")
    def test_get_training_status_info_with_logs(self, mock_getmtime, mock_glob, mock_bot):
        """Test reading training status logs snippets."""
        mock_glob.return_value = ["/path/to/task-123.log"]
        mock_getmtime.return_value = 1600000000.0
        
        mock_log_content = "Epoch 1  Loss 0.5  Acc 92.5%\nEpoch 2  Loss 0.3  Acc 95.1%\n"
        
        with patch("builtins.open", mock_open(read_data=mock_log_content)):
            with patch("psutil.process_iter", return_value=[]):
                status = bot.get_training_status_info()
                self.assertIn("task-123.log", status)
                self.assertIn("Epoch 2  Loss 0.3  Acc 95.1%", status)

    @patch("bot.bot")
    @patch("bot.DISCORD_BOT_TOKEN", "mock_token")
    def test_get_status_ui_active(self, mock_bot):
        """Test /status returns Active HTML when bot is connected."""
        mock_bot.is_ready.return_value = True
        with patch("bot.discover_agent_sessions", return_value=[]):
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)
            html = response.text
            self.assertIn("Active", html)
            self.assertIn("#10b981", html)

    @patch("bot.bot")
    @patch("bot.DISCORD_BOT_TOKEN", "mock_token")
    @patch("time.time")
    def test_get_status_ui_connecting(self, mock_time, mock_bot):
        """Test /status returns Connecting HTML when bot is initializing within startup window."""
        mock_bot.is_ready.return_value = False
        bot.START_TIME = 1000.0
        mock_time.return_value = 1010.0
        with patch("bot.discover_agent_sessions", return_value=[]):
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)
            html = response.text
            self.assertIn("Connecting", html)
            self.assertIn("#f59e0b", html)

    @patch("bot.bot")
    @patch("bot.DISCORD_BOT_TOKEN", "mock_token")
    @patch("time.time")
    def test_get_status_ui_disconnected(self, mock_time, mock_bot):
        """Test /status returns Disconnected HTML when bot remains offline past startup window."""
        mock_bot.is_ready.return_value = False
        bot.START_TIME = 1000.0
        mock_time.return_value = 1040.0
        with patch("bot.discover_agent_sessions", return_value=[]):
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)
            html = response.text
            self.assertIn("Disconnected", html)
            self.assertIn("#ef4444", html)

    @patch("bot.bot")
    @patch("bot.DISCORD_BOT_TOKEN", None)
    def test_get_status_ui_config_warning(self, mock_bot):
        """Test /status returns Config Warning HTML when bot token is unset."""
        with patch("bot.discover_agent_sessions", return_value=[]):
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)
            html = response.text
            self.assertIn("Config Warning", html)
            self.assertIn("#f59e0b", html)

    @patch("bot.bot")
    @patch("bot.DISCORD_BOT_TOKEN", "mock_token")
    def test_get_status_api_active(self, mock_bot):
        """Test /api/status returns correct JSON when bot is connected."""
        mock_bot.is_ready.return_value = True
        with patch("bot.discover_agent_sessions", return_value=[]):
            response = client.get("/api/status")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status_label"], "Active")
            self.assertEqual(data["status_color"], "#10b981")
            self.assertEqual(data["active_sessions"], 0)

    def test_discover_agent_sessions_no_brain(self):
        """Test session discovery with nonexistent brain directory."""
        with patch("bot.BRAIN_DIR", "/nonexistent/path"):
            sessions = bot.discover_agent_sessions()
            self.assertEqual(sessions, [])

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("os.path.isdir")
    @patch("glob.glob")
    @patch("psutil.process_iter")
    def test_discover_agent_sessions_mocked(self, mock_process_iter, mock_glob, mock_isdir, mock_listdir, mock_exists):
        """Test discovery of valid and invalid sessions."""
        def exists_mock(path):
            if path == "/brain":
                return True
            if "session-1" in path and ("task.md" in path or "tasks" in path):
                return True
            return False
        mock_exists.side_effect = exists_mock
        mock_listdir.return_value = ["session-1", "session-empty", ".hidden-dir"]
        
        # isdir mock: only session directories are True
        def isdir_mock(path):
            return "session-1" in path or "session-empty" in path
        mock_isdir.side_effect = isdir_mock
        
        # glob mock for tasks
        def glob_mock(pattern):
            if "session-1" in pattern:
                return ["/brain/session-1/.system_generated/tasks/task-1.log"]
            return []
        mock_glob.side_effect = glob_mock
        
        # mock open file reads
        mock_log_content = "# Target Goal Name\n- [ ] Todo"
        
        # Mock process iter
        mock_process_iter.return_value = []

        with patch("bot.BRAIN_DIR", "/brain"):
            with patch("builtins.open", mock_open(read_data=mock_log_content)):
                with patch("os.path.getmtime", return_value=time.time()):
                    sessions = bot.discover_agent_sessions()
                    
                    # We expect session-1 to be discovered (it has log files or task.md)
                    # session-empty has neither so it should be skipped
                    self.assertEqual(len(sessions), 1)
                    self.assertEqual(sessions[0]["convo_id"], "session-1")
                    self.assertEqual(sessions[0]["goal_name"], "Target Goal Name")

    def test_get_discord_policies(self):
        """Test policy hooks generation — each tool gets an allow (native pre-check) and ask_user (Discord fallback)."""
        import discord_policy
        with patch("google.antigravity.hooks.policy.ask_user") as mock_ask_user, \
             patch("google.antigravity.hooks.policy.allow") as mock_allow:
            discord_policy.get_discord_policies()
            # Each of the 9 tools should get one allow() and one ask_user() call
            self.assertEqual(mock_ask_user.call_count, 9)
            self.assertEqual(mock_allow.call_count, 9)
            ask_calls = [c[0][0] for c in mock_ask_user.call_args_list]
            allow_calls = [c[0][0] for c in mock_allow.call_args_list]
            for tool in ["run_command", "create_file", "edit_file", "write_to_file",
                         "replace_file_content", "multi_replace_file_content",
                         "generate_image", "start_subagent", "ask_permission"]:
                self.assertIn(tool, ask_calls)
                self.assertIn(tool, allow_calls)

    def test_make_allow_predicate(self):
        """Test _make_allow_predicate returns a predicate that delegates to check_persistent_permission."""
        import discord_policy
        from unittest.mock import MagicMock, patch

        predicate = discord_policy._make_allow_predicate("run_command")
        self.assertEqual(predicate.__name__, "_is_natively_approved_run_command")

        # Build a mock ToolCall with args dict
        mock_tool_call = MagicMock()
        mock_tool_call.args = {"CommandLine": "git status"}

        with patch.object(discord_policy, "check_persistent_permission", return_value=True) as mock_check:
            result = predicate(mock_tool_call)
            self.assertTrue(result)
            mock_check.assert_called_once_with("run_command", {"CommandLine": "git status"})

        with patch.object(discord_policy, "check_persistent_permission", return_value=False) as mock_check:
            result = predicate(mock_tool_call)
            self.assertFalse(result)

    @patch("requests.post")
    def test_send_discord_message_helper_success(self, mock_post):
        """Test sending message via helper successfully."""
        import discord_policy
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        success = discord_policy.send_discord_message("Hello from helper")
        self.assertTrue(success)

    @patch("requests.post")
    def test_send_discord_message_helper_failure(self, mock_post):
        """Test helper handles failed requests."""
        import discord_policy
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        success = discord_policy.send_discord_message("Hello from helper")
        self.assertFalse(success)

    @patch("requests.post")
    def test_send_discord_message_helper_exception(self, mock_post):
        """Test helper handles exceptions."""
        import discord_policy
        mock_post.side_effect = Exception("API error")

        success = discord_policy.send_discord_message("Hello from helper")
        self.assertFalse(success)
    @patch("bot.bot")
    @patch("bot.discover_agent_sessions")
    @patch("builtins.open")
    @patch("os.path.exists")
    async def _test_transcript_monitor_filtering_async(self, mock_exists, mock_open_file, mock_sessions, mock_bot):
        """Test transcript monitor concurrent tracking and filtering of tool-invocation messages."""
        mock_exists.return_value = True
        mock_bot.is_ready.return_value = True
        
        mock_sessions.return_value = [
            {"convo_id": "session12345678"},
            {"convo_id": "sessionabcdefgh"}
        ]
        
        mock_user = MagicMock()
        fut_send = self.loop.create_future()
        fut_send.set_result(None)
        mock_user.send = MagicMock(return_value=fut_send)
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)
        
        # Test logs setup
        lines_session1 = [
            '{"step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Initial step"}',
            '{"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "I will run ls", "tool_calls": [{"name": "run_command"}]}',
            '{"step_index": 2, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Task completed successfully", "tool_calls": []}'
        ]
        
        lines_session2 = [
            '{"step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Initial step"}',
            '{"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Hello from session 2", "tool_calls": []}'
        ]
        
        file_mocks = {
            "session12345678": lines_session1,
            "sessionabcdefgh": lines_session2
        }
        
        def mock_open_fn(path, *args, **kwargs):
            for k, lines in file_mocks.items():
                if k in path:
                    return mock_open(read_data="\n".join(lines) + "\n")()
            return mock_open()()
            
        mock_open_file.side_effect = mock_open_fn
        
        # Clear tracker state
        bot.last_processed_steps.clear()
        
        with patch("bot.BRAIN_DIR", "/"):
            # Step 1: Initial tracking setup
            await bot.transcript_monitor.coro()
            self.assertEqual(bot.last_processed_steps["session12345678"], 2)
            self.assertEqual(bot.last_processed_steps["sessionabcdefgh"], 1)
            
            # Reset indexes to 0 to simulate new logs processing
            bot.last_processed_steps["session12345678"] = 0
            bot.last_processed_steps["sessionabcdefgh"] = 0
            
            # Step 2: process new lines
            await bot.transcript_monitor.coro()
            
            # Verify user.send messages
            send_calls = [c[0][0] for c in mock_user.send.call_args_list]
            # Verify session prefix prefixing and content presence
            self.assertTrue(any("Task completed successfully" in c and "session1" in c for c in send_calls))
            self.assertTrue(any("Hello from session 2" in c and "sessiona" in c for c in send_calls))
            # The tool call message should be filtered out
            self.assertFalse(any("I will run ls" in c for c in send_calls))

    @patch("bot.PORT", 12345)
    @patch("google.antigravity.Agent")
    @patch("google.antigravity.LocalAgentConfig")
    async def _test_run_spawned_agent_async(self, mock_config, mock_agent_class, mock_channel):
        """Test agent spawner setup, safety policies config, environment scoping, and termination message."""
        mock_agent_instance = MagicMock()
        
        mock_response = MagicMock()
        mock_response.text = "Mocked Agent Response Text"
        
        fut_chat = self.loop.create_future()
        fut_chat.set_result(mock_response)
        mock_agent_instance.chat = MagicMock(return_value=fut_chat)
        
        fut_context = self.loop.create_future()
        fut_context.set_result(mock_agent_instance)
        
        mock_agent_class.return_value.__aenter__ = MagicMock(return_value=fut_context)
        mock_agent_class.return_value.__aexit__ = MagicMock(return_value=self.loop.create_future())
        mock_agent_class.return_value.__aexit__.return_value.set_result(None)
        
        mock_msg = MagicMock()
        fut_edit = self.loop.create_future()
        fut_edit.set_result(None)
        mock_msg.edit = MagicMock(return_value=fut_edit)
        
        fut_send = self.loop.create_future()
        fut_send.set_result(mock_msg)
        mock_channel.send = MagicMock(return_value=fut_send)
        
        # Verify run_spawned_agent execution
        await bot.run_spawned_agent("run pytest", mock_channel)
        
        mock_agent_instance.chat.assert_called_once_with("run pytest")
        
        send_calls = [c[0][0] for c in mock_channel.send.call_args_list]
        self.assertTrue(any("Mocked Agent Response Text" in c for c in send_calls))
        self.assertTrue(any("Spawning background agent" in c for c in send_calls))

    @patch("bot.discover_agent_sessions", return_value=[])
    @patch("bot.run_spawned_agent")
    async def _test_on_message_spawns_agent_async(self, mock_run_spawned_agent, mock_discover_sessions):
        """Test receiving a DM message automatically spawns a background agent."""
        temp_bot = bot.create_bot(use_message_content=True)
        
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.author.id = 12345
        mock_message.guild = None
        mock_message.content = "run pytest in Discord-Agent"
        mock_message.channel = MagicMock()
        
        fut_process = self.loop.create_future()
        fut_process.set_result(None)
        temp_bot.process_commands = MagicMock(return_value=fut_process)
        
        await temp_bot.on_message(mock_message)
        
        # Allow task on the loop to run
        await asyncio.sleep(0.1)
        mock_run_spawned_agent.assert_called_once_with("run pytest in Discord-Agent", mock_message.channel)

    @patch("bot.discover_agent_sessions")
    @patch("bot.send_agent_message", return_value=True)
    async def _test_on_message_routes_to_active_agent_async(self, mock_send_agent_message, mock_discover_sessions):
        """Test receiving a message routes it to an active agent if one exists."""
        temp_bot = bot.create_bot(use_message_content=True)
        
        mock_discover_sessions.return_value = [
            {
                'convo_id': 'active-session-123',
                'goal_name': 'My Active Goal',
                'status': 'Active',
                'latest_mtime': time.time(),
                'task_path': '/path/to/task.md',
                'active_tasks': []
            }
        ]
        
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.author.id = 12345
        mock_message.guild = None
        mock_message.content = "do the next step"
        
        mock_channel = MagicMock()
        mock_channel.send = MagicMock(return_value=self.loop.create_future())
        mock_channel.send.return_value.set_result(None)
        mock_message.channel = mock_channel
        
        fut_process = self.loop.create_future()
        fut_process.set_result(None)
        temp_bot.process_commands = MagicMock(return_value=fut_process)
        
        await temp_bot.on_message(mock_message)
        
        mock_send_agent_message.assert_called_once_with('active-session-123', "do the next step")
        mock_channel.send.assert_called_once()
        sent_content = mock_channel.send.call_args[0][0]
        self.assertIn("Prompt routed to active agent", sent_content)

    @patch("bot.discover_agent_sessions")
    @patch("bot.scan_active_processes")
    @patch("os.path.exists")
    @patch("builtins.open")
    def test_project_dashboard_features(self, mock_open, mock_exists, mock_scan, mock_sessions):
        """Test project resolver, build_dashboard_ui, and build_project_menu_ui."""
        mock_exists.return_value = True
        mock_scan.return_value = []
        
        # Mock sessions
        mock_sessions.return_value = [
            {
                "convo_id": "session12345678",
                "goal_name": "Fix some bugs",
                "latest_log": "/logs/1",
                "latest_mtime": 1000.0,
                "status": "Active",
                "task_path": None,
                "active_tasks": []
            },
            {
                "convo_id": "sessionabcdefgh",
                "goal_name": "Write documentation",
                "latest_log": "/logs/2",
                "latest_mtime": 900.0,
                "status": "Idle",
                "task_path": None,
                "active_tasks": []
            }
        ]
        
        # Mock file reads for transcripts to resolve project names
        lines_session1 = ['{"content": "I am in /Users/logankirkendall/Documents/antigravity/Discord-Agent-IDE/bot.py"}']
        lines_session2 = ['{"content": "I am in /Users/logankirkendall/Documents/antigravity/other-project/src/main.py"}']
        
        file_mocks = {
            "session12345678": lines_session1,
            "sessionabcdefgh": lines_session2
        }
        
        class MockFile:
            def __init__(self, content):
                self.content = content
                self.lines = content.splitlines(keepends=True)
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            def read(self, *args, **kwargs):
                return self.content
            def readlines(self, *args, **kwargs):
                return self.lines
            def __iter__(self):
                return iter(self.lines)
                
        def mock_open_fn(path, *args, **kwargs):
            for k, lines in file_mocks.items():
                if k in path:
                    return MockFile("\n".join(lines) + "\n")
            return MockFile("")
            
        mock_open.side_effect = mock_open_fn
        
        # Test helper
        proj1 = bot.get_session_project("session12345678")
        proj2 = bot.get_session_project("sessionabcdefgh")
        self.assertEqual(proj1, "Discord-Agent-IDE")
        self.assertEqual(proj2, "other-project")
        
        # Test build_dashboard_ui
        embed, view = bot.build_dashboard_ui()
        self.assertIsNotNone(embed)
        self.assertIsNotNone(view)
        
        # Check buttons in view
        buttons = [item for item in view.children if isinstance(item, bot.discord.ui.Button)]
        custom_ids = [btn.custom_id for btn in buttons]
        self.assertTrue(any("dash_proj_" in cid for cid in custom_ids))
        
        # Test build_project_menu_ui
        embed_proj, view_proj = bot.build_project_menu_ui("Discord-Agent-IDE")
        self.assertIsNotNone(embed_proj)
        self.assertIsNotNone(view_proj)
        
        # Check buttons in project view
        buttons_proj = [item for item in view_proj.children if isinstance(item, bot.discord.ui.Button)]
        custom_ids_proj = [btn.custom_id for btn in buttons_proj]
        self.assertTrue(any("dash_sess_" in cid for cid in custom_ids_proj))
        self.assertTrue(any("dash_proj_back" in cid for cid in custom_ids_proj))

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open")
    def test_get_project_folder_path(self, mock_open, mock_listdir, mock_exists):
        """Test getting project CWD from project config JSON files."""
        mock_exists.return_value = True
        mock_listdir.return_value = ["proj1.json", "proj2.json", "invalid.txt"]
        
        proj1_json = {
            "name": "DeCorrelationEngine",
            "projectResources": {
                "resources": [
                    {
                        "gitFolder": {
                            "folderUri": "file:///Users/logankirkendall/CorrelationEngine"
                        }
                    }
                ]
            }
        }
        
        proj2_json = {
            "name": "Discord-Agent-IDE",
            "projectResources": {
                "resources": [
                    {
                        "folderUri": "file:///Users/logankirkendall/Documents/antigravity/Discord-Agent-IDE"
                    }
                ]
            }
        }
        
        import json
        file_mocks = {
            "proj1.json": json.dumps(proj1_json),
            "proj2.json": json.dumps(proj2_json)
        }
        
        class MockFile:
            def __init__(self, content):
                self.content = content
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            def read(self, *args, **kwargs):
                return self.content
                
        def mock_open_fn(path, *args, **kwargs):
            for k, content in file_mocks.items():
                if k in path:
                    return MockFile(content)
            return MockFile("")
            
        mock_open.side_effect = mock_open_fn
        
        path1 = bot.get_project_folder_path("DeCorrelationEngine")
        path2 = bot.get_project_folder_path("Discord-Agent-IDE")
        path_none = bot.get_project_folder_path("Nonexistent")
        
        self.assertEqual(path1, "/Users/logankirkendall/CorrelationEngine")
        self.assertEqual(path2, "/Users/logankirkendall/Documents/antigravity/Discord-Agent-IDE")
        self.assertIsNone(path_none)

    @patch("bot.bot")
    @patch("bot.DISCORD_USER_ID", "12345")
    def test_message_chunking(self, mock_bot):
        """Test chunking of messages in /message endpoint when length exceeds 1900."""
        mock_bot.is_ready.return_value = True
        
        mock_user = MagicMock()
        sent_messages = []
        
        async def mock_send(content, *args, **kwargs):
            sent_messages.append(content)
            return MagicMock()
            
        mock_user.send = MagicMock(side_effect=mock_send)
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)
        
        # Send a 4000 character message
        long_content = "A" * 4000
        payload = {
            "content": long_content,
            "embed_title": "Test Title"
        }
        
        response = client.post("/message", json=payload)
        self.assertEqual(response.status_code, 200)
        
        # Verify it was split into 3 chunks
        self.assertEqual(len(sent_messages), 3)
        self.assertEqual(sum(len(msg) for msg in sent_messages), 4000)

    @patch("bot.bot")
    @patch("bot.DISCORD_USER_ID", "12345")
    @patch("os.path.exists")
    @patch("os.path.isdir")
    @patch("os.listdir")
    @patch("builtins.open")
    def test_pending_items_checker(self, mock_open, mock_listdir, mock_isdir, mock_exists, mock_bot):
        """Test scanning and notifying of pending plans and memory approvals."""
        mock_bot.is_ready.return_value = True
        mock_exists.return_value = True
        mock_isdir.return_value = True
        
        # Mock brain dir listing containing a session
        mock_listdir.return_value = ["session_abc"]
        
        # Mock metadata JSON file content
        metadata_json = {
            "artifactType": "ARTIFACT_TYPE_IMPLEMENTATION_PLAN",
            "requestFeedback": True,
            "summary": "Mock plan summary"
        }
        
        import json
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(metadata_json)
        
        # Populate in-memory active_pending_items
        import time
        bot.active_pending_items["req_1"] = {
            "type": "permission",
            "convo_id": "session_abc",
            "project_name": "TestProject",
            "tool_name": "run_command",
            "arguments": {"CommandLine": "ls"},
            "agent_name": "TestAgent",
            "timestamp": time.time()
        }
        
        mock_user = MagicMock()
        sent_messages = []
        async def mock_send(content, *args, **kwargs):
            sent_messages.append(content)
            return MagicMock()
        mock_user.send = MagicMock(side_effect=mock_send)
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)
        
        # Run checker as launch
        self.loop.run_until_complete(bot.check_pending_notifications(is_launch=True))
        
        # Check that we sent a message summarizing BOTH the pending plan and the memory approval
        self.assertTrue(len(sent_messages) > 0)
        combined_text = "".join(sent_messages)
        self.assertIn("Mock plan summary", combined_text)
        self.assertIn("run_command", combined_text)
        
        # Clean up
        bot.active_pending_items.clear()
        bot.notified_pending_keys.clear()

    @patch("bot.discover_agent_sessions")
    @patch("os.path.exists")
    @patch("builtins.open")
    def test_dashboard_enhancements_and_consolidation(self, mock_open, mock_exists, mock_sessions):
        """Test new features: get_last_completed_action, is_session_awaiting_approval, and get_session_project worktree parsing."""
        mock_exists.return_value = True
        
        # 1. Test get_session_project with worktree path
        file_content_worktree = '{"content": "I am in /Users/logankirkendall/.gemini/antigravity/worktrees/OpenFeedbackRemover/plugin/Source/PluginProcessor.cpp"}'
        mock_open.return_value.__enter__.return_value.readlines.return_value = [file_content_worktree]
        mock_open.return_value.__enter__.return_value.__iter__.return_value = iter([file_content_worktree])
        
        proj = bot.get_session_project("session_worktree")
        self.assertEqual(proj, "OpenFeedbackRemover")

        # 2. Test get_last_completed_action parsing
        transcript_lines = [
            '{"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "hello"}',
            '{"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "thinking", "tool_calls": [{"name": "run_command", "args": {"toolAction": "Checking status"}}]}'
        ]
        mock_open.return_value.__enter__.return_value.readlines.return_value = transcript_lines
        mock_open.return_value.__enter__.return_value.__iter__.return_value = iter(transcript_lines)
        
        last_action = bot.get_last_completed_action("session_worktree")
        self.assertEqual(last_action, "Calling: Checking status")

        # Test fallback tool call description
        transcript_lines_fallback = [
            '{"step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "thinking", "tool_calls": [{"name": "list_dir"}]}'
        ]
        mock_open.return_value.__enter__.return_value.readlines.return_value = transcript_lines_fallback
        mock_open.return_value.__enter__.return_value.__iter__.return_value = iter(transcript_lines_fallback)
        last_action_fallback = bot.get_last_completed_action("session_worktree")
        self.assertEqual(last_action_fallback, "Running tool: list_dir")

        # 3. Test is_session_awaiting_approval
        pending_plans = [{"convo_id": "session_1", "project_name": "OpenFeedbackRemover"}]
        pending_approvals = []
        pending_interactions = []
        
        self.assertTrue(bot.is_session_awaiting_approval("session_1", pending_plans, pending_approvals, pending_interactions))
        self.assertFalse(bot.is_session_awaiting_approval("session_2", pending_plans, pending_approvals, pending_interactions))

    @patch("bot.bot")
    @patch("bot.discover_agent_sessions")
    @patch("builtins.open")
    @patch("os.path.exists")
    async def _test_message_consolidation_async(self, mock_exists, mock_open_file, mock_sessions, mock_bot):
        mock_exists.return_value = True
        mock_bot.is_ready.return_value = True
        
        mock_sessions.return_value = [
            {"convo_id": "session_c1234567"}
        ]
        
        mock_msg = MagicMock()
        mock_msg.author = mock_bot.user
        mock_msg.content = "💬 **[Agent `session_`]**\nFirst line of response"
        
        fut_edit = self.loop.create_future()
        fut_edit.set_result(None)
        mock_msg.edit = MagicMock(return_value=fut_edit)
        
        mock_dm_channel = MagicMock()
        
        class AsyncIter:
            def __init__(self, items):
                self.items = items
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self.items:
                    raise StopAsyncIteration
                return self.items.pop(0)
                
        mock_dm_channel.history = MagicMock(return_value=AsyncIter([mock_msg]))
        
        mock_user = MagicMock()
        mock_user.dm_channel = mock_dm_channel
        
        fut_send = self.loop.create_future()
        fut_send.set_result(mock_msg)
        mock_user.send = MagicMock(return_value=fut_send)
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)
        
        lines = [
            '{"step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "First line of response"}',
            '{"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Second line of response", "tool_calls": []}'
        ]
        
        def mock_open_fn(path, *args, **kwargs):
            return mock_open(read_data="\n".join(lines) + "\n")()
            
        mock_open_file.side_effect = mock_open_fn
        
        bot.last_processed_steps.clear()
        
        with patch("bot.BRAIN_DIR", "/"):
            # Initial tracking setup
            await bot.transcript_monitor.coro()
            self.assertEqual(bot.last_processed_steps["session_c1234567"], 1)
            
            # Reset to index 0
            bot.last_processed_steps["session_c1234567"] = 0
            
            # Execute loop (consolidation should trigger)
            await bot.transcript_monitor.coro()
            
            mock_msg.edit.assert_called_once()
            call_content = mock_msg.edit.call_args[1].get("content") if "content" in mock_msg.edit.call_args[1] else mock_msg.edit.call_args[0][0]
            self.assertIn("First line of response", call_content)
            self.assertIn("Second line of response", call_content)

    @patch("time.sleep")
    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_extract_and_prepare_files_polling(self, mock_isfile, mock_exists, mock_sleep):
        """Test that extract_and_prepare_files polls for file existence if it does not exist immediately."""
        mock_exists.side_effect = [False, False, True]
        mock_isfile.return_value = True
        
        seen = set()
        path = "/fake/walkthrough.md"
        text = f"[walkthrough](file://{path})"
        
        with patch("discord.File") as mock_file:
            res, files = bot.extract_and_prepare_files(text, seen)
            self.assertEqual(res, "**walkthrough (Attached)**")
            self.assertEqual(len(files), 1)
            self.assertEqual(mock_sleep.call_count, 2)

    @patch("bot.PORT", 12345)
    @patch("google.antigravity.Agent")
    @patch("google.antigravity.LocalAgentConfig")
    async def _test_run_spawned_agent_empty_warning_async(self, mock_config, mock_agent_class, mock_channel):
        """Test run_spawned_agent sends a warning message when the agent response is empty."""
        mock_agent_instance = MagicMock()
        
        mock_response = MagicMock()
        mock_response.text = ""
        
        fut_chat = self.loop.create_future()
        fut_chat.set_result(mock_response)
        mock_agent_instance.chat = MagicMock(return_value=fut_chat)
        
        fut_context = self.loop.create_future()
        fut_context.set_result(mock_agent_instance)
        
        mock_agent_class.return_value.__aenter__ = MagicMock(return_value=fut_context)
        mock_agent_class.return_value.__aexit__ = MagicMock(return_value=self.loop.create_future())
        mock_agent_class.return_value.__aexit__.return_value.set_result(None)
        
        mock_msg = MagicMock()
        fut_edit = self.loop.create_future()
        fut_edit.set_result(None)
        mock_msg.edit = MagicMock(return_value=fut_edit)
        
        fut_send = self.loop.create_future()
        fut_send.set_result(mock_msg)
        mock_channel.send = MagicMock(return_value=fut_send)
        
        await bot.run_spawned_agent("run empty agent check", mock_channel)
        
        send_calls = [c[0][0] for c in mock_channel.send.call_args_list]
        self.assertTrue(any("Warning" in c and "empty response" in c for c in send_calls))

    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_extract_and_prepare_files_raw_urls(self, mock_isfile, mock_exists):
        """Test that extract_and_prepare_files parses raw and parenthesized file:// URLs."""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        
        seen = set()
        text = "Check out (file:///Users/logankirkendall/task.md) and file:///Users/logankirkendall/walkthrough.md"
        
        with patch("discord.File") as mock_file:
            res, files = bot.extract_and_prepare_files(text, seen)
            self.assertIn(" (Attached)**", res)
            self.assertEqual(len(files), 2)

    @patch("bot.DISCORD_USER_ID", "12345")
    @patch("bot.update_env_file")
    async def _test_on_ready_dm_purge_async(self, mock_update_env):
        """Test that on_ready event purges old DM history on startup."""
        temp_bot = bot.create_bot(use_message_content=True)
        
        from unittest.mock import PropertyMock
        with patch.object(type(temp_bot), "user", new_callable=PropertyMock) as mock_user_prop:
            mock_bot_user = MagicMock()
            mock_user_prop.return_value = mock_bot_user
            
            mock_user = MagicMock()
            mock_dm_channel = MagicMock()
            
            mock_msg = MagicMock()
            mock_msg.author = mock_bot_user
            
            class AsyncIter:
                def __init__(self, items):
                    self.items = items
                def __aiter__(self):
                    return self
                async def __anext__(self):
                    if not self.items:
                        raise StopAsyncIteration
                    return self.items.pop(0)
                    
            mock_dm_channel.history = MagicMock(return_value=AsyncIter([mock_msg]))
            mock_user.dm_channel = mock_dm_channel
            
            fut_user = self.loop.create_future()
            fut_user.set_result(mock_user)
            temp_bot.fetch_user = MagicMock(return_value=fut_user)
            
            with patch.object(bot.dashboard_updater, "is_running", return_value=True), \
                 patch.object(bot.transcript_monitor, "is_running", return_value=True), \
                 patch.object(bot.check_pending_loop, "is_running", return_value=True):
                 
                await temp_bot.on_ready()
                
            mock_msg.delete.assert_called_once()

    @patch("bot.bot")
    @patch("bot.DISCORD_USER_ID", "12345")
    async def _test_update_dashboard_pinning_async(self, mock_bot):
        """Test that update_dashboard reuses the first pinned dashboard and unpins other bot dashboards."""
        mock_bot.is_ready.return_value = True
        
        mock_user = MagicMock()
        mock_dm_channel = MagicMock()
        
        mock_pin_user = MagicMock()
        mock_pin_user.author.id = 99999
        mock_pin_user.id = 111
        
        mock_pin_bot_1 = MagicMock()
        mock_pin_bot_1.author.id = mock_bot.user.id
        mock_pin_bot_1.id = 222
        embed1 = MagicMock()
        embed1.title = "Multi-Agent System Dashboard"
        mock_pin_bot_1.embeds = [embed1]
        
        mock_pin_bot_2 = MagicMock()
        mock_pin_bot_2.author.id = mock_bot.user.id
        mock_pin_bot_2.id = 444
        embed2 = MagicMock()
        embed2.title = "Multi-Agent System Dashboard"
        mock_pin_bot_2.embeds = [embed2]
        
        fut_unpin_1 = self.loop.create_future()
        fut_unpin_1.set_result(None)
        mock_pin_bot_1.unpin = MagicMock(return_value=fut_unpin_1)
        
        fut_unpin_2 = self.loop.create_future()
        fut_unpin_2.set_result(None)
        mock_pin_bot_2.unpin = MagicMock(return_value=fut_unpin_2)
        
        fut_edit_1 = self.loop.create_future()
        fut_edit_1.set_result(None)
        mock_pin_bot_1.edit = MagicMock(return_value=fut_edit_1)
        
        mock_dm_channel.pins = MagicMock(return_value=self.loop.create_future())
        mock_dm_channel.pins.return_value.set_result([mock_pin_user, mock_pin_bot_1, mock_pin_bot_2])
        
        class AsyncIter:
            def __init__(self, items):
                self.items = items
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self.items:
                    raise StopAsyncIteration
                return self.items.pop(0)
        mock_dm_channel.history = MagicMock(return_value=AsyncIter([]))
        mock_user.dm_channel = mock_dm_channel
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)
        
        bot.dashboard_msg = None
        
        await bot.update_dashboard()
        
        mock_pin_bot_1.edit.assert_called_once()
        mock_pin_bot_2.unpin.assert_called_once()
        mock_pin_bot_1.unpin.assert_not_called()
        mock_pin_user.unpin.assert_not_called()

    @patch("bot.bot")
    @patch("bot.DISCORD_USER_ID", "12345")
    async def _test_update_dashboard_new_pin_async(self, mock_bot):
        """
        Description:
            Test that update_dashboard sends and pins a new dashboard if none exists.
        Usage:
            await self._test_update_dashboard_new_pin_async(mock_bot)
        Usage Example:
            await self._test_update_dashboard_new_pin_async(mock_bot)
        """
        mock_bot.is_ready.return_value = True
        
        mock_user = MagicMock()
        mock_dm_channel = MagicMock()
        
        mock_dm_channel.pins = MagicMock(return_value=self.loop.create_future())
        mock_dm_channel.pins.return_value.set_result([])
        
        class AsyncIter:
            def __init__(self, items):
                self.items = items
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self.items:
                    raise StopAsyncIteration
                return self.items.pop(0)
        mock_dm_channel.history = MagicMock(return_value=AsyncIter([]))
        mock_user.dm_channel = mock_dm_channel
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)
        
        mock_dashboard_msg = MagicMock()
        mock_dashboard_msg.id = 333
        fut_pin = self.loop.create_future()
        fut_pin.set_result(None)
        mock_dashboard_msg.pin = MagicMock(return_value=fut_pin)
        
        fut_send = self.loop.create_future()
        fut_send.set_result(mock_dashboard_msg)
        mock_user.send = MagicMock(return_value=fut_send)
        mock_dm_channel.send = mock_user.send
        
        bot.dashboard_msg = None
        
        await bot.update_dashboard()
        
        mock_user.send.assert_called_once()
        mock_dashboard_msg.pin.assert_called_once()

    async def _test_clear_command_async(self):
        """Test that the clear command purges guild channels and deletes bot messages in DMs."""
        temp_bot = bot.create_bot(use_message_content=True)
        clear_cmd = temp_bot.get_command("clear")
        self.assertIsNotNone(clear_cmd)
        
        # Test Case 1: Guild Channel (has purge)
        mock_ctx_guild = MagicMock()
        mock_guild_channel = MagicMock()
        fut_purge = self.loop.create_future()
        fut_purge.set_result(None)
        mock_guild_channel.purge = MagicMock(return_value=fut_purge)
        mock_ctx_guild.channel = mock_guild_channel
        
        fut_status_send = self.loop.create_future()
        mock_status_msg = MagicMock()
        fut_delete_status = self.loop.create_future()
        fut_delete_status.set_result(None)
        mock_status_msg.delete = MagicMock(return_value=fut_delete_status)
        fut_status_send.set_result(mock_status_msg)
        mock_ctx_guild.send = MagicMock(return_value=fut_status_send)
        
        await clear_cmd.callback(mock_ctx_guild)
        mock_guild_channel.purge.assert_called_once()
        mock_status_msg.delete.assert_called_once()
        
        # Test Case 2: DM Channel (no purge, uses history)
        mock_ctx_dm = MagicMock()
        mock_dm_channel = MagicMock()
        delattr(mock_dm_channel, "purge")
        mock_ctx_dm.channel = mock_dm_channel
        
        fut_status_send_dm = self.loop.create_future()
        mock_status_msg_dm = MagicMock()
        fut_delete_status_dm = self.loop.create_future()
        fut_delete_status_dm.set_result(None)
        mock_status_msg_dm.delete = MagicMock(return_value=fut_delete_status_dm)
        fut_status_send_dm.set_result(mock_status_msg_dm)
        mock_ctx_dm.send = MagicMock(return_value=fut_status_send_dm)
        
        from unittest.mock import PropertyMock
        with patch.object(type(temp_bot), "user", new_callable=PropertyMock) as mock_user_prop:
            mock_bot_user = MagicMock()
            mock_bot_user.id = 12345
            mock_user_prop.return_value = mock_bot_user
            
            mock_bot_msg = MagicMock()
            mock_bot_msg.author.id = 12345
            mock_bot_msg.id = 555
            fut_delete_bot = self.loop.create_future()
            fut_delete_bot.set_result(None)
            mock_bot_msg.delete = MagicMock(return_value=fut_delete_bot)
            
            mock_other_msg = MagicMock()
            mock_other_msg.author.id = 99999
            mock_other_msg.id = 666
            mock_other_msg.delete = MagicMock()
            
            class AsyncIter:
                def __init__(self, items):
                    self.items = items
                def __aiter__(self):
                    return self
                async def __anext__(self):
                    if not self.items:
                        raise StopAsyncIteration
                    return self.items.pop(0)
                    
            mock_dm_channel.history = MagicMock(return_value=AsyncIter([mock_bot_msg, mock_other_msg]))
            
            await clear_cmd.callback(mock_ctx_dm)
            mock_bot_msg.delete.assert_called_once()
            mock_other_msg.delete.assert_not_called()

    @patch("web_server.get_discord_target")
    @patch("httpx.AsyncClient.post")
    async def _test_openai_proxy_ollama_async(self, mock_httpx_post, mock_get_target):
        """
        Description:
            Verifies the non-streaming OpenAI compatible completions proxy endpoint maps
            and resolves local Ollama parameters correctly.
        Usage:
            await self._test_openai_proxy_ollama_async()
        Usage Example:
            await self._test_openai_proxy_ollama_async()
        """
        # Mock Discord target
        mock_target = MagicMock()
        fut_send = self.loop.create_future()
        fut_send.set_result(None)
        mock_target.send = MagicMock(return_value=fut_send)
        mock_get_target.return_value = mock_target

        # Mock httpx completion response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello, I am a local assistant."
                    }
                }
            ]
        }
        mock_httpx_post.return_value = mock_resp

        # Configure state
        bot.state.MODEL_PROVIDER = "ollama"
        bot.state.AGENT_ENDPOINT = "http://localhost:11434/v1"
        bot.state.AGENT_MODEL_NAME = "qwen2.5-coder:7b"

        # Make request
        payload = {
            "messages": [
                {"role": "user", "content": "Tell me a joke."}
            ],
            "stream": False
        }
        response = client.post("/v1/chat/completions", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hello, I am a local assistant.", response.json()["choices"][0]["message"]["content"])
        
        # Wait a tiny bit for background task to dispatch to Discord
        await asyncio.sleep(0.1)
        mock_target.send.assert_called()

    @patch("web_server.get_discord_target")
    @patch("httpx.AsyncClient.stream")
    async def _test_openai_proxy_stream_async(self, mock_httpx_stream, mock_get_target):
        """
        Description:
            Verifies the streaming completions proxy endpoint processes chunks correctly,
            pipes them back to the client, and sends the final response to Discord.
        Usage:
            await self._test_openai_proxy_stream_async()
        Usage Example:
            await self._test_openai_proxy_stream_async()
        """
        # Mock Discord target
        mock_target = MagicMock()
        fut_send = self.loop.create_future()
        fut_send.set_result(None)
        mock_target.send = MagicMock(return_value=fut_send)
        mock_get_target.return_value = mock_target

        # Mock streaming context manager & async iterator
        class MockStreamResponse:
            def __init__(self):
                self.status_code = 200
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            async def aiter_bytes(self):
                chunks = [
                    b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
                    b'data: {"choices": [{"delta": {"content": " world"}}]}\n\n',
                    b'data: [DONE]\n\n'
                ]
                for chunk in chunks:
                    yield chunk

        mock_httpx_stream.return_value = MockStreamResponse()

        # Configure state
        bot.state.MODEL_PROVIDER = "ollama"

        # Make request
        payload = {
            "messages": [
                {"role": "user", "content": "Hello stream."}
            ],
            "stream": True
        }
        
        with client.stream("POST", "/v1/chat/completions", json=payload) as response:
            self.assertEqual(response.status_code, 200)
            body = b"".join(response.iter_bytes())
            self.assertIn(b"Hello", body)
            self.assertIn(b"world", body)

        # Wait for background task to send to Discord
        await asyncio.sleep(0.1)
        mock_target.send.assert_called()

    @patch("httpx.AsyncClient.get")
    async def _test_openai_models_async(self, mock_httpx_get):
        """
        Description:
            Verifies the list models endpoint resolves models correctly depending
            on active model provider settings.
        Usage:
            await self._test_openai_models_async()
        Usage Example:
            await self._test_openai_models_async()
        """
        # Mock Ollama models response if active
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "object": "list",
            "data": [
                {"id": "qwen2.5-coder:7b", "object": "model"}
            ]
        }
        mock_httpx_get.return_value = mock_resp

        # 1. Test Ollama mode
        bot.state.MODEL_PROVIDER = "ollama"
        bot.state.AGENT_ENDPOINT = "http://localhost:11434/v1"
        response = client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["id"], "qwen2.5-coder:7b")

        # 2. Test Gemini mode
        bot.state.MODEL_PROVIDER = "gemini"
        response = client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["id"], "gemini-2.5-flash")

    async def _test_registered_user_constraint_async(self):
        """
        Description:
            Verifies that messages from other (non-registered) users are ignored.
        Usage:
            await self._test_registered_user_constraint_async()
        Usage Example:
            await self._test_registered_user_constraint_async()
        """
        temp_bot = bot.create_bot(use_message_content=True)
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.author.name = "MaliciousUser"
        mock_message.author.id = 99999
        mock_message.content = "Run rm -rf /"
        
        fut_proc = self.loop.create_future()
        fut_proc.set_result(None)
        temp_bot.process_commands = MagicMock(return_value=fut_proc)
        
        with patch.dict(os.environ, {"DISCORD_USER_ID": "12345", "DISCORD_USER_NAME": "Tig1"}):
            await temp_bot.on_message(mock_message)
            temp_bot.process_commands.assert_not_called()

    @patch("bot.run_spawned_agent")
    async def _test_server_thread_routing_async(self, mock_run_agent):
        """
        Description:
            Verifies that prompt invocations in a server channel create a thread,
            and replies inside the thread continue the conversation.
        Usage:
            await self._test_server_thread_routing_async()
        Usage Example:
            await self._test_server_thread_routing_async()
        """
        temp_bot = bot.create_bot(use_message_content=True)
        
        mock_msg_server = MagicMock()
        mock_msg_server.author.bot = False
        mock_msg_server.author.id = 12345
        mock_msg_server.guild = MagicMock()
        mock_msg_server.channel.name = "agent-discussion"
        mock_msg_server.content = "Build something"
        
        mock_thread = MagicMock()
        fut_thread_send = self.loop.create_future()
        fut_thread_send.set_result(None)
        mock_thread.send = MagicMock(return_value=fut_thread_send)
        
        fut_create_thread = self.loop.create_future()
        fut_create_thread.set_result(mock_thread)
        mock_msg_server.create_thread = MagicMock(return_value=fut_create_thread)
        
        fut_proc = self.loop.create_future()
        fut_proc.set_result(None)
        temp_bot.process_commands = MagicMock(return_value=fut_proc)
        
        with patch.dict(os.environ, {"DISCORD_USER_ID": "12345"}):
            await temp_bot.on_message(mock_msg_server)
            mock_msg_server.create_thread.assert_called_once()
            mock_run_agent.assert_called_once()

    @patch("bot.bot")
    @patch("bot.discover_agent_sessions")
    @patch("bot.scan_active_processes")
    async def _test_dashboard_pin_cleaning_async(self, mock_scan, mock_sessions, mock_bot):
        """
        Description:
            Verifies update_dashboard pins a single dashboard, cleans duplicate pins,
            and skips deleting the dashboard on DM purge.
        Usage:
            await self._test_dashboard_pin_cleaning_async()
        Usage Example:
            await self._test_dashboard_pin_cleaning_async()
        """
        mock_sessions.return_value = []
        mock_scan.return_value = []
        
        mock_bot.is_ready.return_value = True
        mock_bot.user.id = 12345
        
        mock_user = MagicMock()
        mock_dm = MagicMock()
        
        mock_pm1 = MagicMock()
        mock_pm1.author.id = 12345
        mock_pm1.id = 101
        embed_mock1 = MagicMock()
        embed_mock1.title = "🖥️ Multi-Agent System Dashboard"
        mock_pm1.embeds = [embed_mock1]
        
        mock_pm2 = MagicMock()
        mock_pm2.author.id = 12345
        mock_pm2.id = 102
        embed_mock2 = MagicMock()
        embed_mock2.title = "🖥️ Multi-Agent System Dashboard"
        mock_pm2.embeds = [embed_mock2]
        
        fut_delete = self.loop.create_future()
        fut_delete.set_result(None)
        mock_pm2.delete = MagicMock(return_value=fut_delete)
        
        fut_unpin2 = self.loop.create_future()
        fut_unpin2.set_result(None)
        mock_pm2.unpin = MagicMock(return_value=fut_unpin2)
        
        fut_edit1 = self.loop.create_future()
        fut_edit1.set_result(None)
        mock_pm1.edit = MagicMock(return_value=fut_edit1)
        
        fut_pins = self.loop.create_future()
        fut_pins.set_result([mock_pm1, mock_pm2])
        mock_dm.pins = MagicMock(return_value=fut_pins)
        
        fut_create_dm = self.loop.create_future()
        fut_create_dm.set_result(mock_dm)
        mock_user.create_dm = MagicMock(return_value=fut_create_dm)
        mock_user.dm_channel = mock_dm
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)
        
        # Mocking dm history for cleaning obsolete messages
        class AsyncIter:
            def __init__(self, items):
                self.items = items
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self.items:
                    raise StopAsyncIteration
                return self.items.pop(0)
        mock_dm.history = MagicMock(return_value=AsyncIter([mock_pm2]))
        
        bot.state.dashboard_msg = None
        with patch.dict(os.environ, {"DISCORD_USER_ID": "12345"}):
            await bot.update_dashboard()
            mock_pm2.delete.assert_called_once()

    async def _test_multi_provider_routing_async(self):
        """
        Description:
            Verifies resolve_target_and_payload routes all new providers to the correct URLs,
            headers, and payloads based on settings.
        Usage:
            await self._test_multi_provider_routing_async()
        Usage Example:
            await self._test_multi_provider_routing_async()
        """
        import web_server
        import state
        
        # Test Case 1: deepseek
        state.MODEL_PROVIDER = "deepseek"
        state.DEEPSEEK_API_KEY = "ds-key"
        state.DEEPSEEK_MODEL_NAME = "deepseek-coder"
        url, pay, head = web_server.resolve_target_and_payload({"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(head.get("Authorization"), "Bearer ds-key")
        self.assertEqual(pay.get("model"), "deepseek-coder")
        
        # Test Case 2: groq
        state.MODEL_PROVIDER = "groq"
        state.GROQ_API_KEY = "g-key"
        state.GROQ_MODEL_NAME = "mixtral"
        url, pay, head = web_server.resolve_target_and_payload({"messages": []})
        self.assertEqual(url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(head.get("Authorization"), "Bearer g-key")
        self.assertEqual(pay.get("model"), "mixtral")

        # Test Case 3: huggingface
        state.MODEL_PROVIDER = "huggingface"
        state.HF_API_KEY = "hf-key"
        state.HF_MODEL_NAME = "custom-hf-model"
        url, pay, head = web_server.resolve_target_and_payload({"messages": []})
        self.assertEqual(url, "https://api-inference.huggingface.co/v1/chat/completions")
        self.assertEqual(head.get("Authorization"), "Bearer hf-key")
        self.assertEqual(pay.get("model"), "custom-hf-model")

    async def _test_claude_translation_and_stream_async(self):
        """
        Description:
            Verifies Anthropic Claude payload translation, non-streaming translation,
            and streaming chunk parsing and conversion to OpenAI format.
        Usage:
            await self._test_claude_translation_and_stream_async()
        Usage Example:
            await self._test_claude_translation_and_stream_async()
        """
        import web_server
        import state
        
        # 1. Verify Payload Translation
        state.MODEL_PROVIDER = "claude"
        state.CLAUDE_API_KEY = "c-key"
        state.CLAUDE_MODEL_NAME = "claude-3-5"
        raw_req = {
            "messages": [
                {"role": "system", "content": "You are a helper"},
                {"role": "user", "content": "Hello"}
            ]
        }
        url, pay, head = web_server.resolve_target_and_payload(raw_req)
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(head.get("x-api-key"), "c-key")
        self.assertEqual(pay.get("system"), "You are a helper")
        self.assertEqual(len(pay.get("messages")), 1)
        self.assertEqual(pay.get("messages")[0]["role"], "user")
        
        # 2. Verify Non-Streaming Translation
        claude_res = {
            "id": "msg_123",
            "content": [{"type": "text", "text": "Hi back"}],
            "stop_reason": "end_turn",
            "model": "claude-3-5",
            "usage": {"input_tokens": 5, "output_tokens": 10}
        }
        openai_res = web_server.translate_claude_response_to_openai(claude_res)
        self.assertEqual(openai_res["choices"][0]["message"]["content"], "Hi back")
        self.assertEqual(openai_res["choices"][0]["finish_reason"], "stop")
        self.assertEqual(openai_res["usage"]["prompt_tokens"], 5)

    @patch("web_server.update_settings_in_env")
    async def _test_update_settings_multi_provider_async(self, mock_update):
        """
        Description:
            Verifies SettingsRequest accepts multi-provider fields and triggers update_settings_in_env.
        Usage:
            await self._test_update_settings_multi_provider_async()
        Usage Example:
            await self._test_update_settings_multi_provider_async()
        """
        import web_server
        from fastapi.testclient import TestClient
        
        client = TestClient(web_server.app)
        settings_payload = {
            "model_provider": "deepseek",
            "auto_switch_local": True,
            "discord_bot_permissions": "12345",
            "deepseek_api_key": "new-ds-key",
            "deepseek_model_name": "deepseek-reasoner"
        }
        response = client.post("/api/settings", json=settings_payload)
        self.assertEqual(response.status_code, 200)
        mock_update.assert_called_once()

    @patch("web_server.state")
    async def _test_force_server_chat_routing_async(self, mock_state):
        """
        Description:
            Verifies get_discord_target ignores DM routing and resolves to a guild
            text channel when FORCE_SERVER_CHAT is True.
        Usage:
            await self._test_force_server_chat_routing_async()
        Usage Example:
            await self._test_force_server_chat_routing_async()
        """
        import web_server
        
        mock_state.FORCE_SERVER_CHAT = True
        mock_state.bot.is_ready.return_value = True
        
        mock_guild = MagicMock()
        mock_chan1 = MagicMock()
        mock_chan1.name = "agent-discussion"
        mock_chan1.permissions_for.return_value.send_messages = True
        
        mock_guild.text_channels = [mock_chan1]
        mock_state.bot.guilds = [mock_guild]
        
        target = await web_server.get_discord_target()
        self.assertEqual(target, mock_chan1)
        mock_state.bot.fetch_user.assert_not_called()

    @patch("bot.state")
    @patch("bot.discover_agent_sessions")
    @patch("bot.scan_active_processes")
    async def _test_force_server_chat_dashboard_async(self, mock_scan, mock_sessions, mock_state):
        """
        Description:
            Verifies update_dashboard targets guild text channels instead of DM
            when FORCE_SERVER_CHAT is True.
        Usage:
            await self._test_force_server_chat_dashboard_async()
        Usage Example:
            await self._test_force_server_chat_dashboard_async()
        """
        import bot
        
        mock_sessions.return_value = []
        mock_scan.return_value = []
        
        mock_state.FORCE_SERVER_CHAT = True
        mock_state.bot.is_ready.return_value = True
        mock_state.bot.user.id = 12345
        
        mock_guild = MagicMock()
        mock_chan = MagicMock()
        mock_chan.name = "agent-dashboard"
        mock_chan.permissions_for.return_value.send_messages = True
        
        fut_pins = self.loop.create_future()
        fut_pins.set_result([])
        mock_chan.pins = MagicMock(return_value=fut_pins)
        
        fut_send = self.loop.create_future()
        mock_msg = MagicMock()
        mock_msg.id = 333
        fut_send.set_result(mock_msg)
        mock_chan.send = MagicMock(return_value=fut_send)
        
        fut_pin = self.loop.create_future()
        fut_pin.set_result(None)
        mock_msg.pin = MagicMock(return_value=fut_pin)
        
        mock_guild.text_channels = [mock_chan]
        mock_state.bot.guilds = [mock_guild]
        
        bot.dashboard_msg = None
        await bot.update_dashboard()
        
        mock_chan.send.assert_called_once()
        mock_msg.pin.assert_called_once()

    @patch("os._exit")
    async def _test_restart_daemon_async(self, mock_exit):
        """
        Description:
            Verifies the restart daemon API endpoint initiates a shutdown / exit.
        Usage:
            await self._test_restart_daemon_async()
        Usage Example:
            await self._test_restart_daemon_async()
        """
        import web_server
        from fastapi.testclient import TestClient
        
        test_client = TestClient(web_server.app)
        response = test_client.post("/api/restart-daemon")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        
        await asyncio.sleep(1.1)
        mock_exit.assert_called_once_with(0)

    @patch("psutil.process_iter")
    @patch("sys.exit")
    @patch("os.getpid")
    def test_check_single_instance_running(self, mock_getpid, mock_exit, mock_process_iter):
        """
        Description:
            Verifies check_single_instance exits with code 1 if another bot.py process is active.
        Usage:
            test_check_single_instance_running(mock_getpid, mock_exit, mock_process_iter)
        Usage Example:
            test_check_single_instance_running(mock_getpid, mock_exit, mock_process_iter)
        """
        mock_getpid.return_value = 1234
        
        # Mocking process info
        mock_proc = MagicMock()
        mock_proc.pid = 5678
        mock_proc.info = {"name": "python3"}
        mock_proc.cmdline.return_value = ["/path/to/venv/bin/python", "-u", "/path/to/bot.py"]
        
        mock_process_iter.return_value = [mock_proc]
        
        bot.check_single_instance()
        
        mock_exit.assert_called_once_with(1)

    @patch("psutil.process_iter")
    @patch("sys.exit")
    @patch("os.getpid")
    def test_check_single_instance_not_running(self, mock_getpid, mock_exit, mock_process_iter):
        """
        Description:
            Verifies check_single_instance does not exit if no other bot.py process is active.
        Usage:
            test_check_single_instance_not_running(mock_getpid, mock_exit, mock_process_iter)
        Usage Example:
            test_check_single_instance_not_running(mock_getpid, mock_exit, mock_process_iter)
        """
        mock_getpid.return_value = 1234
        
        # Mocking process info for self only
        mock_proc_self = MagicMock()
        mock_proc_self.pid = 1234
        mock_proc_self.info = {"name": "python3"}
        mock_proc_self.cmdline.return_value = ["/path/to/venv/bin/python", "-u", "/path/to/bot.py"]
        
        # Mocking process info for another python process that is not bot.py
        mock_proc_other = MagicMock()
        mock_proc_other.pid = 5678
        mock_proc_other.info = {"name": "python3"}
        mock_proc_other.cmdline.return_value = ["/path/to/venv/bin/python", "some_other_script.py"]
        
        mock_process_iter.return_value = [mock_proc_self, mock_proc_other]
        
        bot.check_single_instance()
        
        mock_exit.assert_not_called()

    def test_new_features_execution(self):
        """Test wrapper for running new async test cases on the event loop."""
        self.loop.run_until_complete(self._test_transcript_monitor_filtering_async())
        self.loop.run_until_complete(self._test_run_spawned_agent_async(mock_channel=MagicMock()))
        self.loop.run_until_complete(self._test_run_spawned_agent_empty_warning_async(mock_channel=MagicMock()))
        self.loop.run_until_complete(self._test_on_message_spawns_agent_async())
        self.loop.run_until_complete(self._test_on_message_routes_to_active_agent_async())
        self.loop.run_until_complete(self._test_message_consolidation_async())
        self.loop.run_until_complete(self._test_on_ready_dm_purge_async())
        self.loop.run_until_complete(self._test_update_dashboard_pinning_async())
        self.loop.run_until_complete(self._test_update_dashboard_new_pin_async())
        self.loop.run_until_complete(self._test_clear_command_async())
        self.loop.run_until_complete(self._test_openai_proxy_ollama_async())
        self.loop.run_until_complete(self._test_openai_proxy_stream_async())
        self.loop.run_until_complete(self._test_openai_models_async())
        self.loop.run_until_complete(self._test_registered_user_constraint_async())
        self.loop.run_until_complete(self._test_server_thread_routing_async())
        self.loop.run_until_complete(self._test_dashboard_pin_cleaning_async())
        self.loop.run_until_complete(self._test_multi_provider_routing_async())
        self.loop.run_until_complete(self._test_claude_translation_and_stream_async())
        self.loop.run_until_complete(self._test_update_settings_multi_provider_async())
        self.loop.run_until_complete(self._test_force_server_chat_routing_async())
        self.loop.run_until_complete(self._test_force_server_chat_dashboard_async())
        self.loop.run_until_complete(self._test_restart_daemon_async())

if __name__ == '__main__':
    unittest.main()
