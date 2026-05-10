import os
import json
import datetime
import requests
import feedparser
import re
import google.generativeai as genai
from google.cloud import texttospeech
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# .envファイルの読み込み
load_dotenv()

# 設定の取得
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

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
        print(f"❌ 警告: 以下の環境変数が設定されていません: {', '.join(missing)}")
    else:
        print("✅ 基礎的な環境変数の読み込みを確認しました。")

validate_env()

# 定数
TARGET_DIR = os.path.join(os.path.dirname(__file__), "..", "ideas")
os.makedirs(TARGET_DIR, exist_ok=True)
RSS_FEEDS = [
    "https://lnews.jp/feed",
    "https://www.ryutsuu.biz/feed",
    "https://prtimes.jp/main/html/searchrlp/kw/%E3%83%AA%E3%83%86%E3%83%BC%E3%83%ABDX"
]

# --- クラウド実行（GitHub Actions）用の認証設定 ---
def setup_cloud_auth():
    """環境変数から認証ファイルを一時的に復元する"""
    # Cloud TTS用のサービスアカウントJSON
    gcp_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if gcp_json:
        gcp_key_path = os.path.join(TARGET_DIR, "gcp_key.json")
        with open(gcp_key_path, "w", encoding="utf-8") as f:
            f.write(gcp_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcp_key_path
        print("Cloud TTS credentials successfully loaded from environment variable.")

setup_cloud_auth()


def fetch_latest_news():
    print("ニュースを収集しています...")
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get("summary", ""),
                })
        except Exception as e:
            print(f"警告: {url} の取得に失敗しました: {e}")
    return articles

def clean_text_for_tts(text):
    # Markdown記号の削除
    text = re.sub(r'#+\s*', '', text)  # 見出し記号
    text = re.sub(r'\*+', '', text)    # 太字・斜体記号
    text = re.sub(r'---+', '', text)   # 区切り線
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text) # リンク
    text = re.sub(r'-\s*', '', text)   # 箇条書き
    return text

def generate_contents(articles):
    print("Geminiでレポートと音声を生成しています...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
    
    context = "\n".join([f"- {a['title']}: {a['link']}" for a in articles])
    
    # プロンプトの構築（スキル `note_daily_news_curator` のエッセンスを反映）
    prompt = f"""
あなたはフィールドマーケティングの専門家です。以下の最新ニュースから3つのトピックスを選び、
デイリーレポートと音声読み上げ用原稿を作成してください。

【ニュースソース】
{context}

【アウトプット1：デイリーレポート (Markdown)】
以下の構成で作成してください。合計1,800文字程度のボリュームにします。
1. **内容の概要がわかる30文字程度のタイトル** (例: 「赤坂の新施設、ファミマにセブン銀行、山本山の新提案」のように、具体的なトピックを盛り込む)
2. **タイトル・日付**
3. **【全体概要】**: 3つのトピックを俯瞰した、今日の潮流を読み解く導入文。
4. **トピック別の詳細** (3セット):
    - トピックの見出し（## レベル）のみ使用する。
    - 各見出しの直後（本文の前）に、ソースとなったニュース記事のURLを「> 出典: [記事タイトル](URL)」の形式で必ず入れる。
    - セクション内には「1. ニュースの概要」「2. フィールドマーケティングの視点」のような小見出しは一切使わない。
    - ニュースの事実→専門家としての視点→消費者の心理推察を、一つの自然な文章として溶け込ませてコラムのように書く。

【文体ルール（重要）】
- です・ます調の対話体。「〜ですよね」「〜だと思います」のような柔らかい表現を使う。
- **句点（。）ごとに改行する。**
- 2〜3文ごとに空行を入れる。
- 1行は40〜60文字以内。
- 重要なインサイトは太字で強調する。マークダウンの仕様上、太字記号（`**`）の「外側」には半角スペースを入れ、「内側」には絶対に入れないこと（⭕️ `ここは **重要** です` / ❌ `ここは ** 重要 ** です` / ❌ `ここは**重要**です`）。
- 絵文字は使わない。

【禁止事項（AI的な表現の排除）】
以下のような表現は絶対に使わないでください。読者に「AIが書いた」と即座にバレます。
- NG: 気取った文学的表現・抽象的メタファー（「静かに、しかし確実に〜」「境界線の消失」「パラダイムシフト」「心の余白」「時代の潮流」「号砲」「〜という名の〜」「〜の足音が聞こえる」「〜を凌駕する」「〜が胎動している」）
- NG: 大げさな修飾・ドラマチックな演出（「革命的」「衝撃的」「歴史的転換点」「まさに〜と言えるでしょう」「〜の幕開けです」、ポエム調の短文の連打）
- OK: 目指すべきトーン（職場の先輩が昼休みに「こんなニュースあったんだけどさ」と話す感覚。具体的で地に足がついた言い回し。「要するに〜ってことですよね」のような噛み砕いた表現。事実と自分の意見の区別が明確。）

【アウトプット2：音声読み上げ用原稿 (Text)】
要約と「問いかけ」のみに絞った、耳で聞いて心地よい原稿にしてください。
「メタ情報（タイトルやURL、分析ポイント）」は含めないでください。

出力は以下のJSON形式でお願いします。
{{
  "article_title": "30文字程度の魅力的なタイトル",
  "daily_report": "Markdown形式のレポート全文",
  "audio_script": "読み上げ用テキスト",
  "ideas_summary": "NotebookLM用の構造化されたネタ帳（タイトル、URL、問いのみ）"
}}
"""
    response = model.generate_content(prompt)
    
    # JSON抽出（```json ... ``` の中身を取り出す）
    json_text = re.search(r'\{.*\}', response.text, re.DOTALL).group()
    import json
    data = json.loads(json_text)
    
    # 太字のマークダウンのスペースを強制修正 (LLMの揺れを防ぐ)
    if 'daily_report' in data:
        report = data['daily_report']
        # 一旦 ** 周辺のスペースを全て削除
        report = re.sub(r'\s*\*\*\s*', '**', report)
        # ペアになっている **...** の外側にだけスペースを付与
        report = re.sub(r'\*\*(.*?)\*\*', r' **\1** ', report)
        # 連続した半角スペースができていれば1つにまとめる
        report = re.sub(r' +', ' ', report)
        
        # 記事タイトルの挿入（最上部に # タイトル として配置）
        if 'article_title' in data:
            report = f"# {data['article_title']}\n\n" + report
            
        data['daily_report'] = report
        
    return data

def generate_audio(text, output_path):
    print("Google Cloud TTSで音声を生成しています...")
    client = texttospeech.TextToSpeechClient()
    clean_text = clean_text_for_tts(text)
    synthesis_input = texttospeech.SynthesisInput(text=clean_text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="ja-JP",
        name="ja-JP-Neural2-C"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    with open(output_path, "wb") as out:
        out.write(response.audio_content)

def generate_header_image(date_str, output_path):
    print(f"ヘッダー画像を生成しています: {output_path}")
    base_image_path = os.path.join(os.path.dirname(__file__), "..", "resources", "header_base.png")
    
    if os.path.exists(base_image_path):
        try:
            img = Image.open(base_image_path).convert("RGB")
            draw = ImageDraw.Draw(img)
            text_color_main = (0, 80, 150)
            text_color_date = (40, 60, 80)
            has_base = True
        except Exception as e:
            print(f"ベース画像の読み込みに失敗しました: {e}")
            has_base = False
    else:
        has_base = False
        
    if not has_base:
        # ベース画像がない場合は、高級感のあるグラデーション背景を作成
        img = Image.new('RGB', (1920, 1006))
        draw = ImageDraw.Draw(img)
        for y in range(1006):
            r = int(15 + (40 - 15) * (y / 1006))
            g = int(35 + (80 - 35) * (y / 1006))
            b = int(75 + (130 - 75) * (y / 1006))
            draw.line([(0, y), (1920, y)], fill=(r, g, b))
        text_color_main = (255, 255, 255)
        text_color_date = (200, 230, 255)
    
    # フォント設定（GitHub Actions等の日本語フォントが無い環境に対応するためダウンロードフォールバックを追加）
    font_main = None
    font_date = None
    font_paths = [
        "C:\\Windows\\Fonts\\meiryo.ttc",
        "C:\\Windows\\Fonts\\msgothic.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    ]
    
    # ローカルにフォントが無ければインターネットから取得
    if not any(os.path.exists(f) for f in font_paths):
        import urllib.request
        fallback_font_path = os.path.join(TARGET_DIR, "NotoSansJP-SemiBold.ttf")
        if not os.path.exists(fallback_font_path):
            try:
                print("日本語フォントが見つからないため、Noto Sans JPをダウンロードします...")
                # Noto Sans JP (Google Fonts)
                font_url = "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP-SemiBold.ttf"
                urllib.request.urlretrieve(font_url, fallback_font_path)
            except Exception as e:
                print(f"フォントのダウンロードに失敗しました: {e}")
        font_paths.insert(0, fallback_font_path)

    for p in font_paths:
        if os.path.exists(p):
            try:
                font_main = ImageFont.truetype(p, 120, index=0 if 'ttc' in p else 0) 
                font_date = ImageFont.truetype(p, 80, index=0 if 'ttc' in p else 0)
                print(f"フォントを適用しました: {p}")
                break
            except Exception as e:
                pass

    if font_main is None or font_date is None:
        font_main = ImageFont.load_default()
        font_date = ImageFont.load_default()
    
    # 日付の描画 (3月29日 など)
    try:
        parts = date_str.split("-")
        date_text = parts[-2].lstrip("0") + "月" + parts[-1].lstrip("0") + "日"
    except:
        date_text = date_str
        
    main_text = "日刊 リテールニュース"
    w, h = 1920, 1006
    
    try:
        # Pillowのバージョン差異に対応
        date_bbox = draw.textbbox((0, 0), date_text, font=font_date)
        draw.text(((w - (date_bbox[2] - date_bbox[0])) / 2, h/2 - 150), date_text, font=font_date, fill=text_color_date)
        
        main_bbox = draw.textbbox((0, 0), main_text, font=font_main)
        draw.text(((w - (main_bbox[2] - main_bbox[0])) / 2, h/2 - 20), main_text, font=font_main, fill=text_color_main)
        
        if not has_base:
            # グラデーションの場合はおしゃれなラインを引く
            line_y = h/2 + 150
            draw.line([(w/2 - 300, line_y), (w/2 + 300, line_y)], fill=(120, 160, 220), width=3)
    except Exception as e:
        # 古いPillowやフォント読み込み失敗時のフェイルセーフ
        draw.text((w/2 - 200, h/2 - 100), date_text, font=font_date, fill=text_color_date)
        draw.text((w/2 - 300, h/2), main_text, font=font_main, fill=text_color_main)
    
    img.save(output_path)

def get_drive_service():
    """Google Drive API サービスを取得。ローカルファイルと環境変数の両方に対応。"""
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), "..", "token.json")
    credentials_path = os.path.join(os.path.dirname(__file__), "..", "credentials.json")
    scopes = ["https://www.googleapis.com/auth/drive.file"]

    # 1. 環境変数からのトークン取得を優先（GitHub Actions環境）
    token_json = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json:
        try:
            creds_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(creds_data, scopes)
            print(f"✅ Googleトークンを環境変数から読み込みました。(Account: {creds_data.get('account', 'N/A')})")
        except Exception as e:
            print(f"❌ 警告: GOOGLE_TOKEN_JSON の解析に失敗しました: {e}")
    
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
                print(f"トークンの更新に失敗しました（有効期限切れなど）: {e}")
                creds = None
        else:
            # 環境変数またはファイルからcredentials情報を取得
            creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                client_config = json.loads(creds_json)
                flow = InstalledAppFlow.from_client_config(client_config, scopes)
            elif os.path.exists(credentials_path):
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            else:
                raise Exception("認証情報が見つかりません。GOOGLE_CREDENTIALS_JSON または credentials.json が必要です。")
            
            # GitHub Actions環境では新規に対話的認証はできない
            if os.getenv("GITHUB_ACTIONS") and not token_json:
                raise Exception("GitHub Actions環境では有効な GOOGLE_TOKEN_JSON が必須です。ローカルで取得した最新のトークンを登録してください。")
            
            print("ブラウザを開いて認証を行います...")
            creds = flow.run_local_server(port=0)
            
        # 次回のためにローカルに保存（ローカル実行時のみ）
        if not os.getenv("GITHUB_ACTIONS"):
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            
    return build("drive", "v3", credentials=creds)

def get_or_create_drive_folder(folder_name, parent_id):
    """指定された名前のフォルダを取得、なければ作成する"""
    service = get_drive_service()
    query = f"name = '{folder_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    
    if files:
        return files[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'parents': [parent_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def upload_to_drive(file_path, folder_id):
    print(f"Googleドライブへアップロードしています: {os.path.basename(file_path)}")
    try:
        service = get_drive_service()
        file_metadata = {
            "name": os.path.basename(file_path), 
            "parents": [folder_id]
        }
        # 拡張子によってMIMEタイプを切り替え
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.md':
            file_metadata["mimeType"] = "application/vnd.google-apps.document"
            mimetype = "text/markdown"
        elif ext == '.png':
            mimetype = "image/png"
        else:
            mimetype = None
            
        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        print(f"✅ ドライブへのアップロードが成功しました。")
    except Exception as e:
        print(f"ドライブへのアップロードに失敗しました: {e}")

def send_email(subject, body, attachment_paths):
    print("メールを送信しています...")
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
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
        
        # ファイルパス定義
        md_ideas_path = os.path.join(TARGET_DIR, f"{date_str}-ideas.md")
        md_report_path = os.path.join(TARGET_DIR, f"{date_str}-daily-report.md")
        mp3_path = os.path.join(TARGET_DIR, f"{date_str}.mp3")
        
        # 1. ニュース収集
        articles = fetch_latest_news()
        
        # 2. コンテンツ生成
        outputs = generate_contents(articles)
        
        # 3. ファイルの保存
        with open(md_ideas_path, "w", encoding="utf-8") as f:
            ideas = outputs.get('ideas_summary', '')
            f.write(ideas if isinstance(ideas, str) else json.dumps(ideas, ensure_ascii=False, indent=2))
        with open(md_report_path, "w", encoding="utf-8") as f:
            report = outputs.get('daily_report', '')
            f.write(report if isinstance(report, str) else "\n".join(report) if isinstance(report, list) else str(report))
            
        # 4. ヘッダー画像の生成
        header_path = os.path.join(TARGET_DIR, f"{date_str}-header.png")
        generate_header_image(date_str, header_path)
            
        # 5. Googleドライブへアップロード
        if DRIVE_FOLDER_ID:
            # 日付フォルダを取得または作成
            daily_folder_id = get_or_create_drive_folder(date_str, DRIVE_FOLDER_ID)
            
            upload_to_drive(md_ideas_path, daily_folder_id)
            upload_to_drive(md_report_path, daily_folder_id)
            upload_to_drive(header_path, daily_folder_id)
            
        # 6. 音声合成 (audio_scriptを使用)
        audio_script = outputs.get('audio_script', '')
        if isinstance(audio_script, list):
            audio_script = "\n".join(audio_script)
        elif not isinstance(audio_script, str):
            audio_script = str(audio_script)
        generate_audio(audio_script, mp3_path)
        
        # 7. メール送信
        subject_title = outputs.get('article_title', date_str)
        email_body = f"おはようございます。\n本日のリテールレポートとネタ帳、ヘッダー画像を作成しました。\n\n添付ファイル:\n- {date_str}-daily-report.md (note下書き)\n- {date_str}-ideas.md (NotebookLM用)\n- {date_str}-header.png (noteヘッダー)\n- {date_str}.mp3 (音声まとめ)"
        send_email(f"【日刊】{subject_title} - {date_str}", email_body, [md_ideas_path, md_report_path, header_path, mp3_path])
        
        print("すべての工程が正常に終了しました。")
    except Exception as e:
        import traceback
        import sys
        print(f"エラーが発生しました: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
