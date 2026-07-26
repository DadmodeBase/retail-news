import os
import json
import sys
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv("config/.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from skills.neta_gatherer.neta_gatherer import generate_contents

# テスト用のダミー記事データ (3件)
dummy_articles = [
    {
        "title": "ヤオコー、埼玉県新座市に新店舗「ヤオコー新座店」をオープン。最新のデリカ・惣菜売場を導入し、地域密着型の店舗展開を強化。",
        "link": "https://example.com/yaoko-new-store",
        "summary": "ヤオコーは新座市に新店舗をオープンし、デリカ売場などを強化した最新のレイアウトを導入。"
    },
    {
        "title": "ファミリーマート、無人決済店舗「ファミマ!!」を都内オフィスビルに拡大。AIカメラと重量センサーでスピーディな購買体験を実現。",
        "link": "https://example.com/famima-mujin",
        "summary": "ファミリーマートはAIとセンサーを用いた無人決済店舗の拡大を進めている。"
    },
    {
        "title": "イオン、スマートフォン向け公式アプリ「iAEON」のUIを全面刷新。店舗ごとのクーポン配信機能や独自決済「AEON Pay」の利便性を向上。",
        "link": "https://example.com/aeon-app-renewal",
        "summary": "イオンは公式アプリのUIを刷新し、クーポン機能やAEON Payの利便性を強化。"
    }
]

print("最新プロンプトでの生成テストを開始します...")
result = generate_contents(dummy_articles)

if result:
    report_text = result.get("daily_report", "")
    title = result.get("article_title", "")
    print(f"\n--- 生成されたタイトル ---")
    print(title)
    print(f"\n--- 文字数集計 ---")
    print(f"タイトル文字数: {len(title)}")
    print(f"レポート本文文字数: {len(report_text)}")
    print(f"合計文字数: {len(title) + len(report_text)}")
    print(f"\n--- レポート本文の一部抜粋 ---")
    lines = report_text.split("\n")
    for i, line in enumerate(lines[:15]):
        print(line)
    if len(lines) > 15:
        print("...")
else:
    print("レポートの生成に失敗しました。")
