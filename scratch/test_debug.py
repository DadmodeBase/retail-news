import sys
import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv("config/.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

dummy_articles = [
    {
        "title": "PPIH／「ロビン・フッド甚目寺店」オープン、総菜に名古屋グルメ・うどんバイキング",
        "link": "https://www.ryutsuu.biz/report/s042441.html",
        "summary": "PPIHが愛知県あま市に「ロビン・フッド甚目寺店」をオープン。"
    },
    {
        "title": "オンワード／SC向けブランド「アンフィーロ」初の単独店、ららぽーと豊洲にオープン",
        "link": "https://www.ryutsuu.biz/report/s042411.html",
        "summary": "オンワード樫山が展開する「アンフィーロ」が初の単独店舗をオープン。"
    },
    {
        "title": "セブン＆アイ／30年までに北米「7NOW」売上高18億ドルへ",
        "link": "https://www.ryutsuu.biz/abroad/s042412.html",
        "summary": "セブン＆アイが北米事業でデリバリーサービス「7NOW」を強化。"
    }
]

context = "\n".join([f"- {a['title']}: {a['link']}" for a in dummy_articles])
prompt = f"""
あなたはフィールドマーケティングの専門家です。以下の最新ニュースから3つのトピックスを選び、デイリーレポートを作成してください。

【トピック選定ルール】
- 収集したニュースの中にドラッグストア・調剤併設・薬局関連（ウエルシア、ツルハ、マツキヨ、スギ薬局、コスモス等の主要チェーンやDgS動向）のニュースが含まれている場合は、3つのトピックのうち少なくとも1つは優先的にドラッグストア関連のニュースを選出してください。

【ニュースソース】
{context}

【アウトプット：デイリーレポート】
1. タイトル（1行目）：トピックで取り上げた企業名を【】で囲んで冒頭に付ける
2. 空行
3. 全体概要：3つのトピックを俯瞰した導入文（150文字〜200文字程度）。
4. 各トピック（3セット）：
    - トピックタイトル（独立した行）
    - 空行
    - ソースURL（そのまま記載。前後に空行）
    - 空行
    - 本文：専門家としての深い解説コラム（各トピック350文字程度。市場背景、フィールドマーケティングへの具体的なインパクト、今後の展望や取るべきアクションを簡潔に凝縮し、300文字〜400文字の範囲で記述してください。無駄な装飾語は排除すること）。

【文体ルール】
- レポート全体の文章量を、1600文字〜1800文字（最大でも絶対に2000文字以内）となるよう厳密に文字数を制御してください。冗長な解説は徹底的に削り、簡潔で情報密度の高い文章に仕上げてください。
- Markdown記法は使わず、プレーンテキスト形式で。
- 句点（。）ごとに改行し、2〜3文ごとに空行。
- リンクはURLをそのまま記載。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "タイトル",
  "daily_report": "レポート全文"
}}
"""

try:
    print("API呼び出し中...")
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    print("=== RAW RESPONSE TEXT ===")
    print(repr(response.text))
    print("=========================")
    
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if not match:
        print("エラー: re.search がマッチしませんでした。")
    else:
        json_str = match.group()
        data = json.loads(json_str)
        print("JSON parse 成功!")
        print("Keys:", data.keys())
except Exception as e:
    import traceback
    print("例外が発生しました:")
    traceback.print_exc()
