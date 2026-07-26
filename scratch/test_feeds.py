"""火・土曜のフィード取得をシミュレーションするテスト"""
import feedparser
import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')

JST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(JST)
target_days = 1
target_dates = [(now - datetime.timedelta(days=i)).date() for i in range(0, target_days + 1)]
print(f"対象日: {target_dates}")

KEYWORDS = [
    "リテール", "小売", "店舗", "流通", "EC", "コンビニ", "スーパー",
    "ドラッグストア", "マーケティング", "DX", "OMO", "POS", "決済",
    "買い物", "販促", "棚", "売場", "売り場", "接客", "無人",
    "セルフレジ", "デジタルサイネージ", "フードロス", "食品ロス",
    "ネットスーパー", "物流", "ラストワンマイル", "配送",
]

feeds = [
    ("https://prtimes.jp/index.rdf", True),   # PR TIMES: フィルタあり
    ("https://lnews.jp/feed", False),          # LNEWS: フィルタなし
    ("https://www.ryutsuu.biz/feed", False),   # 流通ニュース: フィルタなし
]

all_articles = []
for url, use_filter in feeds:
    feed = feedparser.parse(url)
    count = 0
    for entry in feed.entries:
        if use_filter:
            text = (entry.title + " " + entry.get("summary", "")).upper()
            if not any(k.upper() in text for k in KEYWORDS):
                continue
        entry_time = entry.get('published_parsed') or entry.get('updated_parsed')
        if entry_time:
            dt_utc = datetime.datetime(*entry_time[:6], tzinfo=datetime.timezone.utc)
            dt_jst = dt_utc.astimezone(JST)
            if dt_jst.date() in target_dates:
                all_articles.append(entry.title)
                count += 1
        if count >= 10:
            break
    source = "PR TIMES(フィルタ)" if use_filter else url.split("/")[2]
    print(f"  {source}: {count}件")

print(f"\n合計: {len(all_articles)}件")
for i, title in enumerate(all_articles[:15], 1):
    print(f"  {i}. {title[:70]}")
