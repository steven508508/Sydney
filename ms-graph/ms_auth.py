#!/usr/bin/env python3
"""
Microsoft Graph OAuth helper — Device Code Flow version.
Handles auth URL generation and token exchange.
"""
import http.server
import json
import os
import socket
import sys
import threading
import urllib.parse
import webbrowser

CONFIG_PATH = "/root/.openclaw/workspace/ms-graph/config.json"

TENANT_ID = "YOUR_TENANT_ID"
CLIENT_ID = "YOUR_CLIENT_ID"
USER_EMAIL = "xg@lzl.edu.kg"

SCOPES = [
    "offline_access",
    "openid",
    "profile",
    "Mail.Send",
    "Mail.ReadWrite",
    "Files.ReadWrite",
    "ChannelMessage.Read.All",
    "ChannelMessage.Send",
    "Channel.ReadBasic.All",
    "Tasks.ReadWrite",
]

def save_config(auth_result: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(auth_result, f, indent=2)
    print(f"Config saved to {CONFIG_PATH}")

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

def device_code_flow() -> dict:
    """Initiate device code flow, return device code info."""
    import urllib.request

    data = {
        "client_id": CLIENT_ID,
        "scope": " ".join(SCOPES),
    }

    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode",
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def poll_for_token(device_code_response: dict) -> dict:
    """Poll until user completes auth in browser."""
    import urllib.request
    import time

    interval = device_code_response.get("interval", 5)
    device_code = device_code_response["device_code"]
    user_code = device_code_response.get("user_code", "")
    message = device_code_response.get("message", "")

    # Print the instructions
    lines = message.split("\n")
    for line in lines:
        if line.strip():
            print(line)

    if user_code:
        print(f"\n🔑 YOUR CODE: {user_code}\n")

    while True:
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": CLIENT_ID,
            "device_code": device_code,
            "scope": " ".join(SCOPES),
        }

        req = urllib.request.Request(
            f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
            data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                if "access_token" in result:
                    return result
                if result.get("error") == "authorization_pending":
                    time.sleep(interval)
                else:
                    print(f"Polling error: {result}")
                    return result
        except Exception as e:
            print(f"Connection error: {e}, retrying in {interval}s...")
            time.sleep(interval)

def refresh_access_token(refresh_token: str) -> dict:
    import urllib.request

    data = {
        "client_id": CLIENT_ID,
        "client_secret": "YOUR_CLIENT_SECRET",
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(SCOPES),
    }

    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def main(action: str):
    if action == "auth":
        print("🔄 Starting Microsoft Graph Device Code Flow...\n")
        dc = device_code_flow()
        result = poll_for_token(dc)
        if "access_token" not in result:
            print(f"❌ Auth failed: {result}")
            sys.exit(1)
        result["email"] = USER_EMAIL
        save_config(result)
        print(f"\n✅ Microsoft Graph authorization complete!")
        print(f"   Access token expires in: {result.get('expires_in', '?')} seconds")
        print(f"   Refresh token: {'✅ received' if 'refresh_token' in result else '❌ NOT received'}")
        if "refresh_token" not in result:
            print("⚠️  Warning: No refresh token received.")
        return

    elif action == "refresh":
        config = load_config()
        if "refresh_token" not in config:
            print("No refresh token found. Run 'auth' first.")
            sys.exit(1)
        print("🔄 Refreshing access token...")
        tokens = refresh_access_token(config["refresh_token"])
        tokens["email"] = USER_EMAIL
        save_config(tokens)
        print(f"✅ Refreshed! New token expires in {tokens.get('expires_in', '?')} seconds.")
        return

    else:
        print("Usage: python3 ms_auth.py [auth|refresh]")
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "help")
