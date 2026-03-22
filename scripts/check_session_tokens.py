#!/usr/bin/env python3
"""
Check token usage for main Telegram session and remind if over threshold.
"""
import json
import os
import sys
from datetime import datetime

SESSION_KEY = "agent:main:telegram:direct:7310527312"
THRESHOLD = 180000  # tokens
SESSIONS_FILE = "/root/.openclaw/agents/main/sessions/sessions.json"

def main():
    if not os.path.exists(SESSIONS_FILE):
        print("Sessions file not found, skipping")
        sys.exit(0)

    sessions = json.load(open(SESSIONS_FILE))
    if SESSION_KEY not in sessions:
        print("Main session not found, skipping")
        sys.exit(0)

    data = sessions[SESSION_KEY]
    total_tokens = data.get("totalTokens", 0)
    context_tokens = data.get("contextTokens", 0)
    updated_at = data.get("updatedAt", "unknown")

    # Use totalTokens as the primary measure (contextTokens is actually the window limit)
    usage = total_tokens
    pct = (usage / THRESHOLD) * 100 if usage > 0 else 0

    print(f"TOKENS:{usage}/{THRESHOLD} ({pct:.1f}%)")

    if usage >= THRESHOLD:
        print("OVER_THRESHOLD")
        # Output reminder message
        print("REMINDER:⚠️ 對話即將達到上限，請確認是否需要保存重要資訊到 MEMORY.md")
        sys.exit(1)
    else:
        print(f"OK — {pct:.1f}% used, no action needed")
        sys.exit(0)

if __name__ == "__main__":
    main()
