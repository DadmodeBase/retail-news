import os
import re
import datetime

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
MAPPING_PATH = os.path.join(PROJECT_ROOT, "content", "docs", "retail_url_mapping.md")
PUBLISHED_DIR = os.path.join(PROJECT_ROOT, "content", "posts", "published")
JST = datetime.timezone(datetime.timedelta(hours=9))

def migrate():
    if not os.path.exists(MAPPING_PATH):
        print(f"エラー: マッピングファイルが見つかりません: {MAPPING_PATH}")
        return

    # マッピングファイルの読み込み
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    new_lines = []
    changes = 0

    for line in lines:
        # | `note_imported_n376680b0c63f.md` | ... | のような行を判定
        match = re.search(r"\|\s*`(note_imported_[^`]+)`", line)
        if match:
            old_filename = match.group(1)
            old_filepath = os.path.join(PUBLISHED_DIR, old_filename)
            
            if os.path.exists(old_filepath):
                # mtime から日付を取得
                mtime = os.path.getmtime(old_filepath)
                dt_jst = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).astimezone(JST)
                date_prefix = dt_jst.strftime("%Y-%m-%d")
                
                new_filename = f"{date_prefix}-{old_filename}"
                new_filepath = os.path.join(PUBLISHED_DIR, new_filename)
                
                # リネーム
                try:
                    os.rename(old_filepath, new_filepath)
                    print(f"リネーム成功: {old_filename} -> {new_filename}")
                except Exception as e:
                    print(f"エラー: {old_filename} のリネームに失敗しました: {e}")
                    new_lines.append(line)
                    continue

                # 行のファイル名部分を置換
                new_line = line.replace(f"`{old_filename}`", f"`{new_filename}`")
                new_lines.append(new_line)
                changes += 1
            else:
                # すでにファイルが存在しない、あるいは別の場所にリネーム済み
                print(f"警告: 実ファイルが見つかりません: {old_filename}")
                new_lines.append(line)
        else:
            new_lines.append(line)

    if changes > 0:
        # マッピングファイルを書き換えて保存
        with open(MAPPING_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        print(f"\n移行完了: {changes} 件のファイルをリネームし、マッピングファイルを更新しました。")
    else:
        print("\n移行対象のファイルはありませんでした。")

if __name__ == "__main__":
    migrate()
