import requests
import re
from urllib.parse import urlparse

def resolve_google_news_url(gn_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # Googleニュースの転送ページを取得
        response = requests.get(gn_url, headers=headers, timeout=10)
        # noscriptタグ内のリダイレクト先URLを探す
        match = re.search(r'content="0;url=(.*?)"', response.text)
        if match:
            return match.group(1)
        # 見つからない場合は meta og:url などを探す
        match = re.search(r'property="og:url" content="(.*?)"', response.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Resolve error: {e}")
    return gn_url

url = "https://news.google.com/rss/articles/CBMiakFVX3lxTE9mSG1yVDhBanJOQ01icDJJOUxNQXlaa3hpa0Fwa3lCdFFWSVdsazN2Tkx1cWFpcmtVY3V0UENldXNGMzNxYWlxMGVfbndZX05WLTZuODlCS2E1bnd3bl9pUEVJcUlhWExxQkE?oc=5"
print(f"Resolved URL: {resolve_google_news_url(url)}")
