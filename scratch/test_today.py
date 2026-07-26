import feedparser
import datetime
import os
import sys

JST = datetime.timezone(datetime.timedelta(hours=9))

# 今朝5:13時点のnow_jstをシミュレート
simulated_now = datetime.datetime(2026, 7, 23, 5, 13, 0, tzinfo=JST)
target_days = 1
target_dates = [(simulated_now - datetime.timedelta(days=i)).date() for i in range(0, target_days + 1)]

print(f"シミュレート時刻: {simulated_now}")
print(f"対象日付 (target_dates): {target_dates}")

url = "https://www.ryutsuu.biz/feed"
print(f"\nFeed {url} を取得中...")
feed = feedparser.parse(url)
print(f"取得したエントリー数: {len(feed.entries)}")

for i, entry in enumerate(feed.entries[:15]):
    title = entry.title
    published_parsed = entry.get('published_parsed') or entry.get('updated_parsed')
    dt_jst = None
    if published_parsed:
        dt_utc = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
        dt_jst = dt_utc.astimezone(JST)
    
    is_in_target = dt_jst.date() in target_dates if dt_jst else False
    print(f"[{i+1}] {title}")
    print(f"    公開日時 (JST): {dt_jst}")
    print(f"    対象期間内か?: {is_in_target}")
