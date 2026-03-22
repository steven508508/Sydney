# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

---

## 🔐 重要：不要在這裡寫入明文 API Key

所有 API Key 透過環境變數管理，不要寫在純文字檔案裡。

---

## NovelAI 圖片生成

- **腳本位置**：`~/.openclaw/workspace/skills/novelai-image/novelai_image.py`
- **API Key**：透過環境變數 `NOVELAI_API_KEY` 取得
- **說明**：session 預設不繼承 bashrc，需手動 export

---

## LaTeX 數學輸出

- **中文字體**：`fonts-noto-cjk`（Noto Sans/Serif CJK）
- **字體路徑**：`/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`
- **工具**：Python matplotlib + fontproperties
- **重要**：數學題圖片必須支援中文，確保中文正常顯示

---

## Notion 整合

- **API Key**：透過環境變數 `NOTION_API_KEY` 取得
- **主頁面**：Sydney 工作區
- **使用方式**：透過 notion skill 讀取/寫入

---

## Microsoft Graph（學校信箱瞬光）

- **腳本位置**：`~/.openclaw/workspace/ms-graph/graph_api.py`
- **功能**：讀取/發送學校信箱（xg@lzl.edu.kg）
- **OAuth**：已設定，Token 自動刷新
- **狀態**：✅ 正常運作

---

## gog（Google Workspace）

- **帳號**：kiana@bh3.eu（主要）、csh@hs.edu.rs
- **OAuth**：已設定，keyring 密碼需正確才能解密

---

## 其他工具

| 工具 | 狀態 | 說明 |
|------|------|------|
| Veryfi OCR | ✅ 正常 | header 需用 Client-Id + Authorization |
| Brave Search | ✅ 正常 | web_search 工具 |
| Minimax | ✅ 正常 | 目前對話使用 |
