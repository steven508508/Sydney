#!/usr/bin/env python3
"""
Microsoft Graph token manager with automatic refresh.
Monitors token expiry and refreshes automatically.
Refreshes when tokens are within 2 hours of expiry.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import subprocess
import threading

BASE_DIR = "/root/.openclaw/workspace/ms-graph"
TENANT_ID = "YOUR_TENANT_ID"
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
SCOPES = [
    "offline_access", "openid", "profile",
    "Mail.Send", "Mail.ReadWrite",
    "Files.ReadWrite",
    "Tasks.ReadWrite",
    "Calendars.ReadWrite", "Calendars.Read",
]

REFRESH_BUFFER = 7200  # Refresh if < 2 hours until expiry
MAX_ACCOUNT_AGE_DAYS = 90  # Force re-auth if refresh token > 90 days

def get_accounts():
    accounts = {}
    accounts_dir = f"{BASE_DIR}/accounts"
    if not os.path.exists(accounts_dir):
        return accounts
    for fname in os.listdir(accounts_dir):
        if fname.endswith(".json"):
            path = os.path.join(accounts_dir, fname)
            data = json.load(open(path))
            accounts[data["id"]] = data
    return accounts

def save_account(data):
    with open(f"{BASE_DIR}/accounts/{data['id']}.json", "w") as f:
        json.dump(data, f, indent=2)

def refresh_token(account_data):
    """Refresh access token using refresh_token."""
    if "refresh_token" not in account_data:
        return None

    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": account_data["refresh_token"],
        "scope": " ".join(SCOPES),
    }
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    account_data["access_token"] = result["access_token"]
    account_data["expires_at"] = time.time() + result.get("expires_in", 3600)
    if "refresh_token" in result:
        account_data["refresh_token"] = result["refresh_token"]
        account_data["refresh_token_updated"] = time.time()
    return account_data

def start_device_code_flow():
    """Start Device Code Flow to get new tokens interactively."""
    # Step 1: Get device code
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
    with urllib.request.urlopen(req, timeout=15) as resp:
        dc = json.loads(resp.read())

    print(f"\n🔗 Open: https://login.microsoft.com/device")
    print(f"🔑 Code: {dc.get('user_code', 'N/A')}")
    print(f"⏰ Expires in {dc.get('expires_in', 900)//60} minutes")
    print()
    print("After logging in, run this script with 'poll' to complete.")
    print(f"\nDEVICE_CODE={dc.get('device_code', '')}")
    return dc.get("device_code"), dc.get("interval", 5), dc.get("expires_in", 900)

def poll_device_code(device_code):
    """Poll for device code completion."""
    if not device_code:
        print("No device code. Run 'auth' first.")
        return None

    interval = 5
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": CLIENT_ID,
        "device_code": device_code,
        "scope": " ".join(SCOPES),
    }

    print(f"Polling every {interval}s... (Ctrl+C to cancel)")
    start_time = time.time()
    expires_in = 900  # 15 min default

    while time.time() - start_time < expires_in:
        req = urllib.request.Request(
            f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
            data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                if "access_token" in result:
                    return result
        except urllib.request.HTTPError as e:
            err = json.loads(e.read().decode())
            if err.get("error") == "authorization_pending":
                time.sleep(interval)
            else:
                print(f"Error: {err}")
                return None
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(interval)

    print("Device code expired.")
    return None

def cmd_auth():
    """Start Device Code Flow for a new account."""
    account_id = input("Account ID (e.g. xg_lzl_edu_kg): ").strip()
    if not account_id:
        account_id = input("Email address: ").strip()
        if not account_id:
            print("Cancelled.")
            return
        from urllib.parse import quote
        account_id = quote(account_id, safe='')

    accounts = get_accounts()
    if account_id in accounts:
        email = accounts[account_id].get("email", account_id)
        print(f"Account '{email}' already exists. Use 'refresh' or 'switch {account_id}'.")
        return

    email = input("Email address: ").strip()
    nickname = input("Nickname (Enter to skip): ").strip()
    if not nickname:
        nickname = email.split("@")[0]

    print("\nStarting Device Code Flow...")
    device_code, interval, expires_in = start_device_code_flow()
    input(f"\nPress Enter after you complete login at https://microsoft.com/devicelogin ...")

    print("Polling for token...")
    result = poll_device_code(device_code)
    if not result:
        print("Auth failed or timed out.")
        return

    account_data = {
        "id": account_id,
        "email": email,
        "nickname": nickname,
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "expires_at": time.time() + result.get("expires_in", 3600),
        "refresh_token_updated": time.time(),
        "added_at": time.strftime("%Y-%m-%d"),
        "auth_method": "device_code",
    }
    save_account(account_data)

    # Set as active
    with open(f"{BASE_DIR}/config.json", "w") as f:
        json.dump({"active_account": account_id}, f)

    print(f"\n✅ Account '{nickname}' ({email}) saved and activated!")
    print(f"   Access token expires in {result.get('expires_in', 3600)//60} minutes")
    print(f"   Refresh token: {'✅ received' if 'refresh_token' in result else '❌ NOT received'}")

def cmd_refresh():
    """Refresh tokens for all accounts that are about to expire."""
    accounts = get_accounts()
    if not accounts:
        print("No accounts found.")
        return

    refreshed_count = 0
    for account_id, data in accounts.items():
        expires_at = data.get("expires_at", 0)
        remaining = expires_at - time.time()

        if remaining < REFRESH_BUFFER:
            print(f"Refreshing {data.get('nickname', account_id)} ({data.get('email')})...")
            try:
                refreshed = refresh_token(data)
                if refreshed:
                    save_account(refreshed)
                    print(f"  ✅ OK (expires in {refreshed.get('expires_at', 0) - time.time():.0f}s)")
                    refreshed_count += 1
                else:
                    print(f"  ⚠️  Failed (token may be expired, needs re-auth)")
            except Exception as e:
                print(f"  ⚠️  Error: {e}")
        else:
            print(f"Skipping {data.get('nickname', account_id)}: {remaining:.0f}s until expiry")

    if refreshed_count:
        print(f"\n✅ Refreshed {refreshed_count} account(s).")
    else:
        print("\nNo accounts needed refresh.")

def cmd_check():
    """Check token status for all accounts."""
    accounts = get_accounts()
    if not accounts:
        print("No accounts.")
        return

    print(f"\n{'='*60}")
    print(f" Account Status (as of {time.strftime('%Y-%m-%d %H:%M:%S')})")
    print(f"{'='*60}")
    active = open(f"{BASE_DIR}/config.json").read() if os.path.exists(f"{BASE_DIR}/config.json") else {}
    active_id = json.loads(active).get("active_account", "") if active else ""

    for account_id, data in accounts.items():
        marker = " ← active" if account_id == active_id else ""
        expires_at = data.get("expires_at", 0)
        remaining = expires_at - time.time()
        refresh_token_age = (time.time() - data.get("refresh_token_updated", 0)) / 86400

        status = "✅ OK" if remaining > REFRESH_BUFFER else "⚠️  expiring soon"
        if remaining <= 0:
            status = "❌ expired"
        if refresh_token_age > MAX_ACCOUNT_AGE_DAYS:
            status += f" (refresh token {refresh_token_age:.0f}d old)"

        print(f"\n[{account_id}]{marker}")
        print(f"  Email:    {data.get('email')}")
        print(f"  Nickname:  {data.get('nickname', 'N/A')}")
        print(f"  Status:    {status}")
        print(f"  Expires:   {remaining:.0f}s ({remaining/3600:.1f}h)")
        if 'auth_method' in data:
            print(f"  Auth:      {data['auth_method']}")

    print()

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "auth":
        cmd_auth()
    elif cmd == "refresh":
        cmd_refresh()
    elif cmd == "check":
        cmd_check()
    elif cmd == "poll":
        # Poll with stored device code
        import os
        dc = os.environ.get("DEVICE_CODE", "")
        if not dc:
            print("No DEVICE_CODE set. Run 'auth' first.")
            return
        result = poll_device_code(dc)
        if result:
            print("✅ Auth complete!")
    elif cmd == "help":
        print("Usage:")
        print("  token_manager.py auth     - Add new account (Device Code Flow)")
        print("  token_manager.py refresh   - Refresh expiring tokens")
        print("  token_manager.py check    - Check all account statuses")
        print("  token_manager.py poll     - Poll for pending device code (use with DEVICE_CODE env)")
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'token_manager.py help' for usage.")

if __name__ == "__main__":
    main()
