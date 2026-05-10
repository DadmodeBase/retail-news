import sys
import os

sys.path.append(r"C:\Users\admin\Documents\Antigravity\note\scripts")
import neta_gatherer

print("テスト生成を開始します...")
articles = neta_gatherer.fetch_latest_news()
outputs = neta_gatherer.generate_contents(articles)

output_path = r"C:\Users\admin\Documents\Antigravity\note\ideas\test_api_output.md"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(outputs['daily_report'])

print(f"生成完了: {output_path}")
