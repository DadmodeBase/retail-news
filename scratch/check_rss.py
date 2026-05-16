import feedparser
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

url = "https://news.google.com/rss/search?q=site:prtimes.jp+%E3%83%AA%E3%83%86%E3%83%BC%E3%83%ABDX&hl=ja&gl=JP&ceid=JP:ja"
feed = feedparser.parse(url)

if feed.entries:
    entry = feed.entries[0]
    print(f"Title: {entry.title}")
    print(f"Link: {entry.link}")
    # print all keys to see if there is a direct link
    print(f"Keys: {entry.keys()}")
    if 'source' in entry:
        print(f"Source: {entry.source}")
else:
    print("No entries found")
