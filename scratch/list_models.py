from google import genai
import os
from dotenv import load_dotenv

# config/.env からロード
env_path = "config/.env"
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("GEMINI_API_KEY が設定されていません。")
else:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        # 利用可能なモデルをリストアップ
        print("利用可能なモデル一覧:")
        for model in client.models.list():
            print(f"- {model.name} (Supported: {model.supported_actions})")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
