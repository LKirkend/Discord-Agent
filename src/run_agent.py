import os
import asyncio
from dotenv import load_dotenv
from google.antigravity import Agent, LocalAgentConfig
from discord_policy import get_discord_policies, get_discord_hooks

# Load environment variables (contains GEMINI_API_KEY, etc.)
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, "..", ".env"))

async def main():
    print("[Persistent Agent] Initializing safety policies and hooks...")
    policies = get_discord_policies()
    hooks_list = get_discord_hooks()
    
    # Configure the agent
    config = LocalAgentConfig(
        system_instructions=(
            "You are AGY2 Liaison Agent, a powerful pair-programming and command execution assistant. "
            "You communicate directly with the user via Discord. You are running as a persistent background process on the user's host. "
            "Help the user execute commands, edit files, and monitor processes. "
            "Since you are running persistently in the background, you can respond to Discord DM prompts immediately. "
            "Always explain your actions and verify success. Use clean and structured layouts."
        ),
        policies=policies,
        hooks=hooks_list,
        app_data_dir=os.path.expanduser("~/.gemini/antigravity-ide"),
    )
    
    print("[Persistent Agent] Starting agent session...")
    try:
        async with Agent(config) as agent:
            print("[Persistent Agent] Agent is active and running persistently in the background.")
            print("[Persistent Agent] Watching for incoming messages and tasks. Press Ctrl+C to exit.")
            
            # Keep the event loop running to process triggers/messages in the background
            while True:
                await asyncio.sleep(3600)  # Sleep 1 hour at a time
                
    except asyncio.CancelledError:
        print("[Persistent Agent] Received cancellation. Shutting down...")
    except Exception as e:
        print(f"[Persistent Agent] Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[Persistent Agent] Stopped by user.")
