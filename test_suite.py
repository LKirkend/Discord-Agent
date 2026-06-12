"""
File: test_suite.py
Description:
    Master test suite runner for the Discord Liaison Bot.
    Imports all modular test suites (Web, Bot, and Policy) and runs them.
Author: Logan Kirkendall <Logan@LKAud.io>
"""

import unittest

# Import the individual TestCase classes so they are discovered by unittest.main()
from test_suite_web import TestDiscordApprovalServerWeb
from test_suite_bot import TestDiscordApprovalServerBot
from test_suite_policy import TestDiscordApprovalServerPolicy

if __name__ == '__main__':
    unittest.main()
