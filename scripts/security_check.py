#!/usr/bin/env python3
"""
Sydney Security Check - 整合進 heartbeat
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/.sydney_security')

from prompt_detector import SecurityModule

sm = SecurityModule()

# 1. Workspace 完整性驗證
results = sm.verify_workspace_integrity()
modified = {k: v for k, v in results.items() if v["status"] == "MODIFIED"}

if modified:
    msgs = [f"  {fname}: {info['hash'][:8]} (was {info['stored'][:8]})"
            for fname, info in modified.items()]
    alert = f"🚨 【安全警示】Workspace 檔案被修改！\n" + "\n".join(msgs)
    print(alert)
    sys.exit(1)
else:
    print("✅ Workspace 完整性驗證通過")

# 2. 檢查是否有新的 Alert
if sm.alerts:
    print(f"⚠️  有 {len(sm.alerts)} 個安全警報，詳見 .sydney_security/integrity.log")
    sys.exit(1)
else:
    print("✅ 無 Prompt 注入警報")
    sys.exit(0)
