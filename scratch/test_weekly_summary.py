"""日曜日の週間まとめ生成をシミュレーションするテスト
（実際のメール送信はスキップし、レポート生成までをテスト）
"""
import sys, os, datetime, json, re
sys.stdout.reconfigure(encoding='utf-8')

# プロジェクトルートの設定
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "skills", "neta_gatherer"))

JST = datetime.timezone(datetime.timedelta(hours=9))
TARGET_DIR = os.path.join(PROJECT_ROOT, "content", "reports")

# 明日（日曜 5/31）をシミュレーション
now_jst = datetime.datetime(2026, 5, 31, 5, 0, 0, tzinfo=JST)
print(f"シミュレーション日時: {now_jst.strftime('%Y-%m-%d %H:%M (%A)')}")
print(f"weekday: {now_jst.weekday()} (6=Sun)")
print()

# Step 1: 過去レポートの検索
print("=== Step 1: 過去1週間のレポートを検索 ===")
reports = []
for i in range(1, 8):
    target_date = (now_jst - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
    path = os.path.join(TARGET_DIR, f"{target_date}-daily-report.md")
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    status = f"✅ ({size:,} bytes)" if exists else "❌ なし"
    print(f"  {target_date}: {status}")
    if exists:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            reports.append(f"--- {target_date} ---\n" + content)

print(f"\n見つかったレポート数: {len(reports)} 件")

if not reports:
    print("\n❌ 過去のレポートが見つからないため、まとめを作成できません。")
    sys.exit(1)

# Step 2: Geminiでまとめ生成
print("\n=== Step 2: Geminiで週間まとめを生成 ===")
from dotenv import load_dotenv
env_path = os.path.join(PROJECT_ROOT, "config", ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY が設定されていません")
    sys.exit(1)

from google import genai
from google.genai import types

client = genai.Client(api_key=GEMINI_API_KEY)
context = "\n\n".join(reports)
prompt = f"""
あなたはフィールドマーケティングの専門家です。過去1週間に作成した以下の記事まとめを参照し、
一般消費者を対象として、暮らしの身近な部分に影響が出そうな内容をお知らせ・共有する記事を作成してください。

【過去1週間の記事内容】
{context}

【アウトプット：週間まとめレポート】
- 文字数：2000文字程度
- 内容：暮らしにどのような影響があるか、メリットを中心に分かりやすく解説。
- タイトル：【週間まとめ】暮らしを変えるリテール最新トレンド（{now_jst.strftime('%m/%d')}週）
- 構成：1. 全体俯瞰、2. 注目トピックの深掘り（3〜4つ）、3. まとめ

【文体ルール】
- Markdown記法禁止。プレーンテキスト形式。
- 句点ごとに改行、2〜3文ごとに空行。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "タイトル",
  "daily_report": "レポート全文"
}}
"""

print(f"プロンプト長: {len(prompt):,} 文字")
print("Geminiにリクエスト中...")

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(response_mime_type="application/json"),
)

try:
    data = json.loads(re.search(r'\{.*\}', response.text, re.DOTALL).group())
    if 'article_title' in data and data['article_title'] not in data['daily_report']:
        data['daily_report'] = f"{data['article_title']}\n\n" + data['daily_report']
    
    print(f"\n✅ 生成成功!")
    print(f"タイトル: {data.get('article_title', 'N/A')}")
    report_text = data.get('daily_report', '')
    print(f"文字数: {len(report_text)} 文字")
    print(f"\n--- レポートプレビュー (先頭500文字) ---")
    print(report_text[:500])
    print("...")
    
    # Step 3: X投稿案の生成テスト
    print(f"\n=== Step 3: X投稿案の生成テスト ===")
    # neta_gathererのgenerate_x_postsをインポートして使う
    from neta_gatherer import generate_x_posts
    date_str = now_jst.strftime("%Y-%m-%d")
    x_posts = generate_x_posts(report_text, date_str)
    if x_posts:
        print(f"✅ X投稿案の生成成功! ({len(x_posts)} 文字)")
        print(f"\n--- X投稿案プレビュー (先頭300文字) ---")
        print(x_posts[:300])
        print("...")
    else:
        print("⚠️ X投稿案の生成に失敗しました")
    
    print(f"\n=== 総合判定 ===")
    print(f"✅ 日曜の週間まとめは正常に動作します！")
    
except Exception as e:
    print(f"\n❌ レポート生成に失敗しました: {e}")
    print(f"raw response: {response.text[:300]}")
