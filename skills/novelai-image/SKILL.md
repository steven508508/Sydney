---
name: novelai-image
description: |
  使用 NovelAI 官方 API 進行圖片生成。
  內建 35-45 秒隨機間隔保護，避免因頻率過高觸發 403 禁用。
  支援 txt2img 和 img2img 兩種模式。
  ⚠️  請勿在短時間內連續請求多張圖片，每次生成後都會自動等待 35-45 秒。
---

# NovelAI 圖片生成技能 v3

## 功能一覽

- ✅ txt2img（文字生圖）
- ✅ img2img（圖片生圖）
- ✅ 3 種預設解析度 + 自定義（均不消耗 Anlas 點數）
- ✅ 錯誤分類與最多 3 次自動重試
- ✅ Prompt 逃脫（特殊字元自動過濾）
- ✅ 測試模式（驗證 API Key）
- ✅ 標準化日誌（寫入 `/tmp/novelai_logs/`）

---

## 安裝依賴

```bash
pip install Pillow requests
```

---

## 使用方式

### 基本生圖

```
python3 novelai_image.py '1girl, solo, white dress, garden'
```

### 解析度選擇（互動模式）

```
python3 novelai_image.py
# 會引導你選擇解析度（1/2/3/4 自定義）
```

### 指定參數

| 參數 | 說明 | 預設 |
|------|------|------|
| `-r, --resolution` | 解析度 | `832x1216` |
| `-s, --steps` | 推論步數 | `28` |
| `-g, --guidance` | 引導強度 | `4.0` |
| `--seed` | 固定種子（可重現） | 隨機 |
| `--max-retries` | 最大重試次數 | `3` |

**解析度預設：**
- `832x1216` — 豎向立繪（人形圖推薦）
- `1024x1024` — 方形頭像
- `1216x832` — 橫向風景
- 自定義（格式：`寬x高`，如 `640x960`）

### Img2Img 模式

```bash
python3 novelai_image.py '1girl, elegant dress' \
  --img2img /path/to/input.png \
  --strength 0.3
```

`--strength` 範圍 0.0~1.0，越高越接近原圖（預設 0.3）。

### 測試模式

```bash
python3 novelai_image.py --test
```

驗證 API Key 是否有效，以及 API 連線狀態。

---

## 延遲保護說明

腳本內建 **35-45 秒隨機等待**，每次請求後才會發送，用來避免：

- 🚫 403/429 頻率限制
- 🚫 Anlas 點數異常消耗
- 🚫 小圖功能被鎖

---

## 日誌位置

每次運行的日誌寫入：
```
/tmp/novelai_logs/novelai_YYYYMMDD.log
```

---

## 錯誤代碼說明

| 代碼 | 意義 | 可重試 |
|------|------|--------|
| 400 | 參數或 Prompt 錯誤 | ❌ |
| 401 | API Key 無效或過期 | ❌ |
| 403 | 帳號被封禁 | ❌ |
| 418 | Anlas 點數不足 | ❌ |
| 420/429 | 頻率限制 | ✅ |
| 500/502/503 | NovelAI 伺服器問題 | ✅ |

---

## 注意事項

- **Prompt 請用英文**，自動過濾特殊控制字元
- 圖片預設命名：`/tmp/novelai_{時間}_{seed}.png`
- Img2Img 會自動縮減過大圖片（>4MB）以避免 API 上傳失敗
- 所有 API Key 請透過環境變數 `NOVELAI_API_KEY` 設定
