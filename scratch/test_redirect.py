import requests

url = "https://news.google.com/rss/articles/CBMiakFVX3lxTE9mSG1yVDhBanJOQ01icDJJOUxNQXlaa3hpa0Fwa3lCdFFWSVdsazN2Tkx1cWFpcmtVY3V0UENldXNGMzNxYWlxMGVfbndZX05WLTZuODlCS2E1bnd3bl9pUEVJcUlhWExxQkE?oc=5"
try:
    response = requests.get(url, allow_redirects=True, timeout=10)
    print(f"Final URL: {response.url}")
except Exception as e:
    print(f"Error: {e}")
