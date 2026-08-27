"""
login_note_local.py
ローカルでnoteにログインし、セッションCookieを保存・エクスポートするスクリプト。

使用方法:
  python skills/neta_gatherer/login_note_local.py

ブラウザ（Chromium）が立ち上がるので、noteにログインしてください。
ログインが完了すると、自動的にCookieが config/note_cookies.json に保存され、
GitHub Secrets用の設定値が出力されます。
"""

import os
import json
import time
from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
os.makedirs(CONFIG_DIR, exist_ok=True)
COOKIE_PATH = os.path.join(CONFIG_DIR, "note_cookies.json")

def main():
    print("=" * 60)
    print("【note ログイン & Cookie エクスポートツール】")
    print("=" * 60)
    print("ブラウザを起動します。noteにログインしてください...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # noteのログインページへアクセス
        page.goto("https://note.com/login")
        
        print("\n" + "=" * 60)
        print("【操作手順】")
        print("1. 立ち上がったブラウザで note にログインしてください。")
        print("2. ログインが完了したら、このターミナルに戻り [Enter] キーを押してください。")
        print("=" * 60 + "\n")
        
        try:
            # ユーザーのEnterキー入力を待機
            input(">>> ログインが完了したら、ここにフォーカスして [Enter] キーを押してください: ")
        except (KeyboardInterrupt, EOFError):
            pass
            
        print("\n✅ Cookieを取得・保存しています...")
        # 確実にnoteドメインのクッキーをすべて取得
        cookies = context.cookies()
        
        if cookies:
            with open(COOKIE_PATH, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            print(f"📁 Cookieを保存しました: {COOKIE_PATH}")
            
            # GitHub Secrets 用の1行JSON文字列を出力
            compact_json = json.dumps(cookies, ensure_ascii=False)
            print("\n" + "=" * 60)
            print("【GitHub Actions 用の設定（Secrets）】")
            print("GitHub リポジトリの Settings > Secrets and variables > Actions にて、")
            print("以下の Secret を登録してください:")
            print("-" * 60)
            print("Secret Name: NOTE_SESSION_COOKIES")
            print("Secret Value (下記をそのままコピーして貼り付け):")
            print(compact_json)
            print("=" * 60 + "\n")
        else:
            print("\n❌ Cookieが取得できませんでした。")
            
        browser.close()

if __name__ == "__main__":
    main()
