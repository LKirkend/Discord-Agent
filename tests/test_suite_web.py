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


class TestDiscordApprovalServerWeb(unittest.TestCase):
    """
    Description:
        OOP test suite class for TestDiscordApprovalServerWeb.
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
    def test_approve_endpoint_bot_not_ready(self, mock_bot):
        """Test POST /approve returns 503 if bot is offline."""
        mock_bot.is_ready.return_value = False
        
        payload = {
            "agent_name": "TestAgent",
            "conversation_id": "test-conv",
            "tool_name": "run_command",
            "arguments": {"CommandLine": "ls"}
        }
        
        response = client.post("/approve", json=payload)
        self.assertEqual(response.status_code, 503)
        self.assertIn("Discord bot is not ready", response.json()["detail"])

    @patch("bot.bot")
    def test_approve_endpoint_success_approved(self, mock_bot):
        """Test /approve endpoint returns approved status when approved by user."""
        mock_bot.is_ready.return_value = True
        
        # Mock User and Message objects
        mock_user = MagicMock()
        mock_msg = MagicMock()
        
        # Mock msg.edit to be awaitable
        fut_edit = self.loop.create_future()
        fut_edit.set_result(None)
        mock_msg.edit = MagicMock(return_value=fut_edit)
        
        # Create future in loop context
        fut_send = self.loop.create_future()
        fut_send.set_result(mock_msg)
        mock_user.send = MagicMock(return_value=fut_send)
        
        # Create future for fetch_user
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)

        # We need to simulate the click on view. The endpoint awaits view.wait().
        async def mock_wait_approved(view_self):
            # Resolve approval future as True
            fut = bot.pending_approvals[view_self.request_id]
            fut.set_result(True)
            return None

        payload = {
            "request_id": "test-req-id-1",
            "agent_name": "TestAgent",
            "conversation_id": "test-conv",
            "tool_name": "run_command",
            "arguments": {"CommandLine": "ls"}
        }

        # Apply patch to DiscordApprovalView.wait
        with patch("bot.DiscordApprovalView.wait", mock_wait_approved):
            response = client.post("/approve", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["approved"])

    @patch("bot.bot")
    def test_approve_endpoint_success_approved_ide(self, mock_bot):
        """Test /approve endpoint returns approved status when approved via Language Server."""
        mock_bot.is_ready.return_value = True
        
        # Mock User and Message objects
        mock_user = MagicMock()
        mock_msg = MagicMock()
        
        # Mock msg.edit to be awaitable
        fut_edit = self.loop.create_future()
        fut_edit.set_result(None)
        mock_msg.edit = MagicMock(return_value=fut_edit)
        
        # Create future in loop context
        fut_send = self.loop.create_future()
        fut_send.set_result(mock_msg)
        mock_user.send = MagicMock(return_value=fut_send)
        
        # Create future for fetch_user
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)

        # Mock the LS polling to succeed with allow=True
        async def mock_poll_ls(ls_address, ls_token, convo_id, tool_name, arguments, fut):
            fut.set_result("approve_ide")

        payload = {
            "request_id": "test-req-id-3",
            "agent_name": "TestAgent",
            "conversation_id": "test-conv",
            "tool_name": "run_command",
            "arguments": {"CommandLine": "ls"},
            "ls_address": "127.0.0.1:65081",
            "ls_token": "mock-csrf-token"
        }

        with patch("bot.poll_ls_for_approval", mock_poll_ls):
            response = client.post("/approve", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["approved"])

    @patch("bot.bot")
    def test_approve_endpoint_success_denied(self, mock_bot):
        """Test /approve endpoint returns denied status when denied by user."""
        mock_bot.is_ready.return_value = True
        
        # Mock User and Message objects
        mock_user = MagicMock()
        mock_msg = MagicMock()
        
        # Mock msg.edit to be awaitable
        fut_edit = self.loop.create_future()
        fut_edit.set_result(None)
        mock_msg.edit = MagicMock(return_value=fut_edit)
        
        # Create futures in loop context
        fut_send = self.loop.create_future()
        fut_send.set_result(mock_msg)
        mock_user.send = MagicMock(return_value=fut_send)
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)

        async def mock_wait_denied(view_self):
            # Resolve approval future as False
            fut = bot.pending_approvals[view_self.request_id]
            fut.set_result(False)
            return None

        payload = {
            "request_id": "test-req-id-2",
            "agent_name": "TestAgent",
            "conversation_id": "test-conv",
            "tool_name": "run_command",
            "arguments": {"CommandLine": "rm -rf /"}
        }

        with patch("bot.DiscordApprovalView.wait", mock_wait_denied):
            response = client.post("/approve", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["approved"])

    @patch("bot.bot")
    def test_post_message_bot_not_ready(self, mock_bot):
        """Test /message returns 503 if bot is offline."""
        mock_bot.is_ready.return_value = False
        response = client.post("/message", json={"content": "hello"})
        self.assertEqual(response.status_code, 503)

    @patch("bot.bot")
    @patch("bot.DISCORD_USER_ID", None)
    def test_post_message_no_user_resolved(self, mock_bot):
        """Test /message returns 500 if no user ID is configured/resolved."""
        mock_bot.is_ready.return_value = True
        response = client.post("/message", json={"content": "hello"})
        self.assertEqual(response.status_code, 500)

    @patch("bot.bot")
    @patch("bot.DISCORD_USER_ID", "12345")
    def test_post_message_success(self, mock_bot):
        """Test /message successfully forwards messages via Discord DM."""
        mock_bot.is_ready.return_value = True
        
        mock_user = MagicMock()
        fut_send = self.loop.create_future()
        fut_send.set_result(MagicMock())
        mock_user.send = MagicMock(return_value=fut_send)
        
        fut_user = self.loop.create_future()
        fut_user.set_result(mock_user)
        mock_bot.fetch_user = MagicMock(return_value=fut_user)

        response = client.post("/message", json={"content": "hello", "embed_title": "Test Title"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})

    @patch("bot.bot")
    @patch("bot.DISCORD_USER_ID", "12345")
    def test_post_message_exception(self, mock_bot):
        """Test /message returns 500 on Discord sending errors."""
        mock_bot.is_ready.return_value = True
        mock_bot.fetch_user.side_effect = Exception("Discord API error")
        response = client.post("/message", json={"content": "hello"})
        self.assertEqual(response.status_code, 500)

    def test_pause_resume_endpoints(self):
        """Test pause, resume, toggle-pause endpoints and auto-approval when paused."""
        # Check initial state
        bot.IS_PAUSED = False
        
        # Test toggle-pause: False -> True
        resp = client.post("/api/toggle-pause")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["paused"])
        self.assertTrue(bot.IS_PAUSED)
        
        # Test auto-approval when paused
        payload = {
            "request_id": "test-req-pause-approve",
            "agent_name": "TestAgent",
            "conversation_id": "test-conv",
            "tool_name": "run_command",
            "arguments": {"CommandLine": "ls"}
        }
        resp = client.post("/approve", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["approved"])
        self.assertEqual(resp.json()["reason"], "Liaison is paused")
        
        # Test resume endpoint
        resp = client.post("/api/resume")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["paused"])
        self.assertFalse(bot.IS_PAUSED)
        
        # Test pause endpoint
        resp = client.post("/api/pause")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["paused"])
        self.assertTrue(bot.IS_PAUSED)
        
        # Reset state after test
        bot.IS_PAUSED = False

    @patch("web_server.update_settings_in_env")
    def test_post_settings_success(self, mock_update):
        """Test POST /api/settings successfully updates provider, auto-switch, and permissions state."""
        payload = {
            "model_provider": "ollama",
            "auto_switch_local": True,
            "discord_bot_permissions": "12345678"
        }
        resp = client.post("/api/settings", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["model_provider"], "ollama")
        self.assertEqual(resp.json()["auto_switch_local"], True)
        self.assertEqual(resp.json()["discord_bot_permissions"], "12345678")
        
        self.assertEqual(bot.MODEL_PROVIDER, "ollama")
        self.assertEqual(bot.AUTO_SWITCH_LOCAL, True)
        self.assertEqual(bot.DISCORD_BOT_PERMISSIONS, "12345678")
        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        self.assertEqual(args[0].model_provider, "ollama")

    @patch("web_server.update_settings_in_env")
    def test_post_settings_partial_success(self, mock_update):
        """
        Description:
            Verifies that a partial settings update (e.g. only updating model_provider)
            succeeds without Pydantic validation errors and does not clear other state fields.
        Usage:
            self.test_post_settings_partial_success(mock_update)
        Usage Example:
            self.test_post_settings_partial_success(mock_update)
        """
        # Set initial values
        bot.MODEL_PROVIDER = "ollama"
        bot.AUTO_SWITCH_LOCAL = True
        bot.DISCORD_BOT_PERMISSIONS = "12345678"
        
        payload = {
            "model_provider": "gemini"
        }
        resp = client.post("/api/settings", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["model_provider"], "gemini")
        self.assertEqual(resp.json()["auto_switch_local"], True)
        self.assertEqual(resp.json()["discord_bot_permissions"], "12345678")
        
        self.assertEqual(bot.MODEL_PROVIDER, "gemini")
        self.assertEqual(bot.AUTO_SWITCH_LOCAL, True)
        self.assertEqual(bot.DISCORD_BOT_PERMISSIONS, "12345678")

    @patch("web_server.update_settings_in_env")
    def test_post_settings_force_server_chat(self, mock_update):
        """
        Description:
            Verifies that POST /api/settings successfully updates force_server_chat
            and sets the dynamic state.FORCE_SERVER_CHAT.
        Usage:
            test_post_settings_force_server_chat(mock_update)
        Usage Example:
            test_post_settings_force_server_chat(mock_update)
        """
        payload = {
            "model_provider": "gemini",
            "auto_switch_local": False,
            "discord_bot_permissions": "8471182706732241",
            "force_server_chat": 1
        }
        resp = client.post("/api/settings", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["force_server_chat"], 1)
        self.assertEqual(bot.state.FORCE_SERVER_CHAT, True)

    @patch("web_server.update_settings_in_env")
    def test_post_settings_force_only_server(self, mock_update):
        """
        Description:
            Verifies that POST /api/settings successfully updates force_only_server
            and sets the dynamic state.FORCE_SERVER_CHAT.
        Usage:
            test_post_settings_force_only_server(mock_update)
        Usage Example:
            test_post_settings_force_only_server(mock_update)
        """
        payload = {
            "model_provider": "gemini",
            "auto_switch_local": False,
            "discord_bot_permissions": "8471182706732241",
            "force_only_server": 1
        }
        resp = client.post("/api/settings", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["force_only_server"], 1)
        self.assertEqual(bot.state.FORCE_SERVER_CHAT, True)


    def test_port_collision_mode(self):
        """Test that _is_port_in_use correctly detects occupied and free ports."""
        import socket
        # Find a free ephemeral port by binding to port 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(("127.0.0.1", 0))
            server_sock.listen(1)
            occupied_port = server_sock.getsockname()[1]

            # Port is actively occupied — should return True
            self.assertTrue(bot._is_port_in_use(occupied_port),
                            f"Expected port {occupied_port} to be detected as in-use")

        # After closing the server socket the port is free — should return False
        self.assertFalse(bot._is_port_in_use(occupied_port),
                         f"Expected port {occupied_port} to be detected as free after release")


if __name__ == '__main__':
    unittest.main()
