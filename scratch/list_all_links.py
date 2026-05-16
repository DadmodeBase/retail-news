import re

with open('scratch/gn_page.html', 'r', encoding='utf-8') as f:
    content = f.read()
    # Find anything that looks like a URL
    links = re.findall(r'https?://[^\s"\'<>]{10,}', content)
    # Print first 20 links
    for link in links[:20]:
        print(link)
