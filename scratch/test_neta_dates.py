import os
import sys
import datetime

# パス追加
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "skills", "neta_gatherer"))
import neta_gatherer

# JST
JST = neta_gatherer.JST

print("--- 設定の検証 ---")
print(f"現在時刻 (JST): {datetime.datetime.now(JST)}")
print(f"現在日付 (JST): {datetime.datetime.now(JST).date()}")
two_weeks_ago = datetime.datetime.now(JST).date() - datetime.timedelta(days=14)
print(f"直近2週間の基準日 (JST): {two_weeks_ago} 以降")

print("\n--- 登録記事の一覧と日付判定 ---")
note_articles = neta_gatherer.load_note_urls()
print(f"全登録記事数: {len(note_articles)}")

recent_articles = []
for article in note_articles:
    basename = os.path.basename(article["file"])
    art_date = neta_gatherer.get_article_date(article)
    in_range = two_weeks_ago <= art_date <= datetime.datetime.now(JST).date()
    
    # ファイルのmtimeも取得して表示
    mtime = os.path.getmtime(article["file"])
    mtime_dt = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).astimezone(JST)
    
    print(f"ファイル: {basename}")
    print(f"  判定日付 (get_article_date): {art_date}")
    print(f"  実際の mtime (JST): {mtime_dt}")
    print(f"  直近2週間以内か: {in_range}")
    
    if in_range:
        recent_articles.append(article)

print(f"\n直近2週間以内の記事数: {len(recent_articles)}")
if len(recent_articles) < 2:
    print("警告: 過去2週間以内の記事が不足しているため、全期間からフォールバックされます。")
