"""
news_fetcher.py
RSSフィードからニュースを収集し、除外ルール（イベント・PR・新規出店）を適用するモジュール。
"""

import datetime
import unicodedata

import feedparser
import requests
import urllib3

import config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _norm(text):
    """全角/半角・大文字/小文字の揺れを吸収した比較用文字列"""
    return unicodedata.normalize("NFKC", text or "").upper()


def _contains_any(text, words):
    return any(_norm(w) in text for w in words)


# ---------------------------------------------------------------------------
# 除外判定
# ---------------------------------------------------------------------------
def is_store_opening(title, link=""):
    """新規出店・オープン系のニュースかどうか（タイトルとURLで判定）"""
    link_l = (link or "").lower()
    if "ryutsuu.biz/store/" in link_l:
        return True

    t = _norm(title)
    # 「オープンイノベーション」等は先に取り除いてから判定する
    for w in config.STORE_OPENING_IGNORE:
        t = t.replace(_norm(w), "")

    if _contains_any(t, config.STORE_OPENING_WORDS):
        return True
    if _contains_any(t, config.STORE_CONTEXT_OPENING_WORDS) and _contains_any(t, config.STORE_CONTEXT_WORDS):
        return True
    return False


def exclusion_reason(entry):
    """除外理由を返す（除外しない場合は None）"""
    title = entry.get("title", "")
    link = entry.get("link", "")
    text = _norm(title + " " + entry.get("summary", ""))

    if is_store_opening(title, link):
        return "新規出店"
    if any(p in link.lower() for p in config.EXCLUDE_URL_PATTERNS):
        return "URL除外"
    if _contains_any(text, config.EXCLUDE_KEYWORDS):
        return "イベント/PR"
    return None


def _matches_prtimes(entry):
    text = _norm(entry.get("title", "") + " " + entry.get("summary", ""))
    return _contains_any(text, config.PRTIMES_KEYWORDS)


# ---------------------------------------------------------------------------
# 取得
# ---------------------------------------------------------------------------
def _parse_feed(url):
    """SSLエラーやUAブロックを回避してフィードを取得・パースする"""
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, verify=False, timeout=15)
        if resp.status_code == 200:
            return feedparser.parse(resp.content)
    except Exception:
        pass
    return feedparser.parse(url)


def _entry_date_jst(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return None
    try:
        return datetime.datetime(*t[:6], tzinfo=datetime.timezone.utc).astimezone(config.JST).date()
    except Exception:
        return None


def _collect(feeds, days, history, now_jst, ignore_dates=False, stats=None):
    target_dates = {(now_jst - datetime.timedelta(days=i)).date() for i in range(0, days + 1)}
    seen = set(history)
    articles = []

    for url in feeds:
        try:
            feed = _parse_feed(url)
            is_prtimes = "prtimes.jp" in url
            count = 0
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                if not title or title in seen:
                    continue

                reason = exclusion_reason(entry)
                if reason:
                    if stats is not None:
                        stats.setdefault(reason, []).append(title)
                    continue
                if is_prtimes and not _matches_prtimes(entry):
                    continue
                if not ignore_dates and _entry_date_jst(entry) not in target_dates:
                    continue

                articles.append({
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                })
                seen.add(title)
                count += 1
                if count >= config.MAX_ARTICLES_PER_FEED:
                    break
        except Exception as e:
            print(f"[警告] {url} の取得に失敗しました: {e}")
    return articles


def fetch_latest_news(feeds, target_days, history, now_jst):
    """ニュースを収集する。0件のときは段階的に範囲を広げて再探索する。"""
    print(f"ニュースを収集しています（当日を含む直近{target_days}日間）...")
    stats = {}
    all_feeds = list(dict.fromkeys(feeds + config.ALL_FALLBACK_FEEDS))

    attempts = [
        ("メインフィード", feeds, target_days, False),
        ("予備フィード追加", all_feeds, target_days, False),
        ("期間を拡張", all_feeds, target_days + 2, False),
        ("日付不問", all_feeds, target_days, True),
    ]
    articles = []
    for i, (label, fds, days, ignore_dates) in enumerate(attempts):
        if i > 0:
            print(f"[フォールバック {i}] {label}で再探索します...")
        articles = _collect(fds, days, history, now_jst, ignore_dates, stats)
        if articles:
            break

    for reason, titles in stats.items():
        uniq = list(dict.fromkeys(titles))
        print(f"  除外（{reason}）: {len(uniq)}件")
        if reason == "新規出店":
            for t in uniq[:10]:
                print(f"    - {t}")

    print(f"新規記事を {len(articles)} 件取得しました。")
    return articles
