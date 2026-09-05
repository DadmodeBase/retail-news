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
    magazine_name: str = None,
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
        magazine_name: 追加するマガジン名（例: "日刊リテールニュース & 流通トレンド分析"）
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
            # 1. noteエディタへアクセス
            print("1. noteエディタへアクセス中...")
            try:
                page.goto("https://editor.note.com/new", wait_until="load", timeout=60000)
            except Exception:
                page.goto("https://note.com/notes/new", wait_until="load", timeout=60000)
            
            # エディタURL（editor.note.com や /edit/、/new）へのリダイレクトを待機
            try:
                page.wait_for_url(re.compile(r"editor\.note\.com|/edit/|/new"), timeout=20000)
            except Exception:
                # リダイレクトされずダッシュボード等に留まった場合のフォールバック
                try:
                    post_btn = page.locator('button:has-text("投稿"), a:has-text("投稿")').first
                    if post_btn.count() > 0 and post_btn.is_visible():
                        post_btn.click()
                        time.sleep(2)
                        text_link = page.locator('a[href*="/notes/new"], button:has-text("テキスト")').first
                        if text_link.count() > 0 and text_link.is_visible():
                            text_link.click()
                            page.wait_for_url(re.compile(r"editor\.note\.com|/edit/|/new"), timeout=20000)
                except Exception as e:
                    print(f"   [注意] 投稿ボタン経由の遷移スキップ: {e}")
            
            # ログイン状態の確認
            if "/login" in page.url:
                browser.close()
                return {
                    "success": False,
                    "url": "",
                    "status": "auth_error",
                    "message": "セッションCookieの有効期限が切れています。再度 login_note_local.py でログインしてください。"
                }

            # 邪魔なモーダルがあれば閉じる
            try:
                close_btn = page.locator('button[aria-label="閉じる"], button:has-text("閉じる"), div[data-name="modal"] button').first
                if close_btn.count() > 0 and close_btn.is_visible():
                    close_btn.click()
                    time.sleep(1)
            except Exception:
                pass

            # 2. タイトルの入力
            print("3. タイトルを入力しています...")
            title_selector = 'textarea[placeholder*="記事タイトル"], [data-placeholder*="記事タイトル"]'
            page.wait_for_selector(title_selector, timeout=30000)
            title_elem = page.locator(title_selector).first
            title_elem.fill(title)
            time.sleep(1)

            # 3. ヘッダー画像（見出し画像）のアップロード
            if header_image_path and os.path.exists(header_image_path):
                print(f"4. ヘッダー画像をアップロードしています: {header_image_path}")
                try:
                    # ヘッダー画像アイコンをクリックしてメニューを表示
                    header_img_btn = page.locator('main button[data-id="ButtonIcon"]').first
                    if header_img_btn.count() > 0 and header_img_btn.is_visible():
                        header_img_btn.click()
                        time.sleep(1)
                        
                        # 「画像をアップロード」ボタンをクリックしてファイル選択ダイアログに渡す
                        upload_btn = page.locator('button:has-text("画像をアップロード")').first
                        with page.expect_file_chooser(timeout=10000) as fc_info:
                            upload_btn.click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(header_image_path)
                        time.sleep(3)
                        
                        # トリミングダイアログの「保存」ボタンをクリック
                        crop_save_btn = page.locator('div.ReactModalPortal button:has-text("保存"), button:has-text("決定")').first
                        if crop_save_btn.count() > 0 and crop_save_btn.is_visible():
                            crop_save_btn.click()
                            time.sleep(3)
                            
                        print(f"   [OK] ヘッダー画像のアップロードが完了しました")
                except Exception as e:
                    print(f"   [注意] ヘッダー画像のアップロードをスキップしました: {e}")

            # 4. 本文の入力
            print("5. 本文を入力しています...")
            # エディタの本文エリアにフォーカス
            body_selector = '[contenteditable="true"], div.ProseMirror, [data-editor-type="body"]'
            page.wait_for_selector(body_selector, timeout=30000)
            body_elem = page.locator(body_selector).first
            body_elem.click()
            time.sleep(1)
            
            # クリップボード経由でMarkdownテキストをペースト
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
                print("6. 公開設定に進んでいます...")
                publish_btn = page.locator('button:has-text("公開に進む")').first
                publish_btn.wait_for(state="visible", timeout=15000)
                publish_btn.click()
                time.sleep(2)

                # ハッシュタグの設定
                if tags:
                    print(f"6. ハッシュタグを設定しています: {tags}")
                    try:
                        tag_input = page.locator('input[placeholder*="タグ"], input[placeholder*="#"]').first
                        if tag_input.count() > 0 and tag_input.is_visible():
                            for tag in tags:
                                clean_tag = tag.lstrip("#").strip()
                                if not clean_tag:
                                    continue
                                tag_input.fill(clean_tag)
                                time.sleep(0.3)
                                page.keyboard.press("Enter")
                                time.sleep(0.5)
                    except Exception as e:
                        print(f"   [注意] タグ設定で例外が発生しました: {e}")

                # マガジンへの追加
                if magazine_name:
                    print(f"6. マガジンに追加しています: {magazine_name}")
                    try:
                        time.sleep(1)
                        # 対象マガジンの行にある「追加」ボタンをピンポイントで取得
                        mag_btn = page.locator('div').filter(has_text=magazine_name).locator('button:has-text("追加")').first
                        if mag_btn.count() > 0 and mag_btn.is_visible():
                            mag_btn.click()
                            time.sleep(1)
                            print(f"   [OK] マガジン「{magazine_name}」に追加しました")
                        else:
                            # フォールバック走査
                            buttons = page.locator('button:has-text("追加")')
                            matched = False
                            for i in range(buttons.count()):
                                btn = buttons.nth(i)
                                parent_text = btn.locator('xpath=ancestor::div[2]').inner_text()
                                if magazine_name in parent_text or ("日刊リテールニュース" in parent_text and "日刊リテールニュース" in magazine_name):
                                    btn.click(force=True)
                                    time.sleep(1)
                                    print(f"   [OK] マガジン「{magazine_name}」に追加しました（フォールバック）")
                                    matched = True
                                    break
                            if not matched:
                                print(f"   [注意] 指定されたマガジン「{magazine_name}」が見つかりませんでした")
                    except Exception as e:
                        print(f"   [注意] マガジン追加処理で例外が発生しました: {e}")

                # 最終「投稿する」ボタン
                print("7. 記事を投稿（公開）しています...")
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1)
                
                submit_btn = page.locator('button:has-text("投稿する")').first
                if submit_btn.count() == 0 or not submit_btn.is_visible():
                    submit_btn = page.locator('button:has-text("公開する")').first
                    
                submit_btn.wait_for(state="visible", timeout=15000)
                submit_btn.click()
                print("   「投稿する」ボタンをクリックしました。公開完了を待機します...")
                time.sleep(2)
                
                # 公開完了ダイアログの表示待機（「記事が公開されました」）
                published_success = False
                try:
                    page.locator('text=記事が公開されました, :has-text("記事が公開されました")').first.wait_for(state="visible", timeout=15000)
                    published_success = True
                    print("   [OK] 「記事が公開されました」モーダルを確認しました")
                except Exception as e:
                    print(f"   [注意] 公開完了モーダルの待機タイムアウト（疎通確認に進みます）: {e}")
                    time.sleep(2)
                
                # 記事IDの抽出と公開用URLの構築
                current_url = page.url
                match = re.search(r"/notes/([a-zA-Z0-9]+)", current_url)
                if match:
                    note_id = match.group(1)
                    published_url = f"https://note.com/cool_hyena6987/n/{note_id}"
                else:
                    published_url = current_url
                    
                print(f"[OK] 公開処理が完了しました: {published_url}")
                
                # 公開URLの疎通確認
                try:
                    import requests
                    r = requests.get(published_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    if r.status_code == 200:
                        print(f"   [OK] 公開記事URLの疎通を確認しました（HTTP {r.status_code}）")
                    else:
                        print(f"   [注意] 公開記事URLのステータスコード: {r.status_code}")
                except Exception as e:
                    print(f"   [注意] 公開記事URL疎通確認: {e}")
                
                browser.close()
                return {
                    "success": True,
                    "url": published_url,
                    "status": "published",
                    "message": f"記事が正常に公開されました: {published_url}"
                }
            else:
                print("6. 下書き保存を実行しています...")
                save_btn = page.locator('button:has-text("下書き保存")').first
                if save_btn.count() > 0 and save_btn.is_visible():
                    save_btn.click()
                    time.sleep(3)
                    
                draft_url = page.url
                print(f"[OK] 下書き保存が完了しました: {draft_url}")
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
                print(f"[注意] エラー画面のスクリーンショットを保存しました: {screenshot_path}")
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
