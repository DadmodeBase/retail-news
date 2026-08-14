import datetime
import feedparser
import sys
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json
from dotenv import load_dotenv

load_dotenv("config/.env")

JST = datetime.timezone(datetime.timedelta(hours=9))

DRUGSTORE_GOOGLE_NEWS_FEED = "https://news.google.com/rss/search?q=ドラッグストア+OR+DgS+OR+調剤薬局&hl=ja&gl=JP&ceid=JP:ja"

ALL_FALLBACK_FEEDS = [
    "https://lnews.jp/feed",
    "https://www.ryutsuu.biz/feed",
    "https://diamond-rm.net/feed/",
    DRUGSTORE_GOOGLE_NEWS_FEED,
    "https://prtimes.jp/index.rdf"
]

# 7/29 (水) 朝 05:13 JST のシミュレーション
sim_time_729 = datetime.datetime(2026, 7, 29, 5, 13, 0, tzinfo=JST)

# 7/30 (木) 朝 05:13 JST のシミュレーション
sim_time_730 = datetime.datetime(2026, 7, 30, 5, 13, 0, tzinfo=JST)

def check_sim(now_jst, label):
    print(f"\n==================== {label} ({now_jst}) ====================")
    weekday = now_jst.weekday()
    print(f"曜日: {weekday} (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun)")
    
    if weekday == 0:
        feeds, target_days = ["https://lnews.jp/feed", "https://diamond-rm.net/feed/", "https://www.ryutsuu.biz/feed", DRUGSTORE_GOOGLE_NEWS_FEED], 3
    elif weekday in [2, 3]:
        feeds, target_days = ["https://www.ryutsuu.biz/feed", "https://lnews.jp/feed", "https://diamond-rm.net/feed/", DRUGSTORE_GOOGLE_NEWS_FEED], 1
    elif weekday == 4:
        feeds, target_days = ["https://lnews.jp/feed", "https://diamond-rm.net/feed/", "https://www.ryutsuu.biz/feed", DRUGSTORE_GOOGLE_NEWS_FEED], 1
    elif weekday in [1, 5]:
        feeds, target_days = ["https://prtimes.jp/index.rdf", "https://lnews.jp/feed", "https://www.ryutsuu.biz/feed", "https://diamond-rm.net/feed/", DRUGSTORE_GOOGLE_NEWS_FEED], 1
    else:
        feeds, target_days = ["https://lnews.jp/feed", "https://www.ryutsuu.biz/feed", "https://diamond-rm.net/feed/", DRUGSTORE_GOOGLE_NEWS_FEED], 1

    target_dates = [(now_jst - datetime.timedelta(days=i)).date() for i in range(0, target_days + 1)]
    print(f"ターゲット日付一覧 (target_days={target_days}): {target_dates}")

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            count = 0
            matching_entries = []
            for entry in feed.entries:
                entry_time = entry.get('published_parsed') or entry.get('updated_parsed')
                if entry_time:
                    dt_utc = datetime.datetime(*entry_time[:6], tzinfo=datetime.timezone.utc)
                    dt_jst = dt_utc.astimezone(JST)
                    if dt_jst.date() in target_dates:
                        matching_entries.append((entry.title, dt_jst))
                        count += 1
            print(f"フィード: {url} -> マッチ件数: {count}")
            for t, d in matching_entries[:5]:
                print(f"   [{d.strftime('%Y-%m-%d %H:%M')}] {t[:50]}")
        except Exception as e:
            print(f"エラー ({url}): {e}")

check_sim(sim_time_729, "7/29(水) 朝5:13 シミュレーション")
check_sim(sim_time_730, "7/30(木) 朝5:13 シミュレーション")
