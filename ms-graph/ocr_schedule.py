#!/usr/bin/env python3
"""
OCR Schedule Parser — Extracts dates/deadlines from text or images
and creates events in Microsoft Calendar + Notion.
Supports: YYYY/MM/DD, 民國年, 月日, 英文月份
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

# ─── Config ──────────────────────────────────────────────────────────────────

NOTION_KEY = "YOUR_NOTION_API_KEY"
NOTION_CALENDAR_DB = "32a5f8ef-1e02-8161-8cfa-d46825467bf4"
GRAPH_CONFIG = "/root/.openclaw/workspace/ms-graph/accounts/xg_lzl_edu_kg.json"
TENANT_ID = "YOUR_TENANT_ID"
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
SCOPES = [
    "offline_access", "openid", "profile",
    "Mail.Send", "Mail.ReadWrite", "Files.ReadWrite",
    "Tasks.ReadWrite", "Calendars.ReadWrite", "Calendars.Read",
]
EN_MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

# ─── Date Parsing ─────────────────────────────────────────────────────────────

def parse_dates(text: str) -> list:
    """Extract unique dates from text. Returns list of (raw_str, datetime_obj)."""
    results = []
    seen = {}  # key: date_str YYYY-MM-DD, value: (raw_str, datetime_obj)
    current_year = datetime.now().year

    # Helper: try parsing a date string with given format
    def try_date(raw, fmt=None, extra=None):
        try:
            if fmt:
                dt = datetime.strptime(raw, fmt)
            else:
                return None
            key = dt.strftime("%Y-%m-%d")
            if key not in seen:
                seen[key] = (raw, dt)
                results.append((raw, dt))
            return True
        except:
            return False

    def try_3part(raw, year_first=True, add_years=0, sep='[-/.]'):
        parts = re.split(sep + '+', raw)
        parts = [p for p in parts if p.strip()]
        if len(parts) != 3:
            return False
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if add_years:
                y += add_years
            else:
                # If no year offset, must be a valid Western year (>= 1900)
                if y < 1900 or y > 2100:
                    return False
            if not (1 <= m <= 12 and 1 <= d <= 31):
                return False
            dt = datetime(y, m, d)
            key = dt.strftime("%Y-%m-%d")
            if key not in seen:
                seen[key] = (raw, dt)
                results.append((raw, dt))
            return True
        except:
            return False

    # Find all potential date-like strings (3 or more consecutive segments with separators)
    # We search for patterns like: digits sep digits sep digits
    for m in re.finditer(r'\d+[' + re.escape('/-月日年.．．') + r']+\d+[' + re.escape('/-月日年.．．') + r']+\d+', text):
        raw = m.group().rstrip('月日年./\\-.．．').lstrip('月日年./\\-.．．')

        # Try Western year first (4-digit year)
        if try_3part(raw, True):
            continue
        if try_3part(raw, True, add_years=1911):
            continue
        # Try reversed (month first, year last - like MM/DD/YYYY or DD/MM/YYYY)
        # But in Taiwan, YY/MM/DD is common for ROC dates

    # Pattern: bare YYYY/MM/DD
    for m in re.finditer(r'(?<!\d)\d{4}[/-]\d{1,2}[/-]\d{1,2}(?!\d)', text):
        raw = m.group()
        try_3part(raw, True, sep='[-/]')

    # Pattern: 民國年 bare (e.g., 114/3/25, 114-3-25) — 2 or 3 digit year followed by / or - then month then day
    for m in re.finditer(r'(?<!\d)\d{1,3}[/-]\d{1,2}[/-]\d{1,2}(?!\d)', text):
        raw = m.group()
        # Check: first part should be a valid ROC year (1-200 range, 0 would be 1911)
        parts = re.split(r'[/-]+', raw)
        parts = [p for p in parts if p]
        if len(parts) == 3:
            try:
                y, m2, d = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= m2 <= 12 and 1 <= d <= 31 and y <= 200:
                    western = y + 1911
                    dt = datetime(western, m2, d)
                    key = dt.strftime("%Y-%m-%d")
                    if key not in seen:
                        seen[key] = (raw, dt)
                        results.append((raw, dt))
            except:
                pass

    # Pattern: YYYYMMDD compact (e.g., 20260321)
    for m in re.finditer(r'(?<!\d)\d{8}(?!\d)', text):
        raw = m.group()
        try:
            dt = datetime(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
            key = dt.strftime("%Y-%m-%d")
            if key not in seen:
                seen[key] = (raw, dt)
                results.append((raw, dt))
        except:
            pass

    # Pattern: Chinese 年月日 (e.g., 114年3月25日)
    for m in re.finditer(r'\d{1,3}年\d{1,2}月\d{1,2}日?', text):
        raw = m.group()
        parts = re.findall(r'\d+', raw)
        if len(parts) >= 3:
            try:
                y, m2, d = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= m2 <= 12 and 1 <= d <= 31:
                    if y <= 200:  # ROC year
                        y += 1911
                    dt = datetime(y, m2, d)
                    key = dt.strftime("%Y-%m-%d")
                    if key not in seen:
                        seen[key] = (raw, dt)
                        results.append((raw, dt))
            except:
                pass

    # Pattern: Chinese 月日 (e.g., 3月25日, 3月25)
    # Skip if preceded by Chinese 年 (ROC year marker)
    for m in re.finditer(r'(?<!年)\d{1,2}月\d{1,2}日?', text):
        start = m.start()
        # Skip if preceded by 2-3 digits (likely a ROC year)
        if start >= 3:
            prefix = text[start-3:start].lstrip()
            if re.match(r'^\d{1,3}$', prefix):
                continue
        raw = m.group()
        parts = re.findall(r'\d+', raw)
        if len(parts) >= 2:
            try:
                m2, d = int(parts[0]), int(parts[1])
                if 1 <= m2 <= 12 and 1 <= d <= 31:
                    dt = datetime(current_year, m2, d)
                    key = dt.strftime("%Y-%m-%d")
                    if key not in seen:
                        seen[key] = (raw, dt)
                        results.append((raw, dt))
            except:
                pass

    # Pattern: MM/DD or MM-DD — skip if preceded by ROC year (1-3 digits + /)
    for m in re.finditer(r'\b\d{1,2}[/-]\d{1,2}\b', text):
        start = m.start()
        if start >= 2:
            prefix = text[max(0, start-3):start]
            if re.search(r'\d{1,3}[/-]$', prefix):
                continue
        start = m.start()
        # Skip if preceded by 2-3 digits (likely a ROC year)
        if start >= 3:
            prefix = text[start-3:start].lstrip()
            if re.match(r'^\d{1,3}$', prefix):
                continue
        raw = m.group()
        parts = raw.split(m.group()[1])  # split by separator
        if len(parts) == 2:
            try:
                m2, d = int(parts[0]), int(parts[1])
                if 1 <= m2 <= 12 and 1 <= d <= 31:
                    dt = datetime(current_year, m2, d)
                    key = dt.strftime("%Y-%m-%d")
                    if key not in seen:
                        seen[key] = (raw, dt)
                        results.append((raw, dt))
            except:
                pass

    # Pattern: English month name (March 25, Mar. 25, March 25, 2026)
    for m in re.finditer(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?', text, re.I):
        raw = m.group()
        month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', m.group(), re.I)
        nums = re.findall(r'\d+', raw)
        if month_match and len(nums) >= 1:
            m_name = month_match.group(1).lower()
            day = int(nums[0])
            year = int(nums[1]) if len(nums) > 1 else current_year
            try:
                dt = datetime(year, EN_MONTHS.get(m_name[:3], 1), day)
                key = dt.strftime("%Y-%m-%d")
                if key not in seen:
                    seen[key] = (raw, dt)
                    results.append((raw, dt))
            except:
                pass

    results.sort(key=lambda x: x[1])
    return results

def suggest_type(text: str) -> str:
    text_lower = text.lower()
    if any(k in text_lower for k in ['段考', '期中考', '期末考', 'exam', '考試']):
        return '📚 段考'
    if any(k in text_lower for k in ['作業', 'hw', 'homework', '報告', 'report', '繳交', 'due']):
        return '📝 作業'
    if any(k in text_lower for k in ['學校', 'school', '活動', 'activity']):
        return '🏫 學校活動'
    return '📅 其他'

def extract_title_around_date(text: str, date_str: str) -> str:
    """Extract context around a specific date occurrence — ONLY look after the date."""
    pos = text.find(date_str)
    if pos == -1:
        return "行事曆事件"

    # Only look AFTER the date (40 chars after, not before to avoid other dates)
    start = pos + len(date_str)
    end = min(len(text), start + 50)
    snippet = text[start:end]

    # Remove all date patterns from snippet
    cleaned = re.sub(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', ' ', snippet)
    cleaned = re.sub(r'\d{1,3}[/-]\d{1,2}[/-]\d{1,2}', ' ', cleaned)
    cleaned = re.sub(r'\d{1,3}年\d{1,2}月\d{1,2}日?', ' ', cleaned)
    cleaned = re.sub(r'\d{1,2}月\d{1,2}日?', ' ', cleaned)
    cleaned = re.sub(r'\b\d{1,2}[-/]\d{1,2}\b', ' ', cleaned)
    cleaned = re.sub(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Skip common filler words
    skip = {'的', '在', '是', '和', '與', '及', '到', '從', '為', '這', '那', '有', '沒',
            '請', '記得', '記', '記下', '於', '截止', '截止時間', '繳交', '時間',
            '日', '月', '年'}
    # Split on any non-alphanumeric character
    words = re.split(r'[\s,，、。.!！?？:：/()（）\[\]【】"\'「」『』\-—–_]+', cleaned)
    words = [w for w in words if w not in skip and len(w) > 1]
    result = ''.join(words[:6])[:50].strip('：:,，,.。!?！? ')
    return result if result else "行事曆事件"

# ─── Token Manager ────────────────────────────────────────────────────────────

def get_token():
    import urllib.request, urllib.parse
    account = json.load(open(GRAPH_CONFIG))
    if account.get("expires_at", 0) > time.time() + 300:
        return account["access_token"]
    data = {
        "grant_type": "refresh_token", "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET, "refresh_token": account["refresh_token"],
        "scope": " ".join(SCOPES),
    }
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    account["access_token"] = result["access_token"]
    account["expires_at"] = time.time() + result.get("expires_in", 3600)
    if "refresh_token" in result:
        account["refresh_token"] = result["refresh_token"]
    with open(GRAPH_CONFIG, "w") as f:
        json.dump(account, f, indent=2)
    return result["access_token"]

# ─── Calendar API ─────────────────────────────────────────────────────────────

def create_calendar_event(subject, start_iso, end_iso, body=None):
    import urllib.request
    token = get_token()
    data = {
        "subject": subject,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Taipei"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Taipei"},
    }
    if body:
        data["body"] = {"contentType": "text", "content": body}
    req = urllib.request.Request(
        "https://graph.microsoft.com/v1.0/me/events",
        data=json.dumps(data).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"status": "ok"}
    except urllib.request.HTTPError as e:
        return {"error": e.read().decode()}

# ─── Notion API ──────────────────────────────────────────────────────────────

def create_notion_event(subject, date_str, end_date=None, event_type="📅 其他", note=""):
    import urllib.request
    payload = {
        "parent": {"database_id": NOTION_CALENDAR_DB},
        "properties": {
            "名稱": {"title": [{"text": {"content": subject}}]},
            "日期": {"date": {"start": date_str}},
            "類型": {"select": {"name": event_type}},
            "備註": {"rich_text": [{"text": {"content": note[:500]}}]},
            "已完成": {"checkbox": False}
        }
    }
    if end_date:
        payload["properties"]["結束時間"] = {"date": {"start": end_date}}
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {NOTION_KEY}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.request.HTTPError as e:
        return {"error": e.read().decode()}

# ─── Main Parser ─────────────────────────────────────────────────────────────

def parse_and_create(text: str, dry_run: bool = False):
    dates = parse_dates(text)
    if not dates:
        print("No dates found.")
        return []

    print(f"Found {len(dates)} date(s):\n")
    created = []

    for raw_date, dt in dates:
        event_type = suggest_type(text)
        title = extract_title_around_date(text, raw_date)
        end_dt = dt + timedelta(hours=2)
        start_iso = dt.strftime("%Y-%m-%dT09:00:00")
        end_iso = end_dt.strftime("%Y-%m-%dT11:00:00")

        event_data = {
            "subject": f"[{event_type}] {title}",  # title already has event_type embedded
            "start": start_iso,
            "end": end_iso,
            "type": event_type,
        }

        print(f"📅 {raw_date} → {dt.strftime('%Y-%m-%d')}")
        print(f"   [{event_type}] {title}")

        if not dry_run:
            try:
                create_calendar_event(event_data["subject"], start_iso, end_iso, text[:200])
                print("   ✅ Calendar ✓")
            except Exception as e:
                print(f"   ⚠️ Calendar: {e}")
            try:
                result = create_notion_event(event_data["subject"], dt.strftime("%Y-%m-%d"),
                                             end_dt.strftime("%Y-%m-%d"), event_type, text[:500])
                url = result.get("url", "")
                if url:
                    print(f"   ✅ Notion ✓ ({url})")
                else:
                    print(f"   ⚠️ Notion: {result.get('error', 'failed')}")
            except Exception as e:
                print(f"   ⚠️ Notion: {e}")
        print()
        created.append(event_data)

    return created

# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: ocr_schedule.py [dry-run|parse] <text>")
        sys.exit(1)
    cmd = sys.argv[1]
    text = " ".join(sys.argv[2:])
    if not text:
        print("No text provided")
        sys.exit(1)
    dry_run = (cmd == "dry-run")
    parse_and_create(text, dry_run=dry_run)

if __name__ == "__main__":
    main()
