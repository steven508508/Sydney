#!/usr/bin/env python3
"""
智慧學習提醒系統 — 報告與作業截止追蹤
每天定時檢查 Notion 資料庫，三天內截止的項目主動提醒
"""
import subprocess
import json
from datetime import datetime, timedelta
from pathlib import Path

# ====== 設定 ======
NOTION_KEY_PATH = Path.home() / ".config/notion/api_key"
NOTION_DB_ID = "6d7f69ad-0070-4e79-88ef-942714fa77d2"
NOTION_API = "https://api.notion.com/v1"
STATE_FILE = Path.home() / ".openclaw/workspace/memory/reminder-state.json"

# 提醒時段（台北時間）
REMINDER_HOURS = [9, 19]  # 早上9點、晚上7點
REMIND_WITHIN_DAYS = 3

def get_notion_key():
    return Path(NOTION_KEY_PATH).read_text().strip()

def notion_headers():
    return {
        "Authorization": f"Bearer {get_notion_key()}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

def http_get(endpoint):
    result = subprocess.run(
        ["curl", "-s", "-X", "GET", f"{NOTION_API}{endpoint}",
         "-H", f"Authorization: Bearer {get_notion_key()}",
         "-H", "Notion-Version: 2022-06-28"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

def http_patch(page_id, data):
    result = subprocess.run(
        ["curl", "-s", "-X", "PATCH",
         f"{NOTION_API}/pages/{page_id}",
         "-H", f"Authorization: Bearer {get_notion_key()}",
         "-H", "Notion-Version: 2022-06-28",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(data)],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

def query_all_items():
    """查詢所有未刪除的項目"""
    result = subprocess.run(
        ["curl", "-s", "-X", "POST",
         f"{NOTION_API}/databases/{NOTION_DB_ID}/query",
         "-H", f"Authorization: Bearer {get_notion_key()}",
         "-H", "Notion-Version: 2022-06-28",
         "-H", "Content-Type: application/json",
         "-d", "{}"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def send_email_via_graph(subject, body):
    """透過 ms-graph 發送 Email"""
    import subprocess
    result = subprocess.run(
        ["python3", "/root/.openclaw/workspace/ms-graph/graph_api.py",
         "send-email", "xg@lzl.edu.kg", subject, body],
        capture_output=True, text=True,
        cwd="/root/.openclaw/workspace/ms-graph"
    )
    return result.returncode == 0

def check_and_remind():
    now = datetime.now()
    today = now.date()
    threshold = today + timedelta(days=REMIND_WITHIN_DAYS)

    # 檢查是否在允許的時段
    hour = now.hour + 8  # UTC+8
    if hour < 9 and hour >= 23:
        print(f"[{now}] 不在提醒時段（09:00-23:00），略過")
        return

    print(f"[{now}] 開始檢查 Notion 提醒...")
    data = query_all_items()
    results = data.get("results", [])

    items_to_remind = []
    for page in results:
        props = page["properties"]
        page_id = page["id"]

        # 取得名稱
        name_list = props.get("Name", {}).get("title", [])
        name = (name_list[0].get("text", {}) or {}).get("content", "無標題") if name_list else "無標題"

        # 取得截止日期
        due_prop = props.get("截止日期", {})
        due_info = due_prop.get("date") or {}
        due_str = due_info.get("start", None)

        if not due_str:
            continue

        due_date = datetime.strptime(due_str, "%Y-%m-%d").date()

        # 取得狀態
        status_prop = props.get("狀態", {})
        status = (status_prop.get("select") or {}).get("name", "未設定")

        # 已完成就跳過
        if status == "已完成":
            continue

        # 逾期（< 今天）就跳過（用戶應該已知）
        if due_date < today:
            continue

        # 檢查是否在三天內
        if due_date > threshold:
            continue

        # 檢查是否已提醒
        reminder_flag = props.get("提醒", {}).get("checkbox", False)
        if reminder_flag:
            continue

        days_left = (due_date - today).days

        # 加入清單（尚未標記提醒）
        items_to_remind.append({
            "id": page_id,
            "name": name,
            "due_str": due_str,
            "days_left": days_left,
            "status": status
        })

    if not items_to_remind:
        print(f"[{now}] 沒有需要提醒的項目")
        return

    # ====== 發送提醒 ======
    print(f"[{now}] 有 {len(items_to_remind)} 個項目需要提醒")

    # 分級：今天截止優先
    urgent = [i for i in items_to_remind if i["days_left"] == 0]
    soon = [i for i in items_to_remind if i["days_left"] == 1]
    later = [i for i in items_to_remind if i["days_left"] >= 2]

    lines = ["📬 【學習提醒】三天內截止的報告/作業：", ""]

    if urgent:
        lines.append("🚨 今天截止！")
        for item in urgent:
            lines.append(f"   ⚠️ {item['name']}（{item['due_str']}）")
        lines.append("")

    if soon:
        lines.append("📅 明天截止")
        for item in soon:
            lines.append(f"   → {item['name']}（{item['due_str']}）")
        lines.append("")

    if later:
        lines.append(f"📆 {REMIND_WITHIN_DAYS}天內截止")
        for item in later:
            lines.append(f"   • {item['name']}（{item['due_str']}，還有{item['days_left']}天）")

    lines.append("")
    lines.append("請記得去更新 Notion 的進度狀態 📊")

    message = "\n".join(lines)
    print(message)

    # 同時發送 Email
    email_lines = lines.copy()
    email_lines.insert(0, "嗨，上官陳，以下是你的學習提醒：\n\n")
    email_body = "\n".join(email_lines)
    email_sent = send_email_via_graph("📬 學習提醒：三天內截止的報告/作業", email_body)
    if email_sent:
        print("  ✅ Email 已發送至 xg@lzl.edu.kg")
    else:
        print("  ⚠️ Email 發送失敗")

    # ====== 標記已提醒 ======
    for item in items_to_remind:
        http_patch(item["id"], {
            "properties": {"提醒": {"checkbox": True}}
        })
        print(f"  ✅ 已標記：{item['name']}")

    # 更新 state
    state = load_state()
    state["last_remind_date"] = str(today)
    state["last_remind_count"] = len(items_to_remind)
    save_state(state)

    return message

if __name__ == "__main__":
    check_and_remind()
