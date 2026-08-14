"""
note_publisher.py
Playwrightを使用してnoteに記事を自動投稿（または下書き保存）するモジュール。
"""

import os
import json
import time
import re
from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
COOKIE_PATH = os.path.join(CONFIG_DIR, "note_cookies.json")

def load_cookies():
    """Cookieを読み込む（環境変数 NOTE_SESSION_COOKIES 優先、なければ note_cookies.json）"""
    env_cookies = os.getenv("NOTE_SESSION_COOKIES")
    if env_cookies:
        try:
            return json.loads(env_cookies)
        except Exception as e:
            print(f"[警告] 環境変数 NOTE_SESSION_COOKIES のパースに失敗しました: {e}")
            
    if os.path.exists(COOKIE_PATH):
        try:
            with open(COOKIE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[警告] Cookieファイルの読み込みに失敗しました: {e}")
            
    return None

def publish_to_note(
    title: str,
    body_text: str,
    header_image_path: str = None,
    tags: list = None,
    publish: bool = True,
    headless: bool = True
) -> dict:
    """
    noteに記事を自動投稿する
    
    Args:
        title: 記事タイトル
        body_text: 記事本文（Markdown形式またはプレーンテキスト）
        header_image_path: 見出し画像（ヘッダー画像）のローカルパス
        tags: ハッシュタグリスト（例: ["リテール", "小売", "VMD"]）
        publish: Trueなら即時公開、Falseなら下書き保存
        headless: ヘッドレスモードで実行するかどうか
        
    Returns:
        {"success": bool, "url": str, "status": str, "message": str}
    """
    cookies = load_cookies()
    if not cookies:
        return {
            "success": False,
            "url": "",
            "status": "error",
            "message": "noteのセッションCookieが見つかりません。先に login_note_local.py を実行してログインするか、NOTE_SESSION_COOKIESを設定してください。"
        }

    print(f"[{'公開' if publish else '下書き'}] noteへの自動投稿を開始します: {title}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_cookies(cookies)
        page = context.new_page()
        
        try:
            # 1. noteのエディタページへアクセス
            print("1. エディタページを開いています...")
            page.goto("https://editor.note.com/notes/new", wait_until="networkidle", timeout=60000)
            
            # ログイン状態の確認（ログインページにリダイレクトされた場合はセッション切れ）
            if "/login" in page.url:
                browser.close()
                return {
                    "success": False,
                    "url": "",
                    "status": "auth_error",
                    "message": "セッションCookieの有効期限が切れています。再度 login_note_local.py でログインしてください。"
                }

            # 2. タイトルの入力
            print("2. タイトルを入力しています...")
            title_selector = 'textarea[placeholder*="タイトル"], [data-placeholder*="タイトル"], textarea.o-noteEditorHeader__title'
            page.wait_for_selector(title_selector, timeout=30000)
            title_elem = page.locator(title_selector).first
            title_elem.fill(title)
            time.sleep(1)

            # 3. ヘッダー画像（見出し画像）のアップロード
            if header_image_path and os.path.exists(header_image_path):
                print(f"3. ヘッダー画像をアップロードしています: {header_image_path}")
                try:
                    # ファイル選択用の input を探す
                    file_input = page.locator('input[type="file"]').first
                    if file_input.count() > 0:
                        file_input.set_input_files(header_image_path)
                        time.sleep(3)  # アップロード完了待機
                except Exception as e:
                    print(f"   [注意] ヘッダー画像のアップロードをスキップしました: {e}")

            # 4. 本文の入力
            print("4. 本文を入力しています...")
            # エディタの本文エリアにフォーカス
            body_selector = '[data-editor-type="body"], [data-placeholder*="記事"], div.ProseMirror, .o-noteEditorBody'
            body_elem = page.locator(body_selector).first
            body_elem.click()
            time.sleep(1)
            
            # クリップボード経由でMarkdownテキストをペースト
            # ブラウザのクリップボードAPIまたはProseMirrorへの流し込み
            page.evaluate(
                """({ text }) => {
                    const dt = new DataTransfer();
                    dt.setData('text/plain', text);
                    const pasteEvent = new ClipboardEvent('paste', {
                        bubbles: true,
                        cancelable: true,
                        clipboardData: dt
                    });
                    document.activeElement.dispatchEvent(pasteEvent);
                }""",
                {"text": body_text}
            )
            time.sleep(3)

            # 5. 公開または下書き保存
            if publish:
                print("5. 公開設定に進んでいます...")
                publish_btn = page.locator('button:has-text("公開に進む"), button:has-text("公開設定")').first
                publish_btn.wait_for(state="visible", timeout=15000)
                publish_btn.click()
                time.sleep(2)

                # ハッシュタグの設定
                if tags:
                    print(f"6. ハッシュタグを設定しています: {tags}")
                    try:
                        tag_input = page.locator('input[placeholder*="タグ"], input[placeholder*="#"]').first
                        if tag_input.count() > 0:
                            for tag in tags:
                                clean_tag = tag.lstrip("#")
                                tag_input.fill(clean_tag)
                                page.keyboard.press("Enter")
                                time.sleep(0.5)
                    except Exception as e:
                        print(f"   [注意] タグ設定で例外が発生しました: {e}")

                # 最終「投稿する」ボタン
                print("7. 記事を投稿（公開）しています...")
                submit_btn = page.locator('button:has-text("投稿する"), button:has-text("公開する")').first
                submit_btn.wait_for(state="visible", timeout=15000)
                submit_btn.click()
                
                # 投稿完了後のURL遷移を待機（https://note.com/<user>/n/<note_id>）
                page.wait_for_url(lambda u: "/n/n" in u or "/notes/" not in u, timeout=30000)
                published_url = page.url
                print(f"✅ 公開が完了しました: {published_url}")
                
                browser.close()
                return {
                    "success": True,
                    "url": published_url,
                    "status": "published",
                    "message": f"記事が正常に公開されました: {published_url}"
                }
            else:
                print("5. 下書き保存を実行しています...")
                # noteは自動保存されるが、明示的な下書き保存ボタンがあれば押す
                save_btn = page.locator('button:has-text("下書き保存"), button:has-text("保存")').first
                if save_btn.count() > 0 and save_btn.is_visible():
                    save_btn.click()
                    time.sleep(2)
                    
                draft_url = page.url
                print(f"✅ 下書き保存が完了しました: {draft_url}")
                browser.close()
                return {
                    "success": True,
                    "url": draft_url,
                    "status": "draft",
                    "message": f"下書きが保存されました: {draft_url}"
                }

        except Exception as e:
            # エラー時のスクリーンショット保存（デバッグ用）
            screenshot_path = os.path.join(PROJECT_ROOT, "logs", f"note_publish_error_{int(time.time())}.png")
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            try:
                page.screenshot(path=screenshot_path)
                print(f"📸 エラー画面のスクリーンショットを保存しました: {screenshot_path}")
            except Exception:
                pass
                
            browser.close()
            return {
                "success": False,
                "url": "",
                "status": "error",
                "message": f"note投稿中にエラーが発生しました: {e}"
            }

if __name__ == "__main__":
    # 単体テスト実行用
    test_title = "【テスト投稿】リテール自動化システムの検証記事"
    test_body = "これは自動投稿システムのテスト記事です。\n\n## 概要\nテスト本文が正常にレンダリングされているか確認します。"
    result = publish_to_note(test_title, test_body, publish=False, headless=False)
    print("テスト結果:", result)
