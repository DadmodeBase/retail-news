import sys
import os
import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "skills", "neta_gatherer"))
import neta_gatherer

JST = neta_gatherer.JST

# 今朝5:13時点を模倣
simulated_now = datetime.datetime(2026, 7, 23, 5, 13, 0, tzinfo=JST)

# 流通ニュースの今朝5:13時点の記事（7/22以前のもの）を全て既読履歴として仮定
mock_history = [
    "サミット／東久留米市に「3店舗目」オープン、生鮮・惣菜・ベーカリー強化",
    "ダイエー／過去最大のデリカ新店、2029年春青葉台オープン",
    "イトーヨーカドー／「湘南台店」7月29日オープン、目標22億円",
    "ピアゴ／愛知県「吉良フードコア」リニューアルオープン、吉良市の商業施設に出店",
]

print("=== フォールバック動作テスト開始 ===")
# ニュース収集（旧構成と同じメインフィード 1つだけで実行）
feeds = ["https://www.ryutsuu.biz/feed"]
target_days = 1

articles = neta_gatherer.fetch_latest_news(
    rss_feeds=feeds,
    target_days=target_days,
    history=mock_history,
    now_jst=simulated_now,
    keywords=None,
    fallback_feeds=neta_gatherer.ALL_FALLBACK_FEEDS
)

print(f"\n取得された記事数: {len(articles)}")
for i, a in enumerate(articles[:5]):
    print(f"[{i+1}] {a['title']} ({a['link']})")

assert len(articles) > 0, "テスト失敗: フォールバック処理で記事が取得できませんでした。"
print("\n=== テスト合格: フォールバック処理が正常に機能しています ===")
