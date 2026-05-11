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

# 日本標準時 (JST)
JST = datetime.timezone(datetime.timedelta(hours=9))

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
RSS_FEEDS = [
    "https://lnews.jp/feed",
    "https://www.ryutsuu.biz/feed",
    "https://prtimes.jp/main/html/searchrlp/kw/%E3%83%AA%E3%83%86%E3%83%BC%E3%83%ABDX",
    "https://diamond-rm.net/feed/",
    "https://news.google.com/rss/search?q=%E5%B0%8F%E5%A3%B2+OR+%E6%B5%81%E9%80%9A+OR+%E5%BA%97%E8%88%97DX&hl=ja&gl=JP&ceid=JP:ja"
]
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
    """Google Drive API サービスを取得。ローカルファイルと環境変数の両方に対応。"""
    creds = None
    token_path = find_file("token.json")
    credentials_path = find_file("credentials.json")
    scopes = ["https://www.googleapis.com/auth/drive.file"]

    # 1. 環境変数からのトークン取得を優先（GitHub Actions環境）
    token_json = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json:
        try:
            creds_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(creds_data, scopes)
            print("[OK] Googleトークンを環境変数から読み込みました。")
        except Exception as e:
            print(f"[NG] 警告: GOOGLE_TOKEN_JSON の解析に失敗しました: {e}")
    
    # 2. ローカルファイルからのトークン取得
    elif os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
        
    # 3. トークンがない、または無効な場合は認証または更新を行う
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Googleトークンを更新しています...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"トークンの更新に失敗しました: {e}")
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
            
            if os.getenv("GITHUB_ACTIONS") and not token_json:
                raise Exception("GitHub Actions環境では有効な GOOGLE_TOKEN_JSON が必須です。")
            
            print("ブラウザを開いて認証を行います...")
            creds = flow.run_local_server(port=0)
            
        if not os.getenv("GITHUB_ACTIONS"):
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            
    return build("drive", "v3", credentials=creds)

def load_history(service, folder_id):
    """Googleドライブから履歴ファイルを読み込む。データとfile_idのタプルを返す。"""
    print("過去の記事履歴を読み込んでいます...")
    try:
        query = f"name = '{HISTORY_FILENAME}' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        if not files:
            print("履歴ファイルが見つかりません。新規作成します。")
            return [], None
            
        file_id = files[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        history_data = json.loads(fh.getvalue().decode('utf-8'))
        print(f"[OK] {len(history_data)} 件の履歴を読み込みました。")
        return history_data, file_id
    except Exception as e:
        print(f"警告: 履歴の読み込みに失敗しました: {e}")
        return [], None

def save_history(service, folder_id, history_data, file_id):
    """履歴ファイルをGoogleドライブに保存（上書きまたは新規作成）"""
    print(f"記事履歴を保存しています ({len(history_data)} 件)...")
    try:
        # 最新の500件に制限
        history_data = history_data[-500:]
        
        file_metadata = {'name': HISTORY_FILENAME, 'parents': [folder_id]}
        
        # メモリ上のデータをアップロードするために MediaIoBaseUpload を使用
        fh = io.BytesIO(json.dumps(history_data, ensure_ascii=False).encode('utf-8'))
        media_body = MediaIoBaseUpload(fh, mimetype='application/json', resumable=True)
        
        if file_id:
            # 上書き
            service.files().update(fileId=file_id, media_body=media_body).execute()
        else:
            # 新規作成
            service.files().create(body=file_metadata, media_body=media_body).execute()
        print("[OK] 履歴の保存が完了しました。")
    except Exception as e:
        print(f"警告: 履歴の保存に失敗しました: {e}")

def fetch_latest_news(history, now_jst):
    print("ニュースを収集しています...")
    articles = []
    # 前日の記事のみを対象にする
    target_date = (now_jst - datetime.timedelta(days=1)).date()
    
    seen_titles = set(history)
    
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                # 重複チェック（タイトル）
                if entry.title in seen_titles:
                    continue
                
                entry_time = entry.get('published_parsed') or entry.get('updated_parsed')
                if entry_time:
                    try:
                        # feedparserの時間はUTCなので、正しくJSTに変換する
                        dt_utc = datetime.datetime(*entry_time[:6], tzinfo=datetime.timezone.utc)
                        dt_jst = dt_utc.astimezone(JST)
                        
                        if dt_jst.date() == target_date:
                            articles.append({
                                "title": entry.title,
                                "link": entry.link,
                                "summary": entry.get("summary", ""),
                            })
                            seen_titles.add(entry.title)
                            count += 1
                    except Exception as e:
                        print(f"警告: 記事の日付パースに失敗しました: {e}")
                
                if count >= 10:
                    break
        except Exception as e:
            print(f"警告: {url} の取得に失敗しました: {e}")
    
    print(f"新規記事を {len(articles)} 件取得しました。")
    return articles


def generate_contents(articles):
    if not articles:
        return None
    
    print("Geminiでレポートを生成しています...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    context = "\n".join([f"- {a['title']}: {a['link']}" for a in articles])
    
    prompt = f"""
あなたはフィールドマーケティングの専門家です。以下の最新ニュースから3つのトピックスを選び、
デイリーレポートを作成してください。

【ニュースソース】
{context}

【アウトプット1：デイリーレポート (note貼り付け用)】
以下の構成で作成してください。合計1,800文字程度のボリュームにします。
1. タイトル（1行目）：概要がわかるタイトル。トピックで取り上げた企業名を【】で囲んで冒頭に付ける（例：【イオン、ヤオコー、セブンイレブン】店舗DXと価格戦略の最前線）
2. 空行
3. 全体概要：3つのトピックを俯瞰した導入文。
4. 各トピック（3セット）：
    - トピックタイトル（独立した行として記載。記号は使わない）
    - 空行
    - ソースURL（URLのみをそのまま生で記載。独立した段落とするため、必ず前後に空行を入れること）
    - 空行
    - 本文：専門家としての深い解説コラム。

【文体ルール（重要）】
- Markdown記法（##, **, >, - など）は絶対に、一切使わないでください。
- すべてプレーンテキスト形式で書いてください。
- 見出しや強調に記号を使わず、文章の内容と構成のみで読みやすさを確保してください。
- リンクにMarkdown記法 [ ]( ) は使わず、URLをそのまま生で記載してください。
- 句点（。）ごとに改行してください。
- 2〜3文ごとに空行を入れてください。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "タイトル",
  "daily_report": "レポート全文",
  "ideas_summary": "構造化されたネタ帳"
}}
"""
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    
    # JSON部分を抽出（余計なテキストが含まれる場合の対策）
    text = response.text
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            data = json.loads(text)
    except Exception as e:
        print(f"[エラー] JSONのパースに失敗しました: {e}")
        print(f"生の出力: {text}")
        return None
    
    # note向け修正
    if 'daily_report' in data:
        report = data['daily_report']
        # タイトルが本文に含まれていない場合は追加
        if 'article_title' in data and data['article_title'] not in report:
            report = f"{data['article_title']}\n\n" + report
        data['daily_report'] = report
        
    return data


def get_header_image(date_str, output_path):
    """
    ヘッダー画像を取得する。
    1. assets/headers/{MM-DD}.png (Canva製プリセット)
    2. assets/headers/{YYYY-MM-DD}-header.png (過去の生成物)
    """
    mm_dd = date_str[5:10]
    headers_dir = os.path.join(PROJECT_ROOT, "assets", "headers")
    
    # 候補1: プリセット (05-09.png)
    preset_path = os.path.join(headers_dir, f"{mm_dd}.png")
    # 候補2: 日付入り (2026-05-09-header.png)
    dated_path = os.path.join(headers_dir, f"{date_str}-header.png")
    
    target_path = None
    if os.path.exists(preset_path):
        print(f"[OK] プリセット画像を使用します: {mm_dd}.png")
        target_path = preset_path
    elif os.path.exists(dated_path):
        print(f"[OK] 日付入り画像を使用します: {date_str}-header.png")
        target_path = dated_path
    
    if target_path:
        if target_path != output_path:
            shutil.copy(target_path, output_path)
        return output_path
    
    print(f"[警告] ヘッダー画像が見つかりません: {preset_path} または {dated_path}")
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
        
        # 0. Drive サービスの初期化 & 履歴の読み込み
        service = None
        history = []
        file_id = None
        if DRIVE_FOLDER_ID:
            service = get_drive_service()
            history, file_id = load_history(service, DRIVE_FOLDER_ID)
            
        # 1. ニュース収集
        articles = fetch_latest_news(history, now_jst)
        if not articles:
            print("新しい記事がないため、本日の処理を終了します。")
            return
            
        # 2. コンテンツ生成
        outputs = generate_contents(articles)
        if not outputs: return

        # 3. ファイルの保存
        md_ideas_path = os.path.join(TARGET_DIR, f"{date_str}-ideas.md")
        md_report_path = os.path.join(TARGET_DIR, f"{date_str}-daily-report.md")
        header_path = os.path.join(TARGET_DIR, f"{date_str}-header.png")

        with open(md_ideas_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(outputs.get('ideas_summary', ''), ensure_ascii=False, indent=2))
        with open(md_report_path, "w", encoding="utf-8") as f:
            f.write(outputs.get('daily_report', ''))
            
        header_result = get_header_image(date_str, header_path)
            
        # 4. 履歴の更新と保存（重複排除のため）
        if service and DRIVE_FOLDER_ID:
            try:
                new_titles = [a['title'] for a in articles]
                history.extend(new_titles)
                save_history(service, DRIVE_FOLDER_ID, history, file_id)
            except Exception as e:
                print(f"[警告] 履歴の保存に失敗しましたが継続します: {e}")
        
        # 5. メール送信（ヘッダー画像がある場合のみ添付）
        attachments = [md_ideas_path, md_report_path]
        if header_result:
            attachments.append(header_path)
        send_email(f"【日刊】{outputs.get('article_title', date_str)} - {date_str}", "本日のレポートを添付します。", attachments)
        print("すべての工程が正常に終了しました。")
    except Exception as e:
        print(f"致命的エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
