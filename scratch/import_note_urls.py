import os
import urllib.request
from bs4 import BeautifulSoup

urls = [
    "https://note.com/cool_hyena6987/n/n376680b0c63f",
    "https://note.com/cool_hyena6987/n/nc7b74c5d3fc6",
    "https://note.com/cool_hyena6987/n/ne306146b023e",
    "https://note.com/cool_hyena6987/n/n59bfacc5ce17",
    "https://note.com/cool_hyena6987/n/n3b1cc1d8f36e",
    "https://note.com/cool_hyena6987/n/n6ecbb281b46f",
    "https://note.com/cool_hyena6987/n/n65b4ddafa6e4",
    "https://note.com/cool_hyena6987/n/n408cf497c134",
    "https://note.com/cool_hyena6987/n/n4da5c4a60b13",
    "https://note.com/cool_hyena6987/n/nd55fce32c238",
    "https://note.com/cool_hyena6987/n/n37496407eb46"
]

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
published_dir = os.path.join(PROJECT_ROOT, "content", "posts", "published")
os.makedirs(published_dir, exist_ok=True)
mapping_path = os.path.join(PROJECT_ROOT, "content", "docs", "retail_url_mapping.md")

with open(mapping_path, "a", encoding="utf-8") as map_file:
    for i, url in enumerate(urls):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.title.string.replace('｜Dad（ダッド）', '').strip() if soup.title else f"Note Article {i}"
                
                # Extract text
                for script in soup(["script", "style"]):
                    script.extract()
                text = soup.get_text(separator=' ')
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                filename = f"note_imported_{url.split('/')[-1]}.md"
                filepath = os.path.join(published_dir, filename)
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(text)
                
                map_file.write(f"| `{filename}` | {title} | {url} |\n")
                print(f"Added: {title}")
        except Exception as e:
            print(f"Failed {url}: {e}")
