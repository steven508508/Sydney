#!/usr/bin/env python3
"""
Microsoft Graph API wrapper — Multi-account version.
Each account stored separately in accounts/ directory.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE_DIR = "/root/.openclaw/workspace/ms-graph"
ACCOUNTS_DIR = f"{BASE_DIR}/accounts"
CONFIG_FILE = f"{BASE_DIR}/config.json"

TENANT_ID = "YOUR_TENANT_ID"
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
SCOPES = [
    "offline_access", "openid", "profile",
    "Mail.Send", "Mail.ReadWrite",
    "Files.ReadWrite",
    "ChannelMessage.Read.All",
    "Tasks.ReadWrite",
    "Calendars.ReadWrite", "Calendars.Read",

]

os.makedirs(ACCOUNTS_DIR, exist_ok=True)

# ─── Account Manager ──────────────────────────────────────────────────────────

def load_account_config(account_id):
    path = f"{ACCOUNTS_DIR}/{account_id}.json"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def save_account_config(account_id, data):
    path = f"{ACCOUNTS_DIR}/{account_id}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def get_active_account():
    if not os.path.exists(CONFIG_FILE):
        return None
    cfg = json.load(open(CONFIG_FILE))
    return cfg.get("active_account")

def set_active_account(account_id):
    cfg = {"active_account": account_id}
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)
    return account_id

def list_accounts():
    accounts = []
    for fname in os.listdir(ACCOUNTS_DIR):
        if fname.endswith(".json"):
            data = json.load(open(f"{ACCOUNTS_DIR}/{fname}"))
            accounts.append(data)
    return accounts

def add_account(account_id, data):
    save_account_config(account_id, data)

def remove_account(account_id):
    path = f"{ACCOUNTS_DIR}/{account_id}.json"
    if os.path.exists(path):
        os.remove(path)
    if get_active_account() == account_id:
        accounts = list_accounts()
        if accounts:
            set_active_account(accounts[0]["id"])
        else:
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)

def make_account_id(email):
    return email.lower().replace("@", "_").replace(".", "_")

# ─── Token Manager ───────────────────────────────────────────────────────────

def refresh_if_needed(account_data):
    if account_data.get("expires_at", 0) > time.time() + 300:
        return account_data

    if "refresh_token" not in account_data:
        print("No refresh token. Use 'token_manager.py auth' to re-authorize.")
        return account_data

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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        account_data["access_token"] = result["access_token"]
        account_data["expires_at"] = time.time() + result.get("expires_in", 3600)
        if "refresh_token" in result:
            account_data["refresh_token"] = result["refresh_token"]
            account_data["refresh_token_updated"] = time.time()
        save_account_config(account_data["id"], account_data)
        return account_data
    except Exception as e:
        print(f"Token refresh failed: {e}")
        return account_data

def get_token(account_data):
    refreshed = refresh_if_needed(account_data)
    return refreshed["access_token"]

# ─── Graph Request ────────────────────────────────────────────────────────────

def graph_request(method, endpoint, data=None, params=None, account_data=None):
    if account_data is None:
        active = get_active_account()
        account_data = load_account_config(active)

    token = get_token(account_data)
    url = f"https://graph.microsoft.com/v1.0{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, headers=headers, method=method)
    if data:
        req.data = json.dumps(data).encode()

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            if not body:
                return {}, resp.status
            return json.loads(body), resp.status
    except urllib.request.HTTPError as e:
        error_body = e.read()
        if not error_body:
            return {"error": "empty error body"}, e.code
        try:
            return {"error": json.loads(error_body)}, e.code
        except:
            return {"error": error_body.decode()}, e.code

# ─── Account Commands ──────────────────────────────────────────────────────────

def cmd_list():
    accounts = list_accounts()
    active = get_active_account()
    if not accounts:
        print("No accounts. Run 'auth' to add one.")
        return
    print(f"\n{'='*50}")
    print(f" Total accounts: {len(accounts)} / 5")
    print(f"{'='*50}")
    for i, acct in enumerate(accounts, 1):
        marker = " ← currently active" if acct["id"] == active else ""
        print(f" [{i}] {acct.get('nickname', acct['id'])}")
        print(f"      Email: {acct['email']}{marker}")
        if "expires_at" in acct:
            remaining = max(0, acct["expires_at"] - time.time())
            mins = int(remaining // 60)
            print(f"      Token: {mins}m remaining")
        print()
    print("Use 'switch <id>' or 'switch <number>' to change active account.")
    print("Use 'remove <id>' to delete an account.")
    print("Use 'add' to add a new account.")

def cmd_switch(target):
    accounts = list_accounts()
    if not accounts:
        print("No accounts found.")
        return

    # Try by number
    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(accounts):
            account_id = accounts[idx]["id"]
            set_active_account(account_id)
            print(f"Switched to: {accounts[idx].get('nickname', accounts[idx]['id'])}")
            return
        print(f"Invalid number: {target}")
        return

    # Try by account_id
    for acct in accounts:
        if acct["id"] == target or acct["email"] == target:
            set_active_account(acct["id"])
            print(f"Switched to: {acct.get('nickname', acct['id'])}")
            return

    print(f"Account not found: {target}")

def cmd_remove(target):
    accounts = list_accounts()
    if not accounts:
        print("No accounts to remove.")
        return

    # Find account
    account = None
    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(accounts):
            account = accounts[idx]
    else:
        for acct in accounts:
            if acct["id"] == target or acct["email"] == target:
                account = acct
                break

    if not account:
        print(f"Account not found: {target}")
        return

    confirm = input(f"Remove {account['email']} ({account.get('nickname', account['id'])})? [y/N]: ")
    if confirm.lower() == "y":
        remove_account(account["id"])
        print("Removed.")
    else:
        print("Cancelled.")

def cmd_add(email=None, nickname=None):
    accounts = list_accounts()
    if len(accounts) >= 5:
        print("Maximum 5 accounts. Remove one first.")
        return

    if not email:
        email = input("Email address: ").strip()
    if not nickname:
        nickname = input("Nickname (optional, Enter to skip): ").strip()
        if not nickname:
            nickname = email.split("@")[0]

    account_id = make_account_id(email)
    if load_account_config(account_id):
        print(f"Account {email} already exists. Use 'switch {account_id}' to activate.")
        return

    print(f"\nStarting OAuth for {email}...")
    print(f"Open this URL in your browser:")
    print(f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize?"
          f"client_id={CLIENT_ID}&response_type=code&redirect_uri=http%3A%2F%2Flocalhost%3A18901%2Fcallback"
          f"&scope={'+'.join(SCOPES)}&response_mode=query\n")

    code = input("Paste the 'code' from the callback URL: ").strip()

    # Exchange code for tokens
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": "http://localhost:18901/callback",
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
    except Exception as e:
        print(f"Token exchange failed: {e}")
        return

    account_data = {
        "id": account_id,
        "email": email,
        "nickname": nickname,
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "expires_at": time.time() + result.get("expires_in", 3600),
        "added_at": "2026-03-21"
    }
    add_account(account_id, account_data)
    set_active_account(account_id)
    print(f"\n✅ Account added and activated: {nickname} ({email})")

def cmd_rename(account_id, new_nickname):
    data = load_account_config(account_id)
    if not data:
        print(f"Account not found: {account_id}")
        return
    data["nickname"] = new_nickname
    save_account_config(account_id, data)
    print(f"Renamed to: {new_nickname}")

# ─── Service Commands ──────────────────────────────────────────────────────────

def cmd_send_email(to_address, subject, body):
    account = get_active_account()
    account_data = load_account_config(account)
    email_data = {
        "message": {
            "subject": subject,
            "body": {"contentType": "text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to_address}}]
        },
        "saveToSentItems": True
    }
    result, status = graph_request("POST", "/me/sendMail", data=email_data, account_data=account_data)
    if status in (200, 201, 202):
        print("Email sent successfully.")
    else:
        print(f"Failed: {result}")

def cmd_read_emails(folder="Inbox", top=10):
    account = get_active_account()
    account_data = load_account_config(account)
    result, status = graph_request(
        "GET", f"/me/mailFolders/{folder}/messages",
        params={"$top": top, "$select": "subject,from,receivedDateTime,bodyPreview,isRead"},
        account_data=account_data
    )
    if "error" in result:
        print(f"Error: {result}")
        return
    print(f"\n{'='*60}")
    active = get_active_account()
    acct = load_account_config(active)
    print(f"Account: {acct.get('nickname', active)} ({acct['email']})")
    print(f"Folder: {folder}\n")
    for msg in result.get("value", []):
        read = "已讀" if msg.get("isRead") else "未讀"
        sender = msg.get("from", {}).get("emailAddress", {}).get("name", "N/A")
        print(f"[{read}] {msg['receivedDateTime'][:10]} | {sender}")
        print(f"  {msg.get('subject', '(無主旨)')}")
        print(f"  {msg.get('bodyPreview', '')[:60]}")
        print()

def cmd_list_files(path="/"):
    account = get_active_account()
    account_data = load_account_config(account)
    endpoint = "/me/drive/root/children" if path == "/" else f"/me/drive/root:/{path.lstrip('/')}:/children"
    result, status = graph_request("GET", endpoint, account_data=account_data)
    if "error" in result:
        print(f"Error: {result}")
        return
    for item in result.get("value", []):
        icon = "📁" if "folder" in item else "📄"
        print(f"{icon} {item['name']}")

def cmd_list_tasks():
    account = get_active_account()
    account_data = load_account_config(account)
    result, status = graph_request("GET", "/me/todo/lists", account_data=account_data)
    if "error" in result:
        print(f"Error: {result}")
        return
    for lst in result.get("value", []):
        print(f"📋 {lst.get('displayName', lst.get('id'))}")

def cmd_list_events(start=None, end=None, days=7):
    """List calendar events. Default: next 7 days."""
    account = get_active_account()
    account_data = load_account_config(account)
    if not start:
        from datetime import datetime, timedelta
        start = datetime.utcnow().isoformat() + "Z"
        end_dt = datetime.utcnow() + timedelta(days=days)
        end = end_dt.isoformat() + "Z"
    params = {"startDateTime": start, "endDateTime": end, "$select": "subject,start,end,location", "$orderby": "start/dateTime"}
    result, status = graph_request("GET", "/me/calendarView", params=params, account_data=account_data)
    if "error" in result:
        print(f"Error: {result}")
        return
    events = result.get("value", [])
    if not events:
        print("No events found.")
        return
    for ev in events:
        s = ev.get("start", {}).get("dateTime", "")[:16]
        loc = ev.get("location", {}).get("displayName", "")
        print(f"📅 {s} | {ev.get('subject', '(No title)')}" + (f" @ {loc}" if loc else ""))
    print(f"\nTotal: {len(events)} event(s)")

def cmd_create_event(subject, start_iso, end_iso, location=None, body=None):
    """Create a calendar event. start_iso and end_iso in ISO format."""
    account = get_active_account()
    account_data = load_account_config(account)
    data = {
        "subject": subject,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Taipei"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Taipei"},
    }
    if location:
        data["location"] = {"displayName": location}
    if body:
        data["body"] = {"contentType": "text", "content": body}
    result, status = graph_request("POST", "/me/events", data=data, account_data=account_data)
    if status in (200, 201, 202):
        print(f"✅ Event created: {subject}")
    else:
        print(f"Failed: {result}")

def cmd_refresh():
    account = get_active_account()
    account_data = load_account_config(account)
    if not account_data:
        print("No active account.")
        return
    refreshed = refresh_if_needed(account_data)
    if refreshed:
        print(f"Token refreshed for {refreshed['email']}.")

# ─── Main CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Microsoft Graph API - Multi Account")
    parser.add_argument("command", nargs="?", help="Command: list, switch, add, remove, rename, refresh, send-email, read-emails, list-files, list-tasks, list-events, create-event")
    parser.add_argument("arg1", nargs="?", help="Argument 1")
    parser.add_argument("arg2", nargs="?", help="Argument 2")
    parser.add_argument("arg3", nargs="?", help="Argument 3")
    args = parser.parse_args(sys.argv[1:] if len(sys.argv) > 1 else ["help"])

    cmd = args.command

    if cmd == "list":
        cmd_list()

    elif cmd == "switch":
        if not args.arg1:
            print("Usage: graph_api.py switch <account_id|email|number>")
        else:
            cmd_switch(args.arg1)

    elif cmd == "remove":
        if not args.arg1:
            print("Usage: graph_api.py remove <account_id|email|number>")
        else:
            cmd_remove(args.arg1)

    elif cmd == "add":
        cmd_add(args.arg1, args.arg2)

    elif cmd == "rename":
        if len(sys.argv) < 4:
            print("Usage: graph_api.py rename <account_id> <new_nickname>")
        else:
            cmd_rename(args.arg1, args.arg2)

    elif cmd == "refresh":
        cmd_refresh()

    elif cmd == "send-email":
        if not args.arg1 or not args.arg2 or not args.arg3:
            print("Usage: graph_api.py send-email <to> <subject> <body>")
        else:
            cmd_send_email(args.arg1, args.arg2, args.arg3)

    elif cmd == "read-emails":
        cmd_read_emails(args.arg1 or "Inbox", int(args.arg2) if args.arg2 else 10)

    elif cmd == "list-files":
        cmd_list_files(args.arg1 or "/")

    elif cmd == "list-tasks":
        cmd_list_tasks()

    elif cmd == "list-events":
        cmd_list_events(args.arg1, args.arg2)

    elif cmd == "create-event":
        # Usage: create-event <subject> <start_iso> <end_iso> [location] [body]
        if not args.arg1 or not args.arg2 or not args.arg3:
            print("Usage: create-event <subject> <start_iso> <end_iso> [location] [body]")
            print("Example: create-event '段考' 2026-03-25T09:00:00 2026-03-25T12:00:00 '教室'")
        else:
            cmd_create_event(args.arg1, args.arg2, args.arg3, args.arg4, args.arg5)

    elif cmd == "help":
        print("Commands:")
        print("  list              - List all accounts")
        print("  switch <target>   - Switch active account (by id, email, or number)")
        print("  add [email] [nickname] - Add new account")
        print("  remove <target>  - Remove account")
        print("  rename <id> <nickname> - Rename account")
        print("  refresh           - Refresh token for active account")
        print("  send-email <to> <subj> <body> - Send email")
        print("  read-emails [folder] [top] - Read emails")
        print("  list-files [path] - List OneDrive files")
        print("  list-tasks        - List Todo lists")
        print("  list-events [days]- List calendar events")
        print("  create-event <subj> <start> <end> [loc] [body] - Create event")
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'graph_api.py help' for usage.")

if __name__ == "__main__":
    main()
