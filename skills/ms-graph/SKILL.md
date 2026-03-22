---
name: ms-graph
description: Microsoft Graph API 整合技能。當用戶提到 Email、Outlook、OneDrive、Todo、Microsoft 365、學校信箱、工作信箱等關鍵字時觸發。支援多帳號管理（最多5個）。
---

# ms-graph — Microsoft Graph API 整合

## 功能一覽

| 功能 | 說明 |
|------|------|
| 📧 Email | 發送、讀取郵件 |
| 📁 OneDrive | 列出、下載、上傳檔案 |
| ✅ Todo | 讀取/新增待辦事項 |
| 📅 Calendar | 列出/新增行事曆行程 |

## 多帳號支援

### 儲存位置
```
~/.openclaw/workspace/ms-graph/
├── accounts/
│   └── xg_lzl_edu_kg.json   # 學校信箱
├── config.json               # 目前作用中帳號
└── graph_api.py             # API 主程式
```

### 支援數量
- 最多 **5 個帳號**
- 每個帳號有獨立暱稱和 OAuth token

### CLI 指令

```bash
# 帳號管理
python3 ms-graph/graph_api.py list              # 列出所有帳號
python3 ms-graph/graph_api.py add [email] [nickname]  # 新增帳號（OAuth）
python3 ms-graph/graph_api.py switch <id>        # 切換作用中帳號
python3 ms-graph/graph_api.py remove <id>       # 刪除帳號
python3 ms-graph/graph_api.py rename <id> <新暱稱>  # 編輯暱稱
python3 ms-graph/graph_api.py refresh           # 刷新 token

# 服務功能
python3 ms-graph/graph_api.py send-email <to> <subj> <body>
python3 ms-graph/graph_api.py read-emails [folder] [top]
python3 ms-graph/graph_api.py list-files [path]
python3 ms-graph/graph_api.py list-tasks
python3 ms-graph/graph_api.py list-events [days]
python3 ms-graph/graph_api.py create-event <subject> <start_iso> <end_iso> [location]
```

## OAuth 設定

- **Azure App**: Claw Sydney
- **Client ID**: 825ae3b1-86e9-406a-8d89-0450254c9698
- **Tenant ID**: 9dc0194d-a4e8-429b-aad9-b343d182949f
- **驗證方式**: Authorization Code Flow（支援 refresh token）
- **驗證 URL**: `http://localhost:18901/callback`

## 權限（Scopes）

```
offline_access, openid, profile,
Mail.Send, Mail.ReadWrite,
Files.ReadWrite,
Tasks.ReadWrite,
Calendars.ReadWrite, Calendars.Read
```

## 自動刷新

- 每 6 小時自動刷新 token（cron job）
- Access token 效期約 1 小時，refresh token 約 90 天
- Token 過期前會自動嘗試刷新

## 注意事項

- 學校信箱（@lzl.edu.kg）的 `/me` 端點可能有 403 限制（組織政策），實際功能不受影響
- 刪除檔案功能預設未啟用，確保安全
