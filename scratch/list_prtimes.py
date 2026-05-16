import feedparser
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

url = "https://prtimes.jp/index.rdf"
feed = feedparser.parse(url)

for i, entry in enumerate(feed.entries[:20]):
    print(f"{i}: {entry.title}")
