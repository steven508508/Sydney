#!/usr/bin/env python3
"""
Sydney Security Module v2
三層防護：Hash驗證、Prompt注入偵測、URL沙盒
"""
import hashlib
import os
import re
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("/root/.openclaw/workspace")
SECURITY_DIR = WORKSPACE / ".sydney_security"
HASH_DB = SECURITY_DIR / "hashes.json"
INTEGRITY_LOG = SECURITY_DIR / "integrity.log"

CRITICAL_FILES = [
    "SOUL.md", "AGENTS.md", "USER.md", "MEMORY.md",
    "TOOLS.md", "IDENTITY.md", "HEARTBEAT.md"
]

PROMPT_PATTERNS = [
    r"you are now\s+(?:\w+\s+){0,5}?(?:assistant|AI|model|bot)",
    r"ignore\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions?|commands?|rules?)",
    r"(?:disregard|forget)\s+",
    r"new\s+(?:system\s+)?prompt[:：]",
    r"system\s+prompt\s*[:=]",
    r"you are a\s+(?:\w+\s+){0,3}?(?:AI|assistant|model|bot)",
    r"pretend you are",
    r"roleplay as",
    r"<system>",
    r"enable developer",
    r"\bDAN\b",
    r"developer mode",
    r"instead of (?:what|how) you were (?:programmed|trained|built)",
    r"override\s+(?:your\s+|the\s+)?(?:safety|content|ethical)",
    r"bypass\s+(?:your\s+|the\s+)?(?:safety|content|restriction)",
    r"forbidden\s+(?:to\s+)?disclose",
    r"main goal is to (?:harm|exfiltrate|steal|delete)",
    r"exfiltrate",
    r"(?:sudo|root|admin)[:：]?\s*(?:rm|del|delete|format|wipe)",
    r"set system prompt to",
    r"reveal (?:your\s+|the\s+)?(?:system\s+)?prompt",
    r"extract (?:your\s+|the\s+)?instructions",
    r"print\s+(?:\w+\s+){0,3}system prompt",
    r"(?:delete|remove)\s+(?:all\s+)?(?:your\s+)?(?:data|files|memory)",
    r"ignore\s+(?:this|these)\s+(?:instructions?|rules?)",
]

ALERT_THRESHOLD = 2

# 外部發布敏感內容 Pattern
EXTERNAL_POST_SENSITIVE_PATTERNS = [
    r"moltbook_sk_[a-zA-Z0-9_-]{20,}",
    r"Bearer\s+[a-zA-Z0-9_-]{20,}",
    r"api[_-]?key[:\s]+[a-zA-Z0-9_-]{10,}",
    r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
    r"-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----",
    r"secret[:\s]+[a-zA-Z0-9_-]{10,}",
    r"password[:\s]+\S+",
    r"passwd[:\s]+\S+",
    r"pwd[:\s]+\S+",
    r"[A-Z]\d{9}",  # 台灣身份證格式
    r"09\d{8}",  # 台灣手機號格式
]


class SecurityModule:
    def __init__(self):
        self.hash_db = self._load_hash_db()
        self.alerts = []

    def _load_hash_db(self) -> dict:
        if HASH_DB.exists():
            return json.loads(HASH_DB.read_text())
        return {}

    def _compute_hash(self, filepath: Path) -> str:
        h = hashlib.sha256()
        h.update(filepath.read_bytes())
        return h.hexdigest()

    def verify_workspace_integrity(self) -> dict:
        results = {}
        for fname in CRITICAL_FILES:
            fpath = WORKSPACE / fname
            if not fpath.exists():
                results[fname] = {"status": "missing", "hash": None}
                continue
            current_hash = self._compute_hash(fpath)
            stored_hash = self.hash_db.get(fname)
            if stored_hash is None:
                self.hash_db[fname] = current_hash
                results[fname] = {"status": "first_seen", "hash": current_hash[:16]}
            elif stored_hash != current_hash:
                results[fname] = {
                    "status": "MODIFIED",
                    "hash": current_hash[:16],
                    "stored": stored_hash[:16]
                }
            else:
                results[fname] = {"status": "OK", "hash": current_hash[:16]}
        self._save_hash_db()
        return results

    def _save_hash_db(self):
        SECURITY_DIR.mkdir(parents=True, exist_ok=True)
        HASH_DB.write_text(json.dumps(self.hash_db, indent=2))

    def log_alert(self, source: str, message: str, severity: str = "HIGH"):
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{severity}] {source}: {message}"
        INTEGRITY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(INTEGRITY_LOG, "a") as f:
            f.write(log_entry + "\n")
        self.alerts.append(log_entry)

    def detect_prompt_injection(self, text: str, source: str = "unknown") -> dict:
        matches = []
        for pattern in PROMPT_PATTERNS:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    matches.append(pattern)
            except re.error:
                continue

        count = len(matches)
        if count >= ALERT_THRESHOLD:
            risk_level = "HIGH"
            action = "truncate"
            self.log_alert(source, f"Prompt injection: {count} patterns found", "HIGH")
        elif count == 1:
            risk_level = "MEDIUM"
            action = "warn"
            self.log_alert(source, f"Suspicious pattern: {matches[0][:50]}", "MEDIUM")
        else:
            risk_level = "LOW"
            action = "allow"

        return {
            "risk": risk_level,
            "count": count,
            "matches": matches[:5],
            "action": action,
            "source": source
        }

    def process_external_content(self, content: str, source: str) -> str:
        result = self.detect_prompt_injection(content, source)

        if result["action"] == "truncate":
            truncated = content[:800] + f"\n\n--- [內容已截断：檢測到 {result['count']} 個可疑模式] ---"
            return truncated
        elif result["action"] == "warn":
            warning = f"\n\n<!-- [⚠️ 安全提示：檢測到 {result['count']} 個可疑模式] -->\n"
            return warning + content
        return content

    def scan_for_external_posting(self, text: str) -> dict:
        """發布前敏感內容掃描，返回是否安全"""
        found = []
        for pattern in EXTERNAL_POST_SENSITIVE_PATTERNS:
            try:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    found.append({
                        "pattern": pattern,
                        "matched": match.group()[:30]
                    })
            except re.error:
                continue

        is_safe = len(found) == 0

        if not is_safe:
            self.log_alert(
                "external_post",
                f"Sensitive content detected before posting: {[f['matched'] for f in found]}",
                "HIGH"
            )

        return {
            "safe": is_safe,
            "found": found,
            "action": "BLOCK" if not is_safe else "ALLOW"
        }

    def fetch_url_sandbox(self, url: str, max_size_kb: int = 500) -> dict:
        with tempfile.TemporaryDirectory(dir="/tmp") as tmpdir:
            output_file = Path(tmpdir) / "fetched"
            try:
                result = subprocess.run(
                    ["curl", "-s", "--max-time", "30", "-L",
                     "-o", str(output_file),
                     "-H", "User-Agent: Mozilla/5.0",
                     "--max-filesize", str(max_size_kb * 1024),
                     url],
                    capture_output=True, text=True, timeout=35
                )
                if result.returncode != 0:
                    return {"error": f"curl failed: {result.stderr[:200]}"}

                if not output_file.exists():
                    return {"error": "No content downloaded"}

                content = output_file.read_text(errors="replace")
                scan = self.detect_prompt_injection(content, url)

                return {
                    "content": content[:2000],
                    "size": len(content),
                    "scan": scan
                }
            except subprocess.TimeoutExpired:
                return {"error": "Fetch timeout"}
            except Exception as e:
                return {"error": str(e)}


if __name__ == "__main__":
    sm = SecurityModule()
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    if cmd == "verify":
        print("Sydney Security Check")
        print("=" * 44)
        results = sm.verify_workspace_integrity()
        for fname, res in results.items():
            print(f"  {res['status']:12} | {fname:20} | {res.get('hash', '?')[:8]}...")

    elif cmd == "scan" and len(sys.argv) >= 3:
        text = sys.argv[2]
        result = sm.detect_prompt_injection(text, "cli")
        print(f"Risk: {result['risk']}")
        print(f"Patterns found: {result['count']}")
        for m in result["matches"]:
            print(f"  - {m[:60]}")

    elif cmd == "fetch" and len(sys.argv) >= 3:
        result = sm.fetch_url_sandbox(sys.argv[2])
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Size: {result['size']} bytes | Risk: {result['scan']['risk']}")

    else:
        print("Usage: security.py [verify|scan <text>|fetch <url>]")
