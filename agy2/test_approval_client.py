import asyncio
import os
from discord_policy import discord_approval_handler

# Set debug environment variables
os.environ["ANTIGRAVITY_AGENT_NAME"] = "MockOpenFeedbackRemoverAgent"
os.environ["ANTIGRAVITY_CONVERSATION_ID"] = "mock-conv-98765"

# Mock class representing a ToolCall object
class MockToolCall:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

async def main():
    print("[Test Client] Starting Discord approval workflow test...")
    
    # 1. Create a mock tool call requesting run_command
    mock_tool = MockToolCall(
        name="run_command",
        arguments={
            "CommandLine": "python scripts/train_feedback_model.py --epochs 60 --batch 256 --lr 5e-4"
        }
    )
    
    print(f"[Test Client] Sending mock approval request for '{mock_tool.name}'...")
    print("[Test Client] CommandLine:", mock_tool.arguments["CommandLine"])
    print("[Test Client] Awaiting user response via Discord bot server...")
    
    # 2. Call the approval handler which performs the POST and blocks
    approved = await discord_approval_handler(mock_tool)
    
    print("\n[Test Client] --- TEST COMPLETED ---")
    if approved:
        print("[Test Client] Result: ✅ APPROVED! Running command...")
    else:
        print("[Test Client] Result: ❌ DENIED! Command blocked.")

if __name__ == "__main__":
    asyncio.run(main())
