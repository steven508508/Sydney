# NovelAI 圖片生成腳本 v3.1
# 新增：--cleanup 完成後自動清理資源

import sys
import os
import re
import json
import time
import random
import logging
import zipfile
import io
import argparse
import base64
import requests
from datetime import datetime

# ── 日誌設定 ──────────────────────────────────────────────
LOG_DIR = "/tmp/novelai_logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, f"novelai_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("novelai")

# ── API 設定 ──────────────────────────────────────────────
API_KEY = os.getenv("NOVELAI_API_KEY")
if not API_KEY:
    logger.error("NOVELAI_API_KEY 環境變數未設定")
    sys.exit(1)

API_URL = "https://image.novelai.net/ai/generate-image"

# ── 解析度選項 ───────────────────────────────────────────
RESOLUTION_PRESETS = {
    "1": {"name": "豎向立繪（人形圖推薦）",  "value": "832x1216"},
    "2": {"name": "方形頭像",                "value": "1024x1024"},
    "3": {"name": "橫向風景",                "value": "1216x832"},
    "4": {"name": "自定義解析度",              "value": None},
}

# ── Prompt 逃脫 ─────────────────────────────────────────
def escape_prompt(prompt: str) -> str:
    prompt = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", prompt)
    return prompt.strip()

# ── 清理函式 ────────────────────────────────────────────
def cleanup_temp_files(output_path: str = None):
    """自動刪除生成的圖檔和日誌，保持乾淨"""
    cleaned = []

    # 刪除剛輸出的圖檔
    if output_path and os.path.exists(output_path):
        os.remove(output_path)
        cleaned.append(f"圖檔: {output_path}")

    # 刪除所有 novelai_ 開頭的 PNG（防漏網之魚）
    for f in os.listdir("/tmp"):
        if f.startswith("novelai_") and f.endswith(".png"):
            path = f"/tmp/{f}"
            try:
                os.remove(path)
                cleaned.append(f"圖檔: {path}")
            except OSError:
                pass

    if cleaned:
        logger.info("🗑️ 自動清理完成：" + " | ".join(cleaned))
    else:
        logger.info("🗑️ 清理：無殘留檔案")


# ── 錯誤分類 ────────────────────────────────────────────
class NovelAIError(Exception):
    def __init__(self, code: int, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(f"[{code}] {message}")

ERROR_MAP = {
    400: lambda m: NovelAIError(400, f"請求格式錯誤: {m}", retryable=False),
    401: lambda m: NovelAIError(401, f"認證失敗，API Key 無效或已過期: {m}", retryable=False),
    403: lambda m: NovelAIError(403, f"禁止訪問: {m}", retryable=False),
    404: lambda m: NovelAIError(404, f"端點不存在: {m}", retryable=False),
    418: lambda m: NovelAIError(418, f"Anlas 點數不足: {m}", retryable=False),
    420: lambda m: NovelAIError(420, f"頻率限制: {m}", retryable=True),
    429: lambda m: NovelAIError(429, f"頻率限制: {m}", retryable=True),
    500: lambda m: NovelAIError(500, f"伺服器錯誤: {m}", retryable=True),
    502: lambda m: NovelAIError(502, f"伺服器錯誤: {m}", retryable=True),
    503: lambda m: NovelAIError(503, f"服務暫不可用: {m}", retryable=True),
}

def parse_error(status_code: int, response_text: str) -> NovelAIError:
    try:
        d = json.loads(response_text)
        msg = d.get("message", response_text[:100])
    except Exception:
        msg = response_text[:100]
    if status_code == 400:
        if "credit" in msg.lower() or "anlas" in msg.lower():
            return NovelAIError(418, f"Anlas 點數不足: {msg}", retryable=False)
        return NovelAIError(400, f"請求參數錯誤: {msg}", retryable=False)
    if status_code in ERROR_MAP:
        return ERROR_MAP[status_code](msg)
    return NovelAIError(status_code, f"未知錯誤: {msg}", retryable=False)


# ── 核心生成 ────────────────────────────────────────────
def generate(
    prompt: str,
    resolution: str = "832x1216",
    steps: int = 28,
    guidance: float = 4.0,
    seed: int = None,
    init_image: str = None,
    init_image_strength: float = 0.3,
    max_retries: int = 3,
    auto_cleanup: bool = False,
) -> str:
    prompt = escape_prompt(prompt)
    if not prompt:
        raise NovelAIError(0, "Prompt 不能為空", retryable=False)

    resolved_seed = seed if seed is not None else random.randint(0, 2**32 - 1)
    wait_time = random.randint(35, 45)

    logger.info(f"🎨 生成請求 | 解析度: {resolution} | 步數: {steps} | 引導: {guidance} | Seed: {resolved_seed}")
    if init_image:
        logger.info(f"📸 Img2Img 模式 | 強度: {init_image_strength}")
    logger.info(f"提示詞: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    logger.info(f"⏳ 等待 {wait_time} 秒後發送...")
    time.sleep(wait_time)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    if not init_image:
        params = {
            "steps": steps,
            "resolution": resolution,
            "guidance": guidance,
            "seed": resolved_seed,
        }
        payload = {"input": prompt, "model": "nai-diffusion-3", "parameters": params}
    else:
        # ── Img2Img 模式：檢查圖片是否存在 ──
        if not os.path.exists(init_image):
            raise NovelAIError(0, f"Img2Img 圖片不存在: {init_image}", retryable=False)
        file_size = os.path.getsize(init_image)
        if file_size > 5 * 1024 * 1024:  # 超過 5MB 則警告
            logger.warning(f"⚠️  圖片大小 {file_size//1024//1024}MB 過大，可能導致上傳失敗，建議在 5MB 以下")
        with open(init_image, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")
        params = {
            "steps": steps,
            "resolution": resolution,
            "guidance": guidance,
            "seed": resolved_seed,
            "image": image_b64,
            "image_strength": init_image_strength,
        }
        payload = {"input": prompt, "model": "nai-diffusion-3", "parameters": params}

    attempt = 0
    last_err = None

    while attempt <= max_retries:
        attempt += 1
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=180)

            if response.status_code == 200:
                z = zipfile.ZipFile(io.BytesIO(response.content))
                filenames = z.namelist()
                if not filenames:
                    raise NovelAIError(0, "ZIP 檔案為空", retryable=False)

                timestamp = datetime.now().strftime("%H%M%S")
                output_path = f"/tmp/novelai_{timestamp}_{resolved_seed}.png"
                z.extract(filenames[0], "/tmp/")
                os.rename("/tmp/" + filenames[0], output_path)

                logger.info(f"✅ 完成！檔案: {output_path} ({(len(response.content))//1024} KB)")

                # ── 自動清理 ──────────────────────────
                if auto_cleanup:
                    cleanup_temp_files(output_path)
                else:
                    logger.info("🗑️ 清理：已保留圖檔，請記得手動刪除或說「清理」")

                return output_path

            err = parse_error(response.status_code, response.text)
            logger.warning(f"⚠️  嘗試 {attempt}/{max_retries+1} 失敗: {err}")

            if not err.retryable:
                raise err

            retry_delay = random.randint(45, 90)
            logger.info(f"⏳ {retry_delay} 秒後重試...")
            time.sleep(retry_delay)

        except requests.exceptions.Timeout:
            err = NovelAIError(0, "請求逾時", retryable=True)
            logger.warning(f"⚠️  逾時 (嘗試 {attempt}/{max_retries+1})")
            time.sleep(30)
        except requests.exceptions.ConnectionError as e:
            err = NovelAIError(0, f"連線錯誤: {e}", retryable=True)
            logger.warning(f"⚠️  連線失敗 (嘗試 {attempt}/{max_retries+1})")
            time.sleep(20)

        last_err = err

    logger.error(f"❌ 超過最大重試次數 ({max_retries})")
    raise last_err or NovelAIError(0, "超過最大重試次數", retryable=False)


# ── 解析度選擇 ─────────────────────────────────────────
def choose_resolution() -> str:
    print("\n📐 選擇解析度：")
    for k, v in RESOLUTION_PRESETS.items():
        print(f"  {k}. {v['name']}")
    while True:
        choice = input("選擇 (1/2/3/4) [預設 1]: ").strip() or "1"
        if choice in RESOLUTION_PRESETS:
            if choice == "4":
                custom = input("輸入自定義解析度（如 640x960）: ").strip()
                if re.match(r"^\d+x\d+$", custom):
                    return custom
                print("格式錯誤，請輸入如 640x960")
            else:
                return RESOLUTION_PRESETS[choice]["value"]
        print("無效選項")


# ── 測試模式 ────────────────────────────────────────────
def test_connection():
    print("=" * 50)
    print("🔧 NovelAI API 測試模式")
    print("=" * 50)

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"input": "test", "model": "nai-diffusion-3",
               "parameters": {"steps": 5, "resolution": "512x512", "seed": 42}}
    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            print("✅ 金鑰有效！狀態: 200 OK")
            z = zipfile.ZipFile(io.BytesIO(r.content))
            print(f"   ZIP 內含: {z.namelist()}")
        else:
            err = parse_error(r.status_code, r.text)
            print(f"❌ 問題: {err}")
    except Exception as e:
        print(f"❌ 連線失敗: {e}")

    print("\n📐 支援解析度：")
    print("   832x1216（豎向立繪）| 1024x1024（方形）| 1216x832（橫向風景）| 自定義 WxH")
    print("\n📝 用法：")
    print("   python3 novelai_image.py '1girl, solo'")
    print("   python3 novelai_image.py '1girl' -r 1024x1024 -s 28")
    print("   python3 novelai_image.py '1girl' -i /tmp/input.png --strength 0.4")
    print("   python3 novelai_image.py --test")
    print("=" * 50)


# ── CLI ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="NovelAI 圖片生成 v3.1")
    parser.add_argument("prompt", nargs="?", help="英文提示詞")
    parser.add_argument("--resolution", "-r", default="832x1216")
    parser.add_argument("--steps", "-s", type=int, default=28)
    parser.add_argument("--guidance", "-g", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--img2img", "-i", default=None)
    parser.add_argument("--strength", type=float, default=0.3)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--cleanup", action="store_true",
                        help="生成後自動刪除所有 novelai 暫存圖檔")
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    if args.test:
        test_connection()
        return

    if not args.prompt:
        print("🎨 NovelAI 圖片生成器（互動模式）")
        prompt = input("輸入英文提示詞: ").strip()
        if not prompt:
            print("❌ Prompt 不能為空")
            sys.exit(1)
        args.prompt = prompt
        args.resolution = choose_resolution()

    try:
        result = generate(
            prompt=args.prompt,
            resolution=args.resolution,
            steps=args.steps,
            guidance=args.guidance,
            seed=args.seed,
            init_image=args.img2img,
            init_image_strength=args.strength,
            max_retries=args.max_retries,
            auto_cleanup=args.cleanup,
        )
        if result:
            print(f"\n✅ 完成！圖片位置: {result}")
            if not args.cleanup:
                print("🗑️ 如需手動清理，請說：清理 novelai 暫存")
        else:
            print("\n❌ 生成失敗")
            sys.exit(1)
    except NovelAIError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("⚠️ 使用者中斷")
        sys.exit(130)


if __name__ == "__main__":
    main()
