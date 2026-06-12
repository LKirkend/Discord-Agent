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
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Configure mock environment before importing bot.py
os.environ["DISCORD_BOT_TOKEN"] = "mock_token"
os.environ["DISCORD_USER_NAME"] = "Tig1"
os.environ["DISCORD_USER_ID"] = "12345"

import bot
from fastapi.testclient import TestClient

client = TestClient(bot.app)


class TestDiscordApprovalServerPolicy(unittest.TestCase):
    """
    Description:
        OOP test suite class for TestDiscordApprovalServerPolicy.
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

    @patch("httpx.AsyncClient.post")
    async def _test_discord_policy_handler_approved_async(self, mock_post):
        """Async helper for testing policy handler approval."""
        # Setup mock http response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"approved": True}
        mock_post.return_value = mock_resp

        import discord_policy
        tool_call = MagicMock()
        tool_call.name = "run_command"
        tool_call.arguments = {"CommandLine": "ls"}

        approved = await discord_policy.discord_approval_handler(tool_call)
        self.assertTrue(approved)

    @patch("httpx.AsyncClient.post")
    async def _test_discord_policy_handler_denied_async(self, mock_post):
        """Async helper for testing policy handler denial."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"approved": False}
        mock_post.return_value = mock_resp

        import discord_policy
        tool_call = MagicMock()
        tool_call.name = "run_command"
        tool_call.arguments = {"CommandLine": "rm -rf"}

        approved = await discord_policy.discord_approval_handler(tool_call)
        self.assertFalse(approved)

    @patch("httpx.AsyncClient.post")
    async def _test_discord_policy_handler_error_async(self, mock_post):
        """Async helper for testing policy handler handling errors."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        import discord_policy
        tool_call = MagicMock()
        tool_call.name = "run_command"

        approved = await discord_policy.discord_approval_handler(tool_call)
        self.assertFalse(approved)

    @patch("httpx.AsyncClient.post")
    async def _test_discord_policy_handler_connection_error_async(self, mock_post):
        """Async helper for testing policy handler handling exceptions."""
        mock_post.side_effect = Exception("Connection timed out")

        import discord_policy
        tool_call = MagicMock()
        tool_call.name = "run_command"

        approved = await discord_policy.discord_approval_handler(tool_call)
        self.assertFalse(approved)

    def test_discord_policy_handlers(self):
        """Test wrapper to run the async policy tests in the event loop."""
        self.loop.run_until_complete(self._test_discord_policy_handler_approved_async())
        self.loop.run_until_complete(self._test_discord_policy_handler_denied_async())
        self.loop.run_until_complete(self._test_discord_policy_handler_error_async())
        self.loop.run_until_complete(self._test_discord_policy_handler_connection_error_async())

    def test_discord_policy_reads_dynamic_port(self):
        """Test that discord_policy dynamically resolves the sidecar port from environment."""
        import discord_policy
        import importlib
        
        # Test with port 12345
        with patch.dict(os.environ, {"ANTIGRAVITY_SIDECAR_WEB_PORT": "12345"}):
            discord_policy._resolved_port_cache = None
            importlib.reload(discord_policy)
            self.assertEqual(discord_policy.DISCORD_APPROVAL_URL, "http://127.0.0.1:12345/approve")
            
        # Test with no env var (fallback to 18000)
        with patch.dict(os.environ, {}):
            if "ANTIGRAVITY_SIDECAR_WEB_PORT" in os.environ:
                del os.environ["ANTIGRAVITY_SIDECAR_WEB_PORT"]
            # Temporarily clear CSRF token to prevent the test from querying the real LS
            old_token = os.environ.pop("ANTIGRAVITY_CSRF_TOKEN", None)
            try:
                discord_policy._resolved_port_cache = None
                importlib.reload(discord_policy)
                self.assertEqual(discord_policy.DISCORD_APPROVAL_URL, "http://127.0.0.1:18000/approve")
            finally:
                if old_token:
                    os.environ["ANTIGRAVITY_CSRF_TOKEN"] = old_token
            
        # Restore default import state
        discord_policy._resolved_port_cache = None
        importlib.reload(discord_policy)

    def test_dangerous_command_check(self):
        """Test dangerous command checker detects destructive patterns."""
        from bot import is_dangerous_command
        self.assertTrue(is_dangerous_command("rm -rf file.txt"))
        self.assertTrue(is_dangerous_command("kill -9 1234"))
        self.assertTrue(is_dangerous_command("rmdir folder"))
        self.assertTrue(is_dangerous_command("dd if=/dev/zero of=/dev/null"))
        
        self.assertFalse(is_dangerous_command("git status"))
        self.assertFalse(is_dangerous_command("python3 main.py"))
        self.assertFalse(is_dangerous_command("echo warmup"))

    def test_command_matches_rule(self):
        """Test token-based prefix matching for command rules."""
        from discord_policy import command_matches_rule
        self.assertTrue(command_matches_rule("git commit -m msg", "git"))
        self.assertTrue(command_matches_rule("git commit -m msg", "git commit"))
        self.assertTrue(command_matches_rule("python3 -m pytest test.py", "python3 -m pytest"))
        
        self.assertFalse(command_matches_rule("python3", "python3 -m pytest"))
        self.assertFalse(command_matches_rule("gitstatus", "git"))

    @patch("discord_policy.os.path.exists")
    @patch("discord_policy.open")
    def test_check_persistent_permission(self, mock_open, mock_exists):
        """Test persistent permission cache lookup."""
        import json
        from discord_policy import check_persistent_permission
        
        mock_exists.return_value = True
        
        mock_perms = {
            "run_command": ["git", "python3 test.py"],
            "write_to_file": ["/Users/test/project"]
        }
        
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.read.return_value = json.dumps(mock_perms)
        mock_open.return_value = mock_file
        
        self.assertTrue(check_persistent_permission("run_command", {"CommandLine": "git status"}))
        self.assertTrue(check_persistent_permission("run_command", {"CommandLine": "python3 test.py --verbose"}))
        self.assertFalse(check_persistent_permission("run_command", {"CommandLine": "rm -rf"}))
        
        self.assertTrue(check_persistent_permission("write_to_file", {"TargetFile": "/Users/test/project/src/main.py"}))
        self.assertFalse(check_persistent_permission("write_to_file", {"TargetFile": "/Users/test/other_dir/file.txt"}))

    @patch("bot.bot")
    def test_interaction_endpoint_choices(self, mock_bot):
        """Test POST /interaction endpoint with multiple choice questions."""
        mock_bot.is_ready.return_value = True
        
        mock_user = MagicMock()
        mock_msg = MagicMock()
        
        fut_edit = self.loop.create_future()
        fut_edit.set_result(None)
        mock_msg.edit = MagicMock(return_value=fut_edit)
        
        async def mock_send(content, embed, view):
            request_id = "test-req-interaction_0"
            fut = bot.pending_interactions[request_id]
            fut.set_result({
                "selected_option_ids": ["1"],
                "freeform_response": "",
                "skipped": False
            })
            return mock_msg
            
        mock_user.send = MagicMock(side_effect=mock_send)
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)
        
        payload = {
            "request_id": "test-req-interaction",
            "agent_name": "TestAgent",
            "conversation_id": "test-conv",
            "questions": [
                {
                    "question": "Proceed with build?",
                    "options": [
                        {"id": "1", "text": "Yes"},
                        {"id": "2", "text": "No"}
                    ],
                    "is_multi_select": False
                }
            ]
        }
        
        response = client.post("/interaction", json=payload)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertFalse(res_json["cancelled"])
        self.assertEqual(len(res_json["responses"]), 1)
        self.assertEqual(res_json["responses"][0]["selected_option_ids"], ["1"])
        self.assertFalse(res_json["responses"][0]["skipped"])

    def test_command_matches_rule_wildcard(self):
        """Test command_matches_rule wildcard '*' support."""
        from discord_policy import command_matches_rule
        self.assertTrue(command_matches_rule("rm -rf /", "*"))
        self.assertTrue(command_matches_rule("git commit -m 'test'", "*"))

    @patch("discord_policy.os.path.exists")
    @patch("discord_policy.open")
    @patch("discord_policy.os.path.isdir")
    def test_check_persistent_permission_recursive_and_dual_globals(self, mock_isdir, mock_open, mock_exists):
        """Test check_persistent_permission walks up directories and checks both global files."""
        import json
        from discord_policy import check_persistent_permission
        
        expected_paths = []
        
        def mock_exists_fn(path):
            expected_paths.append(path)
            # Say permissions file exists at /Users/test/.antigravity_permissions.json
            if path == "/Users/test/.antigravity_permissions.json":
                return True
            # Say global config exists at ~/.gemini/antigravity-ide/permissions.json
            if "antigravity-ide/permissions.json" in path:
                return True
            return False
            
        mock_exists.side_effect = mock_exists_fn
        mock_isdir.return_value = True
        
        # Mock file data
        mock_perms_project = {
            "run_command": ["git status"]
        }
        mock_perms_global = {
            "run_command": ["python3 --version"]
        }
        
        # Create helper to open files with different mock content
        class MockFile:
            def __init__(self, content):
                self.content = content
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            def read(self):
                return self.content
                
        def mock_open_fn(path, *args, **kwargs):
            if "/Users/test/.antigravity_permissions.json" in path:
                return MockFile(json.dumps(mock_perms_project))
            if "antigravity-ide/permissions.json" in path:
                return MockFile(json.dumps(mock_perms_global))
            return MockFile("{}")
            
        mock_open.side_effect = mock_open_fn
        
        with patch("discord_policy.os.getcwd", return_value="/Users/test/dir1/dir2"):
            with patch("discord_policy.os.path.abspath", side_effect=lambda p: p):
                with patch("discord_policy.os.path.dirname", side_effect=lambda p: "/".join(p.split("/")[:-1]) if "/" in p else p):
                    # Check matching rule from project file (/Users/test/.antigravity_permissions.json)
                    self.assertTrue(check_persistent_permission("run_command", {"CommandLine": "git status"}))
                    # Check matching rule from global file (~/.gemini/antigravity-ide/permissions.json)
                    self.assertTrue(check_persistent_permission("run_command", {"CommandLine": "python3 --version"}))
                    # Check non-matching rule
                    self.assertFalse(check_persistent_permission("run_command", {"CommandLine": "rm -rf"}))


if __name__ == '__main__':
    unittest.main()
