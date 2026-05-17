import os
import json
import datetime
import feedparser
import re
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
import io
import shutil
import ssl
import random
import glob

# 日本標準時 (JST)
JST = datetime.timezone(datetime.timedelta(hours=9))
ssl._create_default_https_context = ssl._create_unverified_context

# プロジェクトルート & パス探索ヘルパー
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))

def find_file(filename, subdirs=("config", "note", "")):
    """PROJECT_ROOT 配下の複数ディレクトリからファイルを探す"""
    for sub in subdirs:
        path = os.path.join(PROJECT_ROOT, sub, filename)
        if os.path.exists(path):
            return path
    return os.path.join(PROJECT_ROOT, filename)

# .envファイルの読み込み
env_path = find_file(".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

# 設定の取得
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# 定数
TARGET_DIR = os.path.join(PROJECT_ROOT, "content", "reports")
os.makedirs(TARGET_DIR, exist_ok=True)
HISTORY_FILENAME = "processed_history.json"

def validate_env():
    """必要な環境変数が揃っているか確認する"""
    required_vars = {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "EMAIL_SENDER": EMAIL_SENDER,
        "EMAIL_PASSWORD": EMAIL_PASSWORD,
        "EMAIL_RECEIVER": EMAIL_RECEIVER
    }
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print(f"[警告] 以下の環境変数が設定されていません: {', '.join(missing)}")
    else:
        print("[OK] 基礎的な環境変数の読み込みを確認しました。")

validate_env()

def get_drive_service():
    """Google Drive API サービスを取得。"""
    creds = None
    token_path = find_file("token.json")
    credentials_path = find_file("credentials.json")
    scopes = ["https://www.googleapis.com/auth/drive.file"]

    token_json = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json:
        try:
            creds_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(creds_data, scopes)
        except Exception as e:
            print(f"[NG] 警告: GOOGLE_TOKEN_JSON の解析に失敗しました: {e}")
    
    elif os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                creds = None
        
        if not creds or not creds.valid:
            creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                client_config = json.loads(creds_json)
                flow = InstalledAppFlow.from_client_config(client_config, scopes)
            elif os.path.exists(credentials_path):
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            else:
                raise Exception("認証情報が見つかりません。")
            
            creds = flow.run_local_server(port=0)
            
        if not os.getenv("GITHUB_ACTIONS"):
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            
    return build("drive", "v3", credentials=creds)

def load_history(service, folder_id):
    """Googleドライブから履歴ファイルを読み込む。"""
    print("過去の記事履歴を読み込んでいます...")
    try:
        query = f"name = '{HISTORY_FILENAME}' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        if not files:
            return [], None
            
        file_id = files[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        history_data = json.loads(fh.getvalue().decode('utf-8'))
        return history_data, file_id
    except Exception:
        return [], None

def save_history(service, folder_id, history_data, file_id):
    """履歴ファイルをGoogleドライブに保存。"""
    try:
        history_data = history_data[-500:]
        file_metadata = {'name': HISTORY_FILENAME, 'parents': [folder_id]}
        fh = io.BytesIO(json.dumps(history_data, ensure_ascii=False).encode('utf-8'))
        media_body = MediaIoBaseUpload(fh, mimetype='application/json', resumable=True)
        if file_id:
            service.files().update(fileId=file_id, media_body=media_body).execute()
        else:
            service.files().create(body=file_metadata, media_body=media_body).execute()
    except Exception as e:
        print(f"警告: 履歴の保存に失敗しました: {e}")

def fetch_latest_news(rss_feeds, target_days, history, now_jst):
    print(f"ニュースを収集しています (対象期間: 直近{target_days}日間)...")
    articles = []
    target_dates = [(now_jst - datetime.timedelta(days=i)).date() for i in range(1, target_days + 1)]
    seen_titles = set(history)
    
    for url in rss_feeds:
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                if entry.title in seen_titles:
                    continue
                
                entry_time = entry.get('published_parsed') or entry.get('updated_parsed')
                if entry_time:
                    try:
                        dt_utc = datetime.datetime(*entry_time[:6], tzinfo=datetime.timezone.utc)
                        dt_jst = dt_utc.astimezone(JST)
                        if dt_jst.date() in target_dates:
                            articles.append({
                                "title": entry.title,
                                "link": entry.link,
                                "summary": entry.get("summary", ""),
                            })
                            seen_titles.add(entry.title)
                            count += 1
                    except Exception: pass
                if count >= 10: break
        except Exception as e:
            print(f"警告: {url} の取得に失敗しました: {e}")
    
    print(f"新規記事を {len(articles)} 件取得しました。")
    return articles

def generate_contents(articles):
    if not articles: return None
    print("Geminiでレポートを生成しています...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    context = "\n".join([f"- {a['title']}: {a['link']}" for a in articles])
    prompt = f"""
あなたはフィールドマーケティングの専門家です。以下の最新ニュースから3つのトピックスを選び、デイリーレポートを作成してください。

【ニュースソース】
{context}

【アウトプット：デイリーレポート】
1. タイトル（1行目）：トピックで取り上げた企業名を【】で囲んで冒頭に付ける
2. 空行
3. 全体概要：3つのトピックを俯瞰した導入文。
4. 各トピック（3セット）：
    - トピックタイトル（独立した行）
    - 空行
    - ソースURL（そのまま記載。前後に空行）
    - 空行
    - 本文：専門家としての深い解説コラム。

【文体ルール】
- Markdown記法は使わず、プレーンテキスト形式で。
- 句点（。）ごとに改行し、2〜3文ごとに空行。
- リンクはURLをそのまま記載。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "タイトル",
  "daily_report": "レポート全文"
}}
"""
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        data = json.loads(re.search(r'\{.*\}', response.text, re.DOTALL).group())
        if 'article_title' in data and data['article_title'] not in data['daily_report']:
            data['daily_report'] = f"{data['article_title']}\n\n" + data['daily_report']
        return data
    except Exception: return None

def generate_weekly_summary(now_jst):
    print("過去1週間のレポートをまとめています...")
    reports = []
    for i in range(1, 8):
        target_date = (now_jst - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        path = os.path.join(TARGET_DIR, f"{target_date}-daily-report.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                reports.append(f"--- {target_date} ---\n" + f.read())
    
    if not reports:
        print("過去のレポートが見つからないため、まとめを作成できません。")
        return None
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    context = "\n\n".join(reports)
    prompt = f"""
あなたはフィールドマーケティングの専門家です。過去1週間に作成した以下の記事まとめを参照し、
一般消費者を対象として、暮らしの身近な部分に影響が出そうな内容をお知らせ・共有する記事を作成してください。

【過去1週間の記事内容】
{context}

【アウトプット：週間まとめレポート】
- 文字数：2000文字程度
- 内容：暮らしにどのような影響があるか、メリットを中心に分かりやすく解説。
- タイトル：【週間まとめ】暮らしを変えるリテール最新トレンド（{now_jst.strftime('%m/%d')}週）
- 構成：1. 全体俯瞰、2. 注目トピックの深掘り（3〜4つ）、3. まとめ

【文体ルール】
- Markdown記法禁止。プレーンテキスト形式。
- 句点ごとに改行、2〜3文ごとに空行。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "タイトル",
  "daily_report": "レポート全文"
}}
"""
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        data = json.loads(re.search(r'\{.*\}', response.text, re.DOTALL).group())
        if 'article_title' in data and data['article_title'] not in data['daily_report']:
            data['daily_report'] = f"{data['article_title']}\n\n" + data['daily_report']
        return data
    except Exception: return None

def load_note_urls():
    mapping_path = os.path.join(PROJECT_ROOT, "content", "docs", "retail_url_mapping.md")
    published_dir = os.path.join(PROJECT_ROOT, "content", "posts", "published")
    note_articles = []
    
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("|") and "note.com" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 4:
                            filename = parts[1].replace('`', '')
                            # url_mapping.md内では 'drafts/...' となっている場合もあるため basename を取る
                            filepath = os.path.join(published_dir, os.path.basename(filename))
                            url = parts[3]
                            if url.startswith("https://note.com") and os.path.exists(filepath):
                                note_articles.append({"file": filepath, "url": url})
        except Exception as e:
            print(f"url_mapping.mdの読み込みに失敗しました: {e}")
    return note_articles

def generate_x_posts(today_report, date_str):
    print("X（Twitter）用の投稿案を生成しています...")
    note_articles = load_note_urls()
    today_url = "[本日のnoteのURL]"
    
    past_reports = []
    if len(note_articles) >= 2:
        selected_articles = random.sample(note_articles, 2)
    else:
        selected_articles = note_articles
        
    for article in selected_articles:
        past_date = os.path.basename(article["file"])[:10]
        url = article["url"]
        with open(article["file"], "r", encoding="utf-8") as file:
            # プロンプトが長くなりすぎないように冒頭2000文字程度に絞る
            content_sample = file.read()[:2000]
            past_reports.append(f"【過去のnote記事: {past_date}】\nURL: {url}\n" + content_sample)
            
    past_context = "\n\n".join(past_reports)
    client = genai.Client(api_key=GEMINI_API_KEY)

    
    prompt = f"""
あなたはリテールDXとフィールドマーケティングの専門家です。
本日のレポートと過去のレポートを元に、X（Twitter）で1日に3回投稿するためのポスト案を作成してください。

【本日のレポート】
{today_report}

【過去のレポート（再放送用）】
{past_context}

【アウトプット要件】
以下の3つのポストを作成してください。
1. 「本日の新着記事」に関するポスト（本文とハッシュタグ合わせて110文字以内）
2. 「過去記事1」に関するポスト（本文とハッシュタグ合わせて110文字以内）
3. 「過去記事2」に関するポスト（本文とハッシュタグ合わせて110文字以内）

・この記事を自身のブログ（note）で公開・解説したという前提で、ブログ記事を読みたくなるような誘導（ティーザー）のポストにしてください。
・「本日の新着記事」のポストの最後には、必ず {today_url} をそのまま記載してください。
・「過去記事」のポストの最後には、それぞれに提供された「URL」の値をそのまま記載してください。
・Xの制限（全角140文字）に収めるため、本文＋ハッシュタグ2つ＋URLで合計140文字に収まるように、本文は必ず【110文字以内】と短く簡潔にしてください。
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
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"X投稿案の生成に失敗しました: {e}")
        return ""

def get_header_image(date_str, output_path):
    mm_dd = date_str[5:10]
    headers_dir = os.path.join(PROJECT_ROOT, "assets", "headers")
    preset_path = os.path.join(headers_dir, f"{mm_dd}.png")
    dated_path = os.path.join(headers_dir, f"{date_str}-header.png")
    target_path = preset_path if os.path.exists(preset_path) else (dated_path if os.path.exists(dated_path) else None)
    if target_path:
        if target_path != output_path: shutil.copy(target_path, output_path)
        return output_path
    return None

def send_email(subject, body, attachment_paths):
    print("メールを送信しています...")
    msg = MIMEMultipart()
    msg['From'], msg['To'], msg['Subject'] = EMAIL_SENDER, EMAIL_RECEIVER, subject
    msg.attach(MIMEText(body, 'plain'))
    for path in attachment_paths:
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(path))
        part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(path))
        msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

def main():
    try:
        now_jst = datetime.datetime.now(JST)
        date_str = now_jst.strftime("%Y-%m-%d")
        weekday = now_jst.weekday() # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        
        service = get_drive_service() if DRIVE_FOLDER_ID else None
        history, file_id = load_history(service, DRIVE_FOLDER_ID) if service else ([], None)

        if weekday == 6: # 日曜日：週間まとめ
            outputs = generate_weekly_summary(now_jst)
        else: # 平日・土曜：通常レポート
            # 曜日別ソース設定
            if weekday == 0: # 月曜：LNEWS & ダイヤモンドRM（週末分を含めて3日間）
                feeds, target_days = ["https://lnews.jp/feed", "https://diamond-rm.net/feed/"], 3
            elif weekday in [2, 3]: # 水・木：流通ニュース
                feeds, target_days = ["https://www.ryutsuu.biz/feed"], 1
            elif weekday == 4: # 金曜：LNEWS & ダイヤモンドRM
                feeds, target_days = ["https://lnews.jp/feed", "https://diamond-rm.net/feed/"], 1
            elif weekday in [1, 5]: # 火・土：PR TIMES
                feeds, target_days = ["https://news.google.com/rss/search?q=site:prtimes.jp+%E3%83%AA%E3%83%86%E3%83%BC%E3%83%ABDX&hl=ja&gl=JP&ceid=JP:ja"], 7
            else: # 水・金：LNEWS & ダイヤモンドRM
                feeds, target_days = ["https://lnews.jp/feed", "https://diamond-rm.net/feed/"], 1
            
            articles = fetch_latest_news(feeds, target_days, history, now_jst)
            if not articles:
                print("新しい記事がないため終了します。")
                return
            outputs = generate_contents(articles)
            # 履歴の保存
            if service and history is not None:
                new_titles = [a['title'] for a in articles]
                history.extend(new_titles)
                save_history(service, DRIVE_FOLDER_ID, history, file_id)

        if not outputs: return

        # ファイル保存
        md_report_path = os.path.join(TARGET_DIR, f"{date_str}-daily-report.md")
        with open(md_report_path, "w", encoding="utf-8") as f:
            f.write(outputs.get('daily_report', ''))
        
        header_path = os.path.join(TARGET_DIR, f"{date_str}-header.png")
        header_result = get_header_image(date_str, header_path)
        
        attachments = [md_report_path]
        if header_result: attachments.append(header_path)
        
        # X投稿案の生成
        x_posts_text = generate_x_posts(outputs.get('daily_report', ''), date_str)
        email_body = "本日のレポートを添付します。\n\n" + x_posts_text
        
        send_email(f"【日刊】{outputs.get('article_title', date_str)} - {date_str}", email_body, attachments)
        print("すべての工程が正常に終了しました。")
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    import traceback
    main()
