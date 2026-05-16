import requests
import re

def resolve_url(gn_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    }
    try:
        r = requests.get(gn_url, headers=headers, timeout=10, allow_redirects=True)
        if "google.com" not in r.url:
            return r.url
        match = re.search(r'url=(https?://[^\s"\'<>]+)', r.text)
        if match:
            url = match.group(1).split('"')[0].split("'")[0]
            if "google.com" not in url:
                return url
    except Exception as e:
        return str(e)
    return gn_url

url = "https://news.google.com/rss/articles/CBMiakFVX3lxTFBubXFCZERxMzNBeFBJNU95MU9tOFVMMzlickdlNXFUYmJlYURVaEI1MWgtOXJWcEhnWUF4dkhDQkZTWU5uS21RYnF6MTlCSDZFZ1E3VzB1ODk0Q05oUWNJUEh3dnJtU21VZ3c?oc=5"
print(f"Resolved: {resolve_url(url)}")
