import base64
import re

def decode_google_news_url(url):
    match = re.search(r"articles/(.+?)\?", url)
    if not match:
        return url
    try:
        data = match.group(1)
        # padding
        data += "=" * (-len(data) % 4)
        decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        print(f"Decoded raw: {repr(decoded)}")
        match_url = re.search(r"https?://[^\s\"'<>]+", decoded)
        if match_url:
            return match_url.group(0)
    except Exception as e:
        print(f"Decode error: {e}")
    return url

url = "https://news.google.com/rss/articles/CBMiakFVX3lxTE9mSG1yVDhBanJOQ01icDJJOUxNQXlaa3hpa0Fwa3lCdFFWSVdsazN2Tkx1cWFpcmtVY3V0UENldXNGMzNxYWlxMGVfbndZX05WLTZuODlCS2E1bnd3bl9pUEVJcUlhWExxQkE?oc=5"
print(f"Decoded: {decode_google_news_url(url)}")
