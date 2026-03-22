#!/usr/bin/env python3
"""
Count tokens in the main Telegram session.
Usage: python3 count_tokens.py <session_key>
"""
import sys
import json
import urllib.request
import urllib.error

try:
    import tiktoken
except ImportError:
    print("ERROR:tiktoken not installed")
    sys.exit(1)

GATEWAY_PORT = 18789
MAIN_SESSION = "agent:main:telegram:direct:7310527312"
TOKEN_LIMIT = 180000

def gateway_api(path, method="GET", data=None):
    """Make API call to local gateway."""
    url = f"http://localhost:{GATEWAY_PORT}{path}"
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, headers=headers, method=method)
    if data:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": str(e)}

def count_tokens(text):
    """Count tokens using cl100k_base encoding."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    return len(tokens)

def main():
    session_key = sys.argv[1] if len(sys.argv) > 1 else MAIN_SESSION

    # Fetch session history via gateway API
    # ACP protocol endpoint for session history
    result = gateway_api(f"/api/sessions/{session_key}/history")

    if "error" in result:
        print(f"ERROR:Could not fetch session: {result['error']}")
        sys.exit(0)  # Quiet exit

    messages = result.get("messages", [])
    if not messages:
        print("INFO:No messages found or empty session")
        sys.exit(0)

    total_tokens = 0
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    total_tokens += count_tokens(item.get("text", ""))
        elif isinstance(content, str):
            total_tokens += count_tokens(content)

    pct = (total_tokens / TOKEN_LIMIT) * 100
    print(f"TOKENS:{total_tokens}/{TOKEN_LIMIT} ({pct:.1f}%)")

    if total_tokens >= TOKEN_LIMIT:
        print("OVER_THRESHOLD")
        sys.exit(1)
    else:
        print("OK")
        sys.exit(0)

if __name__ == "__main__":
    main()
