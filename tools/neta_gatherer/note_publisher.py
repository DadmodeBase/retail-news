"""
note_publisher.py
Playwright で note に記事を投稿し、ハッシュタグ・マガジンを設定するモジュール。

設計方針:
  * noteは styled-components のクラス名（sc-xxxx）がデプロイ毎に変わるため、
    クラス名には依存せず「id / placeholder / role / 表示テキスト」で要素を特定する。
  * タグ・マガジンは「設定 → 画面上で確認」を行い、公開後は note の公開APIで
    実際に反映されたかを検証。足りなければ編集画面から再設定（自動修復）する。
"""

import json
import os
import re
import time
import unicodedata

import requests
from playwright.sync_api import sync_playwright

import config

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
_EDITOR_URL_RE = re.compile(r"editor\.note\.com|/edit|/new")
_NOTE_KEY_RE = re.compile(r"/(?:notes|n)/(n[0-9a-z]{6,})")
_TAG_INPUT_SEL = 'input[aria-owns="hashtag-search-result"], input[placeholder*="ハッシュタグ"]'


# ---------------------------------------------------------------------------
# 共通ユーティリティ
# ---------------------------------------------------------------------------
def norm_tag(tag):
    """タグ比較用の正規化（#・記号・全半角・大小文字の揺れを吸収）"""
    t = unicodedata.normalize("NFKC", tag or "").lstrip("#").upper()
    return re.sub(r"[\W_]", "", t)


def load_cookies():
    """環境変数 NOTE_SESSION_COOKIES 優先、なければ config/note_cookies.json"""
    env = os.getenv("NOTE_SESSION_COOKIES")
    if env:
        try:
            return json.loads(env)
        except Exception as e:
            print(f"[警告] NOTE_SESSION_COOKIES のパースに失敗しました: {e}")
    if os.path.exists(config.NOTE_COOKIE_PATH):
        try:
            with open(config.NOTE_COOKIE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[警告] Cookieファイルの読み込みに失敗しました: {e}")
    return None


def _save_debug(page, label):
    """失敗時の画面とDOMを logs/ に保存（GitHub Actions では artifact として回収）"""
    try:
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        base = os.path.join(config.LOGS_DIR, f"note_{label}_{int(time.time())}")
        page.screenshot(path=base + ".png", full_page=True)
        with open(base + ".html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"   [デバッグ] 画面を保存しました: {base}.png")
    except Exception:
        pass


def _extract_key(url):
    m = _NOTE_KEY_RE.search(url or "")
    return m.group(1) if m else ""


def _close_modal(page):
    try:
        btn = page.locator('button[aria-label="閉じる"], button:has-text("閉じる")').first
        if btn.count() > 0 and btn.is_visible():
            btn.click()
            page.wait_for_timeout(800)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# エディタ操作
# ---------------------------------------------------------------------------
def _open_new_editor(page):
    print("1. noteエディタへアクセス中...")
    try:
        page.goto("https://editor.note.com/new", wait_until="load", timeout=60000)
    except Exception:
        page.goto("https://note.com/notes/new", wait_until="load", timeout=60000)
    try:
        page.wait_for_url(_EDITOR_URL_RE, timeout=20000)
    except Exception:
        pass
    if "/login" in page.url:
        raise PermissionError("セッションCookieの有効期限が切れています。login_note_local.py で再ログインしてください。")
    _close_modal(page)


def _fill_title(page, title):
    print("2. タイトルを入力しています...")
    sel = 'textarea[placeholder*="記事タイトル"], [data-placeholder*="記事タイトル"]'
    page.wait_for_selector(sel, timeout=30000)
    page.locator(sel).first.fill(title)
    page.wait_for_timeout(800)


def _upload_header(page, image_path):
    if not image_path or not os.path.exists(image_path):
        return
    print(f"3. ヘッダー画像をアップロードしています: {image_path}")
    try:
        btn = page.locator('main button[data-id="ButtonIcon"]').first
        if btn.count() == 0 or not btn.is_visible():
            print("   [注意] ヘッダー画像ボタンが見つかりません（スキップ）")
            return
        btn.click()
        page.wait_for_timeout(1000)
        with page.expect_file_chooser(timeout=10000) as fc:
            page.locator('button:has-text("画像をアップロード")').first.click()
        fc.value.set_files(image_path)
        page.wait_for_timeout(3000)
        save = page.locator('div.ReactModalPortal button:has-text("保存"), button:has-text("決定")').first
        if save.count() > 0 and save.is_visible():
            save.click()
            page.wait_for_timeout(3000)
        print("   [OK] ヘッダー画像を設定しました")
    except Exception as e:
        print(f"   [注意] ヘッダー画像のアップロードをスキップしました: {e}")


def _paste_body(page, body_text):
    print("4. 本文を入力しています...")
    sel = 'div.ProseMirror, [contenteditable="true"], [data-editor-type="body"]'
    page.wait_for_selector(sel, timeout=30000)
    page.locator(sel).first.click()
    page.wait_for_timeout(800)
    page.evaluate(
        """({ text }) => {
            const dt = new DataTransfer();
            dt.setData('text/plain', text);
            document.activeElement.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true, cancelable: true, clipboardData: dt
            }));
        }""",
        {"text": body_text},
    )
    print("   本文の反映と自動保存を待機しています...")
    page.wait_for_timeout(6000)


def _open_publish_settings(page):
    print("5. 公開設定画面を開いています...")
    btn = page.locator("button").filter(has_text=re.compile(r"(公開|更新)に進む|^\s*公開設定\s*$")).first
    btn.wait_for(state="visible", timeout=20000)
    btn.click()
    page.locator(f"#item-hashtag, {_TAG_INPUT_SEL}").first.wait_for(state="visible", timeout=30000)
    page.wait_for_timeout(1500)
    print("   [OK] 公開設定画面が表示されました")


# ---------------------------------------------------------------------------
# ハッシュタグ
# ---------------------------------------------------------------------------
_JS_REGISTERED_TAGS = """
() => {
  const input = document.querySelector('input[aria-owns="hashtag-search-result"]')
             || document.querySelector('input[placeholder*="ハッシュタグ"]');
  if (!input) return null;
  const list = document.getElementById('hashtag-search-result');
  const pick = (root) => [...root.querySelectorAll('button')]
      .filter(b => !(list && list.contains(b)) && !b.querySelector('img'))
      .map(b => (b.textContent || '').trim())
      .filter(t => /^#\\S+$/.test(t) && t.length <= 40);
  // 入力欄 → ラッパー → タグ一覧を含むコンテナ（2階層上）
  const box = input.parentElement && input.parentElement.parentElement;
  let tags = box ? pick(box) : [];
  if (tags.length === 0) {
    const sec = input.closest('section');
    if (sec) tags = pick(sec);
  }
  return [...new Set(tags)];
}
"""

_JS_CLICK_EXACT_SUGGESTION = """
(tag) => {
  const list = document.getElementById('hashtag-search-result');
  if (!list) return false;
  const clean = s => (s || '').trim().replace(/^#/, '');
  const items = [...list.querySelectorAll('[role="option"], li, button')];
  for (const el of items) {
    // 候補テキスト先頭がタグと完全一致し、その後ろが件数表示などの非文字のみの場合
    const t = clean(el.textContent);
    if (t === tag || new RegExp('^' + tag.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + '[\\\\s\\\\d,.万件]*$').test(t)) {
      el.click();
      return true;
    }
  }
  return false;
}
"""


def _registered_tags(page):
    return page.evaluate(_JS_REGISTERED_TAGS) or []


def _is_registered(page, tag):
    target = norm_tag(tag)
    return any(norm_tag(t) == target for t in _registered_tags(page))


def _type_tag(page, tag):
    inp = page.locator(_TAG_INPUT_SEL).first
    inp.scroll_into_view_if_needed()
    inp.click()
    inp.fill("")
    inp.press_sequentially(tag, delay=40)
    return inp


def _add_tag(page, tag):
    """1つのタグを登録する。サジェスト誤選択を避けるため複数の方法を順に試す。"""
    # 方法1: 入力直後（サジェスト表示前）にEnter
    inp = _type_tag(page, tag)
    inp.press("Enter")
    page.wait_for_timeout(900)
    if _is_registered(page, tag):
        return True

    # 方法2: サジェストの中から完全一致の候補をクリック
    inp = _type_tag(page, tag)
    page.wait_for_timeout(1500)
    if page.evaluate(_JS_CLICK_EXACT_SUGGESTION, tag):
        page.wait_for_timeout(900)
        if _is_registered(page, tag):
            return True

    # 方法3: サジェストを閉じてからEnter
    inp = _type_tag(page, tag)
    page.wait_for_timeout(1500)
    inp.press("Escape")
    page.wait_for_timeout(300)
    if not inp.input_value():
        inp = _type_tag(page, tag)
    inp.press("Enter")
    page.wait_for_timeout(900)
    return _is_registered(page, tag)


def _remove_extra_tag(page, tag_text):
    """note側の自動提案タグを外して枠を空ける（タグ上限対策）"""
    try:
        btn = page.locator("button").filter(has_text=re.compile(rf"^{re.escape(tag_text)}$")).first
        btn.click()
        page.wait_for_timeout(700)
        return tag_text not in _registered_tags(page)
    except Exception:
        return False


def apply_tags(page, tags):
    """タグを設定し、未登録のまま残ったタグのリストを返す"""
    print(f"6. ハッシュタグを設定しています: {tags}")
    try:
        menu = page.locator("#item-hashtag").first
        if menu.count() > 0:
            menu.click()
            page.wait_for_timeout(800)
        page.locator(_TAG_INPUT_SEL).first.wait_for(state="visible", timeout=15000)
    except Exception as e:
        print(f"   [NG] ハッシュタグ入力欄が見つかりません: {e}")
        return list(tags)

    wanted = {norm_tag(t) for t in tags}
    before = _registered_tags(page)
    if before:
        print(f"   既に登録されているタグ: {before}")

    for tag in tags:
        tag = tag.lstrip("#").strip()
        if not tag:
            continue
        if _is_registered(page, tag):
            print(f"   [OK] #{tag}（登録済み）")
            continue
        # 上限に達していたら、こちらが指定していない自動提案タグを外す
        current = _registered_tags(page)
        if len(current) >= config.NOTE_TAG_LIMIT:
            extras = [t for t in current if norm_tag(t) not in wanted]
            if extras and _remove_extra_tag(page, extras[-1]):
                print(f"   [調整] 上限のため自動提案タグ {extras[-1]} を外しました")
        try:
            ok = _add_tag(page, tag)
        except Exception as e:
            print(f"   [注意] #{tag} の入力中に例外: {e}")
            ok = False
        print(f"   [{'OK' if ok else 'NG'}] #{tag}")

    final = _registered_tags(page)
    print(f"   最終的な登録タグ: {final}")
    registered = {norm_tag(t) for t in final}
    return [t for t in tags if norm_tag(t) not in registered]


# ---------------------------------------------------------------------------
# マガジン
# ---------------------------------------------------------------------------
_JS_MAGAZINE = """
({ name, doClick }) => {
  const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
  const target = norm(name);
  const root = document.querySelector('main') || document.body;
  const all = [...root.querySelectorAll('*')].filter(el => norm(el.textContent) === target);
  // 同じテキストを持つ子要素がない「最も内側」の要素だけを残す
  const leaves = all.filter(el => ![...el.children].some(c => norm(c.textContent) === target));
  for (const leaf of leaves) {
    let p = leaf.parentElement;
    for (let i = 0; i < 6 && p; i++, p = p.parentElement) {
      const btns = [...p.querySelectorAll('button')].filter(b => /追加/.test(b.textContent || ''));
      if (btns.length === 1) {
        const b = btns[0];
        const label = norm(b.textContent);
        if (/追加済/.test(label)) return 'added';
        if (!doClick) return 'not_added';
        b.scrollIntoView({ block: 'center' });
        b.click();
        return 'clicked';
      }
      if (btns.length > 1) break;  // 他のマガジンの行まで広がったら打ち切り
    }
  }
  return 'not_found';
}
"""


def apply_magazine(page, magazine_name):
    """マガジンに追加し、画面上で「追加済」になったかを返す"""
    print(f"7. マガジンに追加しています: {magazine_name}")
    try:
        menu = page.locator("#item-magazine-add").first
        if menu.count() > 0:
            menu.click()
            page.wait_for_timeout(1200)
        tab = page.locator("button").filter(has_text=re.compile(r"^マガジン$")).first
        if tab.count() > 0 and tab.is_visible():
            tab.click()
            page.wait_for_timeout(800)
        page.get_by_text(magazine_name, exact=True).first.wait_for(state="attached", timeout=15000)
    except Exception as e:
        print(f"   [NG] マガジン一覧に「{magazine_name}」が見つかりません: {e}")
        return False

    for attempt in range(3):
        state = page.evaluate(_JS_MAGAZINE, {"name": magazine_name, "doClick": True})
        if state == "added":
            print("   [OK] マガジン追加済みを確認しました")
            return True
        if state == "not_found":
            print("   [NG] マガジンの「追加」ボタンを特定できませんでした")
            return False
        page.wait_for_timeout(1500)
        if page.evaluate(_JS_MAGAZINE, {"name": magazine_name, "doClick": False}) == "added":
            print("   [OK] マガジンに追加しました")
            return True
        print(f"   [再試行] 追加状態を確認できません ({attempt + 1}/3)")
    return False


# ---------------------------------------------------------------------------
# 投稿確定
# ---------------------------------------------------------------------------
def _submit(page):
    print("8. 記事を投稿（公開）しています...")
    page.evaluate("window.scrollTo(0, 0)")
    btn = page.locator("button").filter(has_text=re.compile(r"^\s*(投稿する|更新する|公開する)\s*$")).first
    btn.wait_for(state="visible", timeout=15000)
    btn.click()
    try:
        page.get_by_text(re.compile(r"(公開|更新)されました")).first.wait_for(state="visible", timeout=20000)
        print("   [OK] 公開完了を確認しました")
    except Exception:
        print("   [注意] 完了表示を確認できませんでした（公開APIで検証します）")
        page.wait_for_timeout(3000)


def _run_settings(page, tags, magazine_name):
    missing = apply_tags(page, tags) if tags else []
    mag_ok = apply_magazine(page, magazine_name) if magazine_name else True
    if missing or not mag_ok:
        _save_debug(page, "settings")
    return missing, mag_ok


def _with_browser(fn, headless=True):
    cookies = load_cookies()
    if not cookies:
        raise PermissionError("noteのセッションCookieが見つかりません（NOTE_SESSION_COOKIES を設定してください）")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 900}, locale="ja-JP")
        context.add_cookies(cookies)
        page = context.new_page()
        try:
            return fn(page)
        except Exception:
            _save_debug(page, "error")
            raise
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# 公開後の検証（noteの公開APIを使用）
# ---------------------------------------------------------------------------
def fetch_public_tags(note_key):
    for page_no in (1, 2):
        url = f"https://note.com/api/v2/creators/{config.NOTE_USER}/contents?kind=note&page={page_no}"
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=15)
        r.raise_for_status()
        for c in r.json().get("data", {}).get("contents", []):
            if c.get("key") == note_key:
                return [h.get("hashtag", {}).get("name", "") for h in (c.get("hashtags") or [])]
    return None


def fetch_magazine_note_keys(magazine_key):
    url = f"https://note.com/api/v1/layout/magazine/{magazine_key}/section?page=1"
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=15)
    r.raise_for_status()
    return set(re.findall(r'"key":"(n[0-9a-z]{6,})"', r.text))


def verify_published(note_key, tags, magazine_key, attempts=4, interval=20):
    """反映ラグを考慮して数回ポーリングし、(不足タグ, マガジン反映可否) を返す"""
    missing, mag_ok = list(tags), not magazine_key
    for i in range(attempts):
        try:
            public = fetch_public_tags(note_key)
            if public is not None:
                have = {norm_tag(t) for t in public}
                missing = [t for t in tags if norm_tag(t) not in have]
            if magazine_key:
                mag_ok = note_key in fetch_magazine_note_keys(magazine_key)
            if not missing and mag_ok:
                break
        except Exception as e:
            print(f"   [注意] 公開APIでの検証に失敗: {e}")
        if i < attempts - 1:
            time.sleep(interval)
    return missing, mag_ok


# ---------------------------------------------------------------------------
# 公開エントリポイント
# ---------------------------------------------------------------------------
def publish_to_note(title, body_text, header_image_path=None, tags=None,
                    magazine_name=None, publish=True, headless=True):
    """
    noteに記事を投稿する。
    Returns:
        {"success", "url", "key", "status", "message", "missing_tags", "magazine_ok"}
    """
    tags = tags or []
    print(f"[{'公開' if publish else '下書き'}] noteへの自動投稿を開始します: {title}")

    def flow(page):
        _open_new_editor(page)
        _fill_title(page, title)
        _upload_header(page, header_image_path)
        _paste_body(page, body_text)
        key = _extract_key(page.url)

        if not publish:
            save = page.locator('button:has-text("下書き保存")').first
            if save.count() > 0 and save.is_visible():
                save.click()
                page.wait_for_timeout(3000)
            return {"success": True, "url": page.url, "key": key, "status": "draft",
                    "message": "下書きを保存しました", "missing_tags": [], "magazine_ok": False}

        _open_publish_settings(page)
        missing, mag_ok = _run_settings(page, tags, magazine_name)
        _submit(page)
        key = key or _extract_key(page.url)
        url = f"https://note.com/{config.NOTE_USER}/n/{key}" if key else page.url
        return {"success": True, "url": url, "key": key, "status": "published",
                "message": f"公開しました: {url}", "missing_tags": missing, "magazine_ok": mag_ok}

    try:
        return _with_browser(flow, headless=headless)
    except Exception as e:
        return {"success": False, "url": "", "key": "", "status": "error",
                "message": f"note投稿中にエラーが発生しました: {e}",
                "missing_tags": tags, "magazine_ok": False}


def repair_note_settings(note_key, tags, magazine_name, headless=True):
    """公開済み記事の編集画面を開き、タグ・マガジンを再設定して更新する"""
    print(f"[修復] 記事 {note_key} のタグ・マガジンを再設定します...")

    def flow(page):
        page.goto(f"https://editor.note.com/notes/{note_key}/edit/", wait_until="load", timeout=60000)
        if "/login" in page.url:
            raise PermissionError("セッションCookieの有効期限が切れています")
        _close_modal(page)
        page.wait_for_timeout(3000)
        _open_publish_settings(page)
        missing, mag_ok = _run_settings(page, tags, magazine_name)
        _submit(page)
        return missing, mag_ok

    try:
        return _with_browser(flow, headless=headless)
    except Exception as e:
        print(f"[修復] 再設定に失敗しました: {e}")
        return list(tags), False


def publish_with_verification(title, body_text, header_image_path, tags,
                              magazine_name, magazine_key, headless=True):
    """公開 → 公開APIで検証 → 不足があれば編集画面から修復 → 再検証"""
    result = publish_to_note(title, body_text, header_image_path, tags, magazine_name,
                             publish=True, headless=headless)
    if not result["success"] or not result["key"]:
        return result

    key = result["key"]
    print("9. 公開APIでタグ・マガジンの反映を検証しています...")
    missing, mag_ok = verify_published(key, tags, magazine_key)

    if missing or not mag_ok:
        print(f"   [NG] 不足タグ: {missing} / マガジン反映: {mag_ok} → 自動修復を試みます")
        repair_note_settings(key, missing or tags, None if mag_ok else magazine_name, headless=headless)
        missing, mag_ok = verify_published(key, tags, magazine_key)

    result["missing_tags"] = missing
    result["magazine_ok"] = mag_ok
    print(f"   検証結果 → 不足タグ: {missing or 'なし'} / マガジン: {'OK' if mag_ok else 'NG'}")
    return result


if __name__ == "__main__":
    # 単体テスト（下書き保存のみ）
    print(publish_to_note(
        "【テスト投稿】リテール自動化システムの検証記事",
        "これは自動投稿システムのテスト記事です。\n\n### 概要\nテスト本文です。",
        publish=False, headless=False,
    ))
