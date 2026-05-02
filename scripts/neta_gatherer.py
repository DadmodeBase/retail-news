import os
import json
import datetime
import time
import requests
import feedparser
import re
import google.generativeai as genai
from google.cloud import texttospeech
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import io

# .envファイルの読み込み
# ルート直下または note/ 直下の .env を探す
env_paths = [
    os.path.join(os.path.dirname(__file__), "..", ".env"),
    os.path.join(os.path.dirname(__file__), "..", "note", ".env")
]
for p in env_paths:
    if os.path.exists(p):
        load_dotenv(dotenv_path=p)
        break

# 設定の取得
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# 定数
TARGET_DIR = os.path.join(os.path.dirname(__file__), "..", "ideas")
os.makedirs(TARGET_DIR, exist_ok=True)
RSS_FEEDS = [
    "https://lnews.jp/feed",
    "https://www.ryutsuu.biz/feed",
    "https://prtimes.jp/main/html/searchrlp/kw/%E3%83%AA%E3%83%86%E3%83%BC%E3%83%ABDX"
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

# --- クラウド実行（GitHub Actions）用の認証設定 ---
def setup_cloud_auth():
    """環境変数から認証ファイルを一時的に復元する"""
    gcp_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if gcp_json:
        gcp_key_path = os.path.join(TARGET_DIR, "gcp_key.json")
        with open(gcp_key_path, "w", encoding="utf-8") as f:
            f.write(gcp_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcp_key_path
        print("Cloud TTS credentials successfully loaded from environment variable.")

setup_cloud_auth()

def get_drive_service():
    """Google Drive API サービスを取得。ローカルファイルと環境変数の両方に対応。"""
    creds = None
    # 複数のパスを試す
    token_locations = [
        os.path.join(os.path.dirname(__file__), "..", "token.json"),
        os.path.join(os.path.dirname(__file__), "..", "note", "token.json")
    ]
    credentials_locations = [
        os.path.join(os.path.dirname(__file__), "..", "credentials.json"),
        os.path.join(os.path.dirname(__file__), "..", "note", "credentials.json")
    ]
    
    token_path = next((p for p in token_locations if os.path.exists(p)), token_locations[0])
    credentials_path = next((p for p in credentials_locations if os.path.exists(p)), credentials_locations[0])
    
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

def load_history(folder_id):
    """Googleドライブから履歴ファイルを読み込む"""
    print("過去の記事履歴を読み込んでいます...")
    try:
        service = get_drive_service()
        query = f"name = '{HISTORY_FILENAME}' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        if not files:
            print("履歴ファイルが見つかりません。新規作成します。")
            return []
            
        file_id = files[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        history_data = json.loads(fh.getvalue().decode('utf-8'))
        print(f"[OK] {len(history_data)} 件の履歴を読み込みました。")
        return history_data
    except Exception as e:
        print(f"警告: 履歴の読み込みに失敗しました: {e}")
        return []

def save_history(folder_id, history_data):
    """履歴ファイルをGoogleドライブに保存（上書きまたは新規作成）"""
    print(f"記事履歴を保存しています ({len(history_data)} 件)...")
    try:
        # 最新の500件に制限
        history_data = history_data[-500:]
        
        service = get_drive_service()
        file_metadata = {'name': HISTORY_FILENAME, 'parents': [folder_id]}
        
        # メモリ上のデータをアップロードするために MediaIoBaseUpload を使用
        fh = io.BytesIO(json.dumps(history_data, ensure_ascii=False).encode('utf-8'))
        media_body = MediaIoBaseUpload(fh, mimetype='application/json', resumable=True)
        
        # 既存ファイルの検索
        query = f"name = '{HISTORY_FILENAME}' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        
        if files:
            # 上書き
            service.files().update(fileId=files[0]['id'], media_body=media_body).execute()
        else:
            # 新規作成
            service.files().create(body=file_metadata, media_body=media_body).execute()
        print("[OK] 履歴の保存が完了しました。")
    except Exception as e:
        print(f"警告: 履歴の保存に失敗しました: {e}")

def fetch_latest_news(history):
    print("ニュースを収集しています...")
    articles = []
    # 過去2日分の記事を対象にする（時差考慮）
    target_date_1 = (datetime.datetime.now() - datetime.timedelta(days=0)).date()
    target_date_2 = (datetime.datetime.now() - datetime.timedelta(days=1)).date()
    
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
                        dt = datetime.datetime.fromtimestamp(time.mktime(entry_time))
                        if dt.date() in [target_date_1, target_date_2]:
                            articles.append({
                                "title": entry.title,
                                "link": entry.link,
                                "summary": entry.get("summary", ""),
                            })
                            seen_titles.add(entry.title)
                            count += 1
                    except Exception:
                        pass
                
                if count >= 10:
                    break
        except Exception as e:
            print(f"警告: {url} の取得に失敗しました: {e}")
    
    print(f"新規記事を {len(articles)} 件取得しました。")
    return articles

def clean_text_for_tts(text):
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'---+', '', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'-\s*', '', text)
    return text

def generate_contents(articles):
    if not articles:
        return None
    
    print("Geminiでレポートと音声を生成しています...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
    
    context = "\n".join([f"- {a['title']}: {a['link']}" for a in articles])
    
    prompt = f"""
あなたはフィールドマーケティングの専門家です。以下の最新ニュースから3つのトピックスを選び、
デイリーレポートと音声読み上げ用原稿を作成してください。

【ニュースソース】
{context}

【アウトプット1：デイリーレポート (Markdown)】
以下の構成で作成してください。合計1,800文字程度のボリュームにします。
1. **内容の概要がわかる30文字程度のタイトル**
2. **タイトル・日付**
3. **【全体概要】**: 3つのトピックを俯瞰した、今日の潮流を読み解く導入文。
4. **トピック別の詳細** (3セット):
    - トピックの見出し（## レベル）
    - 出典URL
    - コラム形式の深い解説

【文体ルール】
- です・ます調の対話体。
- 句点（。）ごとに改行。
- 重要なインサイトは太字。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "タイトル",
  "daily_report": "レポート全文",
  "audio_script": "読み上げ用テキスト",
  "ideas_summary": "構造化されたネタ帳"
}}
"""
    response = model.generate_content(prompt)
    json_text = re.search(r'\{.*\}', response.text, re.DOTALL).group()
    data = json.loads(json_text)
    
    # マークダウン修正
    if 'daily_report' in data:
        report = data['daily_report']
        report = re.sub(r'\s*\*\*\s*', '**', report)
        report = re.sub(r'\*\*(.*?)\*\*', r' **\1** ', report)
        if 'article_title' in data:
            report = f"# {data['article_title']}\n\n" + report
        data['daily_report'] = report
        
    return data

def generate_audio(text, output_path):
    print("Google Cloud TTSで音声を生成しています...")
    client = texttospeech.TextToSpeechClient()
    clean_text = clean_text_for_tts(text)
    synthesis_input = texttospeech.SynthesisInput(text=clean_text)
    voice = texttospeech.VoiceSelectionParams(language_code="ja-JP", name="ja-JP-Neural2-C")
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    with open(output_path, "wb") as out:
        out.write(response.audio_content)

def generate_header_image(date_str, output_path):
    print(f"ヘッダー画像を生成しています: {output_path}")
    base_image_path = os.path.join(os.path.dirname(__file__), "..", "resources", "header_base.png")
    
    if os.path.exists(base_image_path):
        img = Image.open(base_image_path).convert("RGB")
        # 指定サイズ (1920x1006) にリサイズ
        img = img.resize((1920, 1006), Image.Resampling.LANCZOS)
    else:
        # 高級感のあるグラデーション背景 (1920x1006)
        img = Image.new('RGB', (1920, 1006))
        draw = ImageDraw.Draw(img)
        for y in range(1006):
            r = int(15 + (40 - 15) * (y / 1006))
            g = int(35 + (80 - 35) * (y / 1006))
            b = int(75 + (130 - 75) * (y / 1006))
            draw.line([(0, y), (1920, y)], fill=(r, g, b))

    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # フォント設定
    font_paths = [
        "C:\\Windows\\Fonts\\meiryo.ttc",
        "C:\\Windows\\Fonts\\msgothic.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    ]
    
    # 日本語フォントが無い場合はダウンロード
    fallback_font_path = os.path.join(TARGET_DIR, "NotoSansJP-SemiBold.ttf")
    if not any(os.path.exists(f) for f in font_paths) and not os.path.exists(fallback_font_path):
        try:
            print("日本語フォントをダウンロードします...")
            font_url = "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP-SemiBold.ttf"
            urllib_request = __import__('urllib.request').request
            urllib_request.urlretrieve(font_url, fallback_font_path)
        except: pass
    
    font_paths.insert(0, fallback_font_path)
    font_main, font_date = None, None
    for p in font_paths:
        if os.path.exists(p):
            try:
                font_main = ImageFont.truetype(p, 120)
                font_date = ImageFont.truetype(p, 80)
                break
            except: pass

    if not font_main:
        font_main = font_date = ImageFont.load_default()
    
    date_text = date_str.split("-")[-2].lstrip("0") + "月" + date_str.split("-")[-1].lstrip("0") + "日"
    main_text = "日刊 リテールニュース"
    
    try:
        # シャドウの色
        shadow_color = (0, 0, 0)
        shadow_offset = 4
        
        # 日付の描画
        date_bbox = draw.textbbox((0, 0), date_text, font=font_date)
        date_x = (w - (date_bbox[2]-date_bbox[0]))/2
        date_y = h/2 - 150
        # 影を描画
        draw.text((date_x + shadow_offset, date_y + shadow_offset), date_text, font=font_date, fill=shadow_color)
        # 本体を描画
        draw.text((date_x, date_y), date_text, font=font_date, fill=(255, 255, 255))
        
        # メインタイトルの描画
        main_bbox = draw.textbbox((0, 0), main_text, font=font_main)
        main_x = (w - (main_bbox[2]-main_bbox[0]))/2
        main_y = h/2 - 20
        # 影を描画
        draw.text((main_x + shadow_offset, main_y + shadow_offset), main_text, font=font_main, fill=shadow_color)
        # 本体を描画
        draw.text((main_x, main_y), main_text, font=font_main, fill=(255, 255, 255))
    except:
        # フォールバック時も簡易的な影を付ける
        draw.text((w/2-198, h/2-98), date_text, font=font_date, fill=(0,0,0))
        draw.text((w/2-200, h/2-100), date_text, font=font_date, fill=(255,255,255))
        draw.text((w/2-298, h/2+2), main_text, font=font_main, fill=(0,0,0))
        draw.text((w/2-300, h/2), main_text, font=font_main, fill=(255,255,255))
    
    img.save(output_path)

def upload_to_drive(file_path, folder_id):
    print(f"Googleドライブへアップロードしています: {os.path.basename(file_path)}")
    try:
        service = get_drive_service()
        file_metadata = {"name": os.path.basename(file_path), "parents": [folder_id]}
        ext = os.path.splitext(file_path)[1].lower()
        
        # アップロードするファイル自体のMIMEタイプを指定
        if ext == '.md':
            mimetype = 'text/markdown'
            # Googleドキュメント形式に変換したい場合は metadata に指定
            file_metadata['mimeType'] = 'application/vnd.google-apps.document'
        elif ext == '.png':
            mimetype = 'image/png'
        elif ext == '.mp3':
            mimetype = 'audio/mpeg'
        else:
            mimetype = None
        
        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        print(f"[OK] アップロード成功")
    except Exception as e:
        print(f"[NG] アップロード失敗: {e}")

def send_email(subject, body, attachment_paths):
    print("メールを送信しています...")
    msg = MIMEMultipart()
    msg['From'], msg['To'], msg['Subject'] = EMAIL_SENDER, EMAIL_RECEIVER, subject
    msg.attach(MIMEText(body, 'plain'))
    for path in attachment_paths:
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as f:
            file_data = f.read()
            if ext == '.png':
                from email.mime.image import MIMEImage
                part = MIMEImage(file_data, name=os.path.basename(path))
            elif ext == '.mp3':
                from email.mime.audio import MIMEAudio
                part = MIMEAudio(file_data, _subtype='mpeg')
            else:
                part = MIMEApplication(file_data, Name=os.path.basename(path))
            part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(path))
            msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

def main():
    try:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 0. 履歴の読み込み
        history = []
        if DRIVE_FOLDER_ID:
            history = load_history(DRIVE_FOLDER_ID)
            
        # 1. ニュース収集
        articles = fetch_latest_news(history)
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
        mp3_path = os.path.join(TARGET_DIR, f"{date_str}.mp3")

        with open(md_ideas_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(outputs.get('ideas_summary', ''), ensure_ascii=False, indent=2))
        with open(md_report_path, "w", encoding="utf-8") as f:
            f.write(outputs.get('daily_report', ''))
            
        generate_header_image(date_str, header_path)
        generate_audio(outputs.get('audio_script', ''), mp3_path)
            
        # 4. 履歴の更新と保存（重複排除のため）
        if DRIVE_FOLDER_ID:
            try:
                new_titles = [a['title'] for a in articles]
                history.extend(new_titles)
                save_history(DRIVE_FOLDER_ID, history)
            except Exception as e:
                print(f"[警告] 履歴の保存に失敗しましたが継続します: {e}")
        
        # 5. メール送信
        send_email(f"【日刊】{outputs.get('article_title', date_str)} - {date_str}", "本日のレポートを添付します。", [md_ideas_path, md_report_path, header_path, mp3_path])
        print("すべての工程が正常に終了しました。")
    except Exception as e:
        print(f"致命的エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
