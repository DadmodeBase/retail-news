import re

with open(r'C:\Users\admin\.gemini\antigravity-ide\brain\bc056b8a-2c0c-471b-a983-9aec47629a09\.system_generated\steps\22\content.md', encoding='utf-8') as f:
    text = f.read()

for m in re.finditer(r'スーパー3社比較', text):
    start = max(0, m.start() - 400)
    end = min(len(text), m.end() + 400)
    print("MATCH SNIPPET:")
    print(text[start:end])
