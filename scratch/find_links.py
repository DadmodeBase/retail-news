import re

with open('scratch/gn_page.html', 'r', encoding='utf-8') as f:
    content = f.read()
    # Find all links that look like prtimes
    links = re.findall(r'https://prtimes\.jp/[^\s"\'<>]*', content)
    for link in links:
        print(link)
