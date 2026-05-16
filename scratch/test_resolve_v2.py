import requests
import re

def resolve_url(gn_url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        r = requests.get(gn_url, headers=headers, timeout=10)
        match = re.search(r'data-n-au="([^"]+)"', r.text)
        if match:
            return match.group(1)
        match = re.search(r'url=(https?://[^\s"\'<>]+)', r.text)
        if match:
            url = match.group(1).split('"')[0].split("'")[0]
            if "google.com" not in url:
                return url
    except Exception as e:
        return str(e)
    return "Failed to resolve"

url = "https://news.google.com/rss/articles/CBMiakFVX3lxTFBubXFCZERxMzNBeFBJNU95MU9tOFVMMzlickdlNXFUYmJlYURVaEI1MWgtOXJWcEhnWUF4dkhDQkZTWU5uS21RYnF6MTlCSDZFZ1E3VzB1ODk0Q05oUWNJUEh3dnJtU21VZ3c?oc=5"
print(f"Resolved: {resolve_url(url)}")
