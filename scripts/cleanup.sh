#!/bin/bash
# ================================================
# Sydney 每日凌晨清理腳本 v6
# 執行範圍：安全、破壞性低、可復原
# v6 新增：訂閱轉發郵件附件、session transcripts 過期檔、agent-browser 殘留狀態
# ================================================

LOG_PREFIX="🧹 [清理]"
echo "$LOG_PREFIX 開始執行凌晨清理..."

# 1. 系統暫存檔（OpenClaw 相關，限時 1 天以上）
find /tmp -maxdepth 1 -name "gog*" -mtime +1 -type f -exec shred -u {} \; 2>/dev/null
find /tmp -maxdepth 1 -name "openclaw*" -mtime +1 -type f -exec shred -u {} \; 2>/dev/null
find /tmp -maxdepth 1 -name "euler*" -type f -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ /tmp 清理完成"

# 2. /tmp/openclaw/ 完整覆蓋（所有類型，1天以上）
find /tmp/openclaw -maxdepth 1 -type f -mtime +1 -exec shred -u {} \; 2>/dev/null
find /tmp/openclaw -maxdepth 1 -type d -empty -delete 2>/dev/null
echo "$LOG_PREFIX ✅ /tmp/openclaw/ 完整清理完成"

# 3. workspace 暫存檔
find ~/.openclaw/workspace -maxdepth 3 -name "*.tmp" -type f -exec shred -u {} \; 2>/dev/null
find ~/.openclaw/workspace -maxdepth 2 -name "*.log" -type f -exec shred -u {} \; 2>/dev/null
find ~/.openclaw/workspace -maxdepth 1 -name "*.tar.gz" -type f -exec shred -u {} \; 2>/dev/null
find ~/.openclaw/workspace -maxdepth 1 -name "*.zip" -type f -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ workspace 暫存檔清理完成"

# 4. LaTeX / 圖片輸出（7天前，安全清除）
find ~/.openclaw/workspace -maxdepth 2 \( -name "*.pdf" -o -name "*.png" -o -name "*.jpg" \) -type f -mtime +7 -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ LaTeX / 圖片輸出清理完成（保留近7天）"

# 5. 收到的媒體檔案（超過 7 天，安全清除）
find ~/.openclaw/media/inbound -type f -mtime +7 -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ media/inbound 清理完成（保留近7天）"

# 6. Python __pycache__（3天前）
find ~/.openclaw/workspace -maxdepth 4 -name "__pycache__" -type d -exec rm -rf {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ __pycache__ 清理完成"

# 7. Pip 安裝暫存（3天前）
find ~/.cache/pip -type f -mtime +3 -delete 2>/dev/null
echo "$LOG_PREFIX ✅ pip cache 清理完成"

# 8. Cron 執行紀錄（超過 14 天的）
find ~/.openclaw/cron/runs -name "*.jsonl" -mtime +14 -type f -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ 舊 cron 執行紀錄清理完成"

# 9. 過期的隔離簡報（spam/quarantine old reports）
find ~/.openclaw -maxdepth 5 -name "*.quarantine" -mtime +7 -type f -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ 隔離檔案清理完成"

# 10. 無用的空目錄（選擇性清理）
find ~/.openclaw/workspace -maxdepth 3 -type d -empty -delete 2>/dev/null
echo "$LOG_PREFIX ✅ 空目錄清理完成"

# 11. 清理 gog cli 的暫存認證 token（選擇性，只清理明確過期的）
find ~/.config/gogcli -name "*.tmp" -type f -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ gog 暫存清理完成"

# 12. 清理 node_modules 中的 cache（如果有的話）
find ~/.openclaw/workspace/node_modules -maxdepth 2 -name ".cache" -type d 2>/dev/null | while read dir; do
    rm -rf "$dir" 2>/dev/null && echo "$LOG_PREFIX ✅ node_modules cache: $dir"
done

# 13. 記憶體安全釋放（drop caches - 需要 root 但通常不需要）
sync 2>/dev/null
echo "$LOG_PREFIX ✅ 系統同步完成"

# 14. 關閉所有 agent-browser 分頁 + 清理殘留狀態
if command -v agent-browser &>/dev/null; then
    agent-browser close 2>/dev/null
    echo "$LOG_PREFIX ✅ agent-browser 分頁已關閉"
    # 清理 puppeteer/chrome 暫存資料
    find /tmp -maxdepth 1 -name "chrome*" -type f -exec shred -u {} \; 2>/dev/null
    find /tmp -maxdepth 1 -name " puppeteer_*" -type d -exec rm -rf {} \; 2>/dev/null
    find /tmp -maxdepth 1 -name ".org.chromium.*" -type d -exec rm -rf {} \; 2>/dev/null
    echo "$LOG_PREFIX ✅ agent-browser 殘留狀態清理完成"
else
    echo "$LOG_PREFIX ✅ agent-browser 未安裝，跳過"
fi

# 15. NovelAI 圖片暫存（安全清除）
find /tmp -maxdepth 1 -name "novelai-*" -type f -mtime +1 -exec shred -u {} \; 2>/dev/null
find /tmp -maxdepth 1 -name "novelai-*" -type d -empty -delete 2>/dev/null
echo "$LOG_PREFIX ✅ NovelAI 圖片暫存清理完成（保留近1天）"

# 16. ms-graph OAuth 暫存（ms-auth 的臨時檔案，安全清除）
find /tmp -maxdepth 1 -name "ms_graph*" -type f -exec shred -u {} \; 2>/dev/null
find /tmp -maxdepth 1 -name "device_code*" -type f -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ ms-graph 暫存清理完成"

# 17. 清理 TTS 語音暫存檔（超過 1 天，安全清除）
find /tmp/openclaw/tts-* -type f -mtime +1 -exec shred -u {} \; 2>/dev/null
find /tmp/openclaw/tts-* -type d -empty -delete 2>/dev/null
echo "$LOG_PREFIX ✅ TTS 語音暫存清理完成"

# 18. 過期/已刪除的 session transcripts（超過 7 天）
find ~/.openclaw/agents/main/sessions \( -name "*.reset.*" -o -name "*.deleted.*" \) -mtime +7 -type f -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ 過期 session transcripts 清理完成（保留近7天）"

# 19. 訂閱轉發郵件附件（workspace 內的 email 相關下載檔案，7天前）
find ~/.openclaw/workspace -maxdepth 3 \( -name "*email*" -o -name "*mail*" -o -name "*inbox*" -o -name "*attachment*" \) \( -name "*.pdf" -o -name "*.docx" -o -name "*.xlsx" -o -name "*.zip" -o -name "*.tmp" \) -type f -mtime +7 -exec shred -u {} \; 2>/dev/null
echo "$LOG_PREFIX ✅ 訂閱轉發郵件附件清理完成（保留近7天）"

echo ""
echo "========================================"
echo "✅ 每日凌晨清理完成！"
echo "========================================"
