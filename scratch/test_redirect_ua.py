import requests
import re

url = "https://news.google.com/rss/articles/CBMiakFVX3lxTE9mSG1yVDhBanJOQ01icDJJOUxNQXlaa3hpa0Fwa3lCdFFWSVdsazN2Tkx1cWFpcmtVY3V0UENldXNGMzNxYWlxMGVfbndZX05WLTZuODlCS2E1bnd3bl9pUEVJcUlhWExxQkE?oc=5"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
try:
    response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
    print(f"Final URL: {response.url}")
    # check content for meta refresh
    if "url=" in response.text:
        match = re.search(r'url=(https?://[^\s"\'<>]+)', response.text)
        if match:
            print(f"Meta refresh URL: {match.group(1)}")
except Exception as e:
    print(f"Error: {e}")
