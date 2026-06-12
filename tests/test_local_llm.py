import urllib.request
import json
import sys

def test_chat_completion(model_name: str = "qwen2.5-coder:7b") -> None:
    """
    Description:
        Tests local LLM chat completions using the OpenAI-compatible Ollama API.
        Sends a simple programming question and prints the streamed or full response.
    Usage:
        test_chat_completion(model_name)
    Usage Example:
        test_chat_completion("qwen2.5-coder:7b")
    """
    url = "http://localhost:11434/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Write a quick Python function that returns the Fibonacci sequence up to N."}
        ],
        "temperature": 0.2
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
    print(f"Sending prompt to local model '{model_name}'...")
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            content = res_data["choices"][0]["message"]["content"]
            print("\n--- Model Response ---")
            print(content)
            print("----------------------\n")
            print("✅ Local LLM integration verified successfully!")
    except Exception as e:
        print(f"❌ Error communicating with local model: {e}", file=sys.stderr)

if __name__ == "__main__":
    test_chat_completion()
