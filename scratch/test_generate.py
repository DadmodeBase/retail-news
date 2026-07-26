import sys
import os

# neta_gatherer があるディレクトリをシステムパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "skills", "neta_gatherer"))
import neta_gatherer

# ダミーのニュース記事を用意
dummy_articles = [
    {
        "title": "PPIH／「ロビン・フッド甚目寺店」オープン、総菜に名古屋グルメ・うどんバイキング",
        "link": "https://www.ryutsuu.biz/report/s042441.html",
        "summary": "PPIHが愛知県あま市に「ロビン・フッド甚目寺店」をオープン。名古屋グルメを強化し、うどんバイキングも展開。"
    },
    {
        "title": "オンワード／SC向けブランド「アンフィーロ」初の単独店、ららぽーと豊洲にオープン",
        "link": "https://www.ryutsuu.biz/report/s042411.html",
        "summary": "オンワード樫山が展開する「アンフィーロ」が初の単独店舗をららぽーと豊洲にオープン。高機能カジュアルウェアをアピール。"
    },
    {
        "title": "セブン＆アイ／30年までに北米「7NOW」売上高18億ドルへ、PB・レストラン併設に期待",
        "link": "https://www.ryutsuu.biz/abroad/s042412.html",
        "summary": "セブン＆アイが北米事業でデリバリーサービス「7NOW」を強化。レストラン併設店舗などを増やして売上拡大を狙う。"
    }
]

print("=== 新しいプロンプトでレポートを生成中 ===")
outputs = neta_gatherer.generate_contents(dummy_articles)

if outputs and 'daily_report' in outputs:
    report = outputs['daily_report']
    output_txt_path = os.path.join(os.path.dirname(__file__), "test_report_output.txt")
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write(f"--- 生成されたレポート ---\n{report}\n--------------------------\n")
        f.write(f"タイトル: {outputs.get('article_title')}\n")
        f.write(f"レポート全体の文字数: {len(report)} 文字\n")
    print(f"結果を保存しました: {output_txt_path}")
else:
    print("レポートの生成に失敗しました。")
