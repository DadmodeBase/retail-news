import feedparser
import datetime

rss_url = "https://note.com/cool_hyena6987/rss"
feed = feedparser.parse(rss_url)

print(f"フィードタイトル: {feed.feed.get('title')}")
print(f"記事数: {len(feed.entries)}")

for i, entry in enumerate(feed.entries):
    published = entry.get('published_parsed') or entry.get('updated_parsed')
    dt_jst = "不明"
    if published:
        dt_utc = datetime.datetime(*published[:6], tzinfo=datetime.timezone.utc)
        dt_jst = dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
    
    print(f"\n[{i+1}] {entry.title}")
    print(f"  URL: {entry.link}")
    print(f"  公開日時: {dt_jst}")
