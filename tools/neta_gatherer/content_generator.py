"""
content_generator.py
Gemini API でデイリーレポート・週間まとめ・X投稿案を生成するモジュール。
"""

import datetime
import json
import os
import random
import re
import time
import unicodedata

from google import genai
from google.genai import types

import config

_client = None
_preferred_model = None


def _http_options():
    return types.HttpOptions(
        timeout=getattr(config, "GEMINI_HTTP_TIMEOUT_MS", 45000),
        retry_options=types.HttpRetryOptions(attempts=1),
    )


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=_http_options())
    return _client


def _generate(contents, json_mode=False, max_retries_per_model=2, delay=2):
    """過負荷時はリトライし、ダメなら次の候補モデルへ自動フォールバックする。"""
    global _preferred_model
    client = _get_client()
    http_opts = _http_options()
    if json_mode:
        cfg = types.GenerateContentConfig(response_mime_type="application/json", http_options=http_opts)
    else:
        cfg = types.GenerateContentConfig(http_options=http_opts)
    last_exc = None

    models = list(config.GEMINI_MODELS)
    if _preferred_model and _preferred_model in models:
        models = [_preferred_model] + [m for m in models if m != _preferred_model]

    for model in models:
        print(f"Gemini API 呼び出し中 (モデル: {model})...")
        for attempt in range(max_retries_per_model):
            try:
                resp = client.models.generate_content(model=model, contents=contents, config=cfg)
                _preferred_model = model
                return resp
            except Exception as e:
                last_exc = e
                msg = str(e).upper()
                if any(k in msg for k in ["404", "NOT_FOUND", "NOT FOUND", "UNKNOWN MODEL"]):
                    print(f"[注意] モデル「{model}」は利用できません。次の候補へ切り替えます。")
                    break
                if any(k in msg for k in ["429", "RESOURCE_EXHAUSTED", "QUOTA"]):
                    print(f"[注意] モデル「{model}」はクォータ制限に達しました。次の候補へ切り替えます。")
                    break
                if any(k in msg for k in ["504", "DEADLINE_EXCEEDED", "TIMEOUT", "TIMED OUT"]):
                    print(f"[注意] モデル「{model}」がタイムアウトしました。次の候補へ切り替えます。")
                    break
                temporary = any(k in msg for k in ["503", "UNAVAILABLE", "HIGH DEMAND", "TEMPORARY"])
                if temporary and attempt < max_retries_per_model - 1:
                    wait = delay * (2 ** attempt)
                    print(f"[警告] {model} が高負荷です。{wait}秒後に再試行します ({attempt + 1}/{max_retries_per_model})")
                    time.sleep(wait)
                    continue
                print(f"[警告] {model} のリクエストに失敗しました: {e}")
                time.sleep(1)
                break
    raise last_exc or RuntimeError("Gemini API の呼び出しに失敗しました")


def _parse_report_json(text):
    """{"article_title", "daily_report", "target_entities"} を取り出し、重複タイトルを除去する"""
    try:
        data = json.loads(re.search(r"\{.*\}", text, re.DOTALL).group())
    except Exception as e:
        print(f"[エラー] Geminiの出力をJSONとして解析できませんでした: {e}")
        return None
    title = (data.get("article_title") or "").strip()
    body = (data.get("daily_report") or "").strip()
    if not title or not body:
        return None
    if body.startswith(title):
        body = body[len(title):].strip()
    raw_entities = data.get("target_entities")
    entities = []
    if isinstance(raw_entities, list):
        for item in raw_entities:
            if isinstance(item, str) and item.strip():
                entities.append(item.strip())
    return {"article_title": title, "daily_report": body, "target_entities": entities}


# ---------------------------------------------------------------------------
# デイリーレポート
# ---------------------------------------------------------------------------
def generate_daily_report(articles):
    print("Geminiでレポートを生成しています...")
    context = "\n".join(f"- {a['title']}: {a['link']}" for a in articles)
    prompt = f"""
あなたはフィールドマーケティングの専門家です。以下の最新ニュースから3つのトピックスを選び、デイリーレポートを作成してください。

【トピック選定ルール（厳守）】
- 【厳禁】店舗の新規出店・開店・オープン・新設・移転・開業に関するニュースは、旗艦店・新業態・1号店・話題店であっても一切選定しないでください。
- 【厳禁】イベント案内、セミナー・ウェビナー案内、展示会出展、参加者募集、一時的なキャンペーン告知等のPR記事は選定しないでください。
- 「企業の事業戦略、業態転換、業務提携・M&A、現場DX、新MD・商品戦略、物流・配送網強化、サプライチェーン改革」に関するニュースを選定してください。
- ドラッグストア・調剤併設・薬局関連（ウエルシア、ツルハ、マツキヨ、スギ薬局、コスモス等）のニュースが含まれている場合は、少なくとも1つは優先的に選出してください。

【ニュースソース】
{context}

【アウトプット構成ルール】
- `article_title`: トピックで取り上げた対象企業名・サービス名のみを【】で囲み、`／` 区切りで冒頭に付けた魅力的な記事タイトル（例: 【イオン／ファミマ／コープ】...）
- `target_entities`: 記事の主な対象となる具体的な企業名・サービス名のみのリスト（業態名や「ドラッグストア」「物流DX」等の一般名詞は含めない）
- `daily_report`: 記事本文（※記事タイトルは本文冒頭に含めず、全体概要から書き始めてください）

【本文（daily_report）の構成】
1. 全体概要：3つのトピックを俯瞰した導入文（150〜200文字程度）。
2. 空行
3. 各トピック（3セット）：
    - トピックの小見出し（必ず `### ` を先頭に付けたh3小見出し）
    - 空行
    - ソースURL（そのまま記載）
    - 空行
    - 本文：専門家としての解説コラム（各300〜400文字。市場背景、フィールドマーケティングへの具体的なインパクト、今後の展望や取るべきアクション。無駄な装飾語は排除）。

【文体・書式ルール】
- レポート全体は1600〜1800文字（最大でも2000文字以内）。
- 句点（。）ごとに改行し、2〜3文ごとに空行を入れて読みやすくしてください。
- リンクはURLをそのまま記載してください。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "タイトル（対象企業名・サービス名を【】で囲む）",
  "target_entities": ["企業名・サービス名1", "企業名・サービス名2", "企業名・サービス名3"],
  "daily_report": "全体概要から始まるレポート本文全文（### 小見出しを使用）"
}}
"""
    return _parse_report_json(_generate(prompt, json_mode=True).text)


# ---------------------------------------------------------------------------
# 週間まとめ（日曜）
# ---------------------------------------------------------------------------
def generate_weekly_summary(now_jst):
    print("過去1週間のレポートをまとめています...")
    reports = []
    for i in range(1, 8):
        d = (now_jst - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        path = os.path.join(config.REPORTS_DIR, f"{d}-daily-report.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                reports.append(f"--- {d} ---\n" + f.read())
    if not reports:
        print("過去のレポートが見つからないため、まとめを作成できません。")
        return None

    context = "\n\n".join(reports)
    prompt = f"""
あなたはフィールドマーケティングの専門家です。過去1週間に作成した以下の記事まとめを参照し、
一般消費者を対象として、暮らしの身近な部分に影響が出そうな内容をお知らせ・共有する記事を作成してください。
店舗の新規出店・オープンに関する話題は取り上げないでください。

【過去1週間の記事内容】
{context}

【アウトプット構成ルール】
- `article_title`: 【週間まとめ】暮らしを変えるリテール最新トレンド（{now_jst.strftime('%m/%d')}週）
- `daily_report`: 記事本文（※記事タイトルは本文冒頭に含めず、全体俯瞰から書き始めてください）

【本文（daily_report）の構成】
1. 全体俯瞰（導入文）
2. 注目トピックの深掘り（3〜4つ。各トピックのタイトルは必ず `### ` から始まるh3小見出し）
3. まとめ

【文体・書式ルール】
- 文字数：2000文字程度
- 句点ごとに改行、2〜3文ごとに空行。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "タイトル",
  "daily_report": "全体俯瞰から始まるレポート本文全文（### 小見出しを使用）"
}}
"""
    return _parse_report_json(_generate(prompt, json_mode=True).text)


# ---------------------------------------------------------------------------
# noteハッシュタグ
# ---------------------------------------------------------------------------
_PROTECTED_MIDDOT_NAMES = [
    "ドン・キホーテ",
    "セブン・イレブン",
    "セブン‐イレブン",
    "ロビン・フッド",
    "V・ドラッグ",
    "セキミキ・グループ",
    "ザ・ビッグ",
    "ミスター・マックス",
]
_HEADING_IGNORE_WORDS = ("日刊", "週間まとめ", "テスト")


def _norm_entity_key(text):
    t = unicodedata.normalize("NFKC", text or "").lstrip("#").upper()
    return re.sub(r"[\W_]", "", t)


def _clean_entity_name(name):
    c = re.sub(r"[#＃!！?？,，.。:：;；\[\]【】]", "", (name or "").strip())
    return c.strip()


def _split_entity_text(raw):
    text = (raw or "").strip()
    if not text:
        return []
    if "/" in text or "／" in text:
        parts = re.split(r"[/／、,，&＆]+", text)
    else:
        placeholders = {}
        protected = text
        for idx, name in enumerate(_PROTECTED_MIDDOT_NAMES):
            if name in protected:
                token = f"__MIDDOT_{idx}__"
                protected = protected.replace(name, token)
                placeholders[token] = name
        parts = re.split(r"[/／、・,，\s&＆]+", protected)
        restored = []
        for p in parts:
            for tok, orig in placeholders.items():
                p = p.replace(tok, orig)
            restored.append(p)
        parts = restored
    return [c for c in (_clean_entity_name(p) for p in parts) if c and len(c) <= 20]


def build_note_tags(article_title, body_text="", target_entities=None):
    """
    note用ハッシュタグ（上限 NOTE_TAG_LIMIT 個 = 7個、下限なし）を生成する。
    1. 「フィールドマーケティング」（最優先・固定必須）
    2. 記事の対象となる企業名・サービス名のみ（一般語やフォールバックでの穴埋めはしない）
    """
    must_tags = [t for t in config.NOTE_MUST_TAGS if t]
    seen_norm = {_norm_entity_key(t) for t in must_tags}
    entities = []

    def _add_entity(raw_name):
        c = _clean_entity_name(raw_name)
        if not c or len(c) > 20:
            return
        if any(k in c for k in _HEADING_IGNORE_WORDS):
            return
        key = _norm_entity_key(c)
        if key and key not in seen_norm:
            seen_norm.add(key)
            entities.append(c)

    # 1. タイトルの【】から企業名・サービス名を抽出
    title_m = re.search(r"【(.*?)】", article_title or "")
    if title_m and not any(k in title_m.group(1) for k in _HEADING_IGNORE_WORDS):
        for item in _split_entity_text(title_m.group(1)):
            _add_entity(item)

    # 2. target_entities（Geminiが構造化出力した対象企業名・サービス名）を追加
    if isinstance(target_entities, list):
        for item in target_entities:
            if isinstance(item, str):
                for sub in _split_entity_text(item):
                    _add_entity(sub)
    elif isinstance(target_entities, str):
        for sub in _split_entity_text(target_entities):
            _add_entity(sub)

    # 3. タイトル・target_entities から取れなかった場合のみ、本文の ### 【...】 小見出しから補完
    if not entities and body_text:
        for bm in re.finditer(r"^###\s+【(.*?)】", body_text, re.MULTILINE):
            if not any(k in bm.group(1) for k in _HEADING_IGNORE_WORDS):
                for item in _split_entity_text(bm.group(1)):
                    _add_entity(item)

    return (must_tags + entities)[:config.NOTE_TAG_LIMIT]


# ---------------------------------------------------------------------------
# X投稿案
# ---------------------------------------------------------------------------
def _load_note_articles():
    articles = []
    if not os.path.exists(config.MAPPING_PATH):
        return articles
    try:
        with open(config.MAPPING_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not (line.startswith("|") and "note.com" in line):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 4:
                    continue
                path = os.path.join(config.PUBLISHED_DIR, os.path.basename(parts[1].replace("`", "")))
                if parts[3].startswith("https://note.com") and os.path.exists(path):
                    articles.append({"file": path, "url": parts[3]})
    except Exception as e:
        print(f"retail_url_mapping.md の読み込みに失敗しました: {e}")
    return articles


def _article_date(article):
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", os.path.basename(article["file"]))
    if m:
        try:
            return datetime.datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(article["file"]), config.JST).date()
    except Exception:
        return datetime.date(2000, 1, 1)


def generate_x_posts(today_report, today_url=""):
    print("X（Twitter）用の投稿案を生成しています...")
    note_articles = _load_note_articles()
    today = datetime.datetime.now(config.JST).date()
    recent = [a for a in note_articles if today - datetime.timedelta(days=14) <= _article_date(a) <= today]
    pool = recent if len(recent) >= 2 else note_articles
    selected = random.sample(pool, 2) if len(pool) >= 2 else pool

    past = []
    for a in selected:
        m = re.match(r"^(\d{4}-\d{2}-\d{2})", os.path.basename(a["file"]))
        with open(a["file"], "r", encoding="utf-8") as f:
            past.append(f"【過去のnote記事: {m.group(1) if m else '過去記事'}】\nURL: {a['url']}\n" + f.read()[:2000])

    url_text = today_url or "[本日のnoteのURL]"
    prompt = f"""
あなたはリテールDXとフィールドマーケティングの専門家です。
本日のレポートと過去のレポートを元に、X（Twitter）で1日に3回投稿するためのポスト案を作成してください。

【本日のレポート】
{today_report}

【過去のレポート（再放送用）】
{chr(10).join(past)}

【アウトプット要件】
1. 「本日の新着記事」に関するポスト
2. 「過去記事1」に関するポスト
3. 「過去記事2」に関するポスト

・ブログ（note）記事を読みたくなるティーザーにしてください。
・「本日の新着記事」のポストの最後には、必ず {url_text} をそのまま記載してください。
・「過去記事」のポストの最後には、それぞれの「URL」の値をそのまま記載してください。
・本文＋ハッシュタグ2つ＋URLで全角140文字に収まるよう、本文は必ず110文字以内にしてください。
・専門家としての鋭い視点や、現場の人が「なるほど」と思う気づきを含めること。
・プレーンテキストで、以下のフォーマットで出力してください。

【本日のX投稿スケジュール案】

① 朝（本日の記事紹介）
(ポスト本文)
(今日のURL)

② 昼（過去記事の再紹介）
(ポスト本文)
(過去記事のURL)

③ 晩（過去記事の再紹介）
(ポスト本文)
(過去記事のURL)
"""
    try:
        return _generate(prompt).text.strip()
    except Exception as e:
        print(f"X投稿案の生成に失敗しました: {e}")
        return ""
