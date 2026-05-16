import feedparser
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

url = "https://prtimes.jp/index.rdf"
feed = feedparser.parse(url)

print(f"Total entries: {len(feed.entries)}")
for i, entry in enumerate(feed.entries[:100]):
    text = (entry.title + entry.get("summary", "")).lower()
    if "リテール" in text or "dx" in text:
        print(f"Match found: {entry.title} - {entry.link}")

print("Check finished")
