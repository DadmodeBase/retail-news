import base64
import re

def resolve_url(gn_url):
    try:
        match = re.search(r'articles/(.*?)\?', gn_url)
        if not match:
            match = re.search(r'articles/(.*)', gn_url)
        if not match: return gn_url
        encoded_str = match.group(1)
        encoded_str += "=" * (-len(encoded_str) % 4)
        decoded_bytes = base64.urlsafe_b64decode(encoded_str)
        decoded_text = decoded_bytes.decode('utf-8', errors='ignore')
        urls = re.findall(r'https?://[^\s\x00-\x1f\x7f-\xff"\'<>]+', decoded_text)
        if urls:
            return urls[0]
    except: pass
    return gn_url

url = "https://news.google.com/rss/articles/CBMiakFVX3lxTFBubXFCZERxMzNBeFBJNU95MU9tOFVMMzlickdlNXFUYmJlYURVaEI1MWgtOXJWcEhnWUF4dkhDQkZTWU5uS21RYnF6MTlCSDZFZ1E3VzB1ODk0Q05oUWNJUEh3dnJtU21VZ3c?oc=5"
print(f"Resolved: {resolve_url(url)}")
