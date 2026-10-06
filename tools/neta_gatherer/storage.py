"""
storage.py
処理済み履歴（Google Drive）、note記事の同期、Gitへの保存、メール送信を扱うモジュール。
"""

import datetime
import io
import json
import os
import random
import re
import shutil
import smtplib
import subprocess
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import feedparser

import config

# ---------------------------------------------------------------------------
# Google Drive（処理済み記事タイトルの履歴）
# ---------------------------------------------------------------------------
_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    token_path = config.find_file("token.json")
    token_json = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json:
        try:
            creds = Credentials.from_authorized_user_info(json.loads(token_json), _SCOPES)
        except Exception as e:
            print(f"[警告] GOOGLE_TOKEN_JSON の解析に失敗しました: {e}")
    elif os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, _SCOPES)

    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if config.IS_GITHUB_ACTIONS:
            raise RuntimeError("Google Drive の認証情報が無効です（GOOGLE_TOKEN_JSON を更新してください）")
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        cred_path = config.find_file("credentials.json")
        if creds_json:
            flow = InstalledAppFlow.from_client_config(json.loads(creds_json), _SCOPES)
        elif os.path.exists(cred_path):
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, _SCOPES)
        else:
            raise RuntimeError("Google Drive の認証情報が見つかりません")
        creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def load_history(service):
    from googleapiclient.http import MediaIoBaseDownload
    print("過去の記事履歴を読み込んでいます...")
    try:
        q = f"name = '{config.HISTORY_FILENAME}' and '{config.DRIVE_FOLDER_ID}' in parents and trashed = false"
        files = service.files().list(q=q, fields="files(id, name)").execute().get("files", [])
        if not files:
            return [], None
        file_id = files[0]["id"]
        fh = io.BytesIO()
        dl = MediaIoBaseDownload(fh, service.files().get_media(fileId=file_id))
        done = False
        while not done:
            _, done = dl.next_chunk()
        return json.loads(fh.getvalue().decode("utf-8")), file_id
    except Exception as e:
        print(f"[警告] 履歴の読み込みに失敗しました: {e}")
        return [], None


def save_history(service, history, file_id):
    from googleapiclient.http import MediaIoBaseUpload
    try:
        fh = io.BytesIO(json.dumps(history[-500:], ensure_ascii=False).encode("utf-8"))
        media = MediaIoBaseUpload(fh, mimetype="application/json", resumable=True)
        if file_id:
            service.files().update(fileId=file_id, media_body=media).execute()
        else:
            body = {"name": config.HISTORY_FILENAME, "parents": [config.DRIVE_FOLDER_ID]}
            service.files().create(body=body, media_body=media).execute()
    except Exception as e:
        print(f"[警告] 履歴の保存に失敗しました: {e}")


# ---------------------------------------------------------------------------
# Git（GitHub Actions 上でのみ実行）
# ---------------------------------------------------------------------------
def git_pull():
    if config.IS_GITHUB_ACTIONS:
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False, capture_output=True)


def git_commit_and_push(paths, message):
    if not config.IS_GITHUB_ACTIONS:
        return
    try:
        subprocess.run(["git", "config", "--local", "user.email", "actions@github.com"], check=True)
        subprocess.run(["git", "config", "--local", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "add", *paths], check=False)
        if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
            print("コミット対象の変更がないためスキップしました。")
            return
        subprocess.run(["git", "commit", "-m", f"{message} [skip ci]"], check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)
        subprocess.run(["git", "push"], check=True)
        print(f"Gitへ保存しました: {message}")
    except Exception as e:
        print(f"[警告] Gitへの保存に失敗しました: {e}")


# ---------------------------------------------------------------------------
# note RSS → retail_url_mapping.md 同期（X投稿の過去記事紹介用）
# ---------------------------------------------------------------------------
def sync_note_articles():
    print("note RSSから最新記事を同期しています...")
    if not os.path.exists(config.MAPPING_PATH):
        print("[警告] retail_url_mapping.md が見つからないため同期をスキップします。")
        return
    os.makedirs(config.PUBLISHED_DIR, exist_ok=True)

    registered = set()
    with open(config.MAPPING_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("|") and "note.com" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:
                    registered.add(parts[3])

    try:
        feed = feedparser.parse(config.NOTE_RSS_URL)
        prefix = f"https://note.com/{config.NOTE_USER}"
        new_entries = [e for e in feed.entries if e.link.startswith(prefix) and e.link not in registered]
        if not new_entries:
            return
        with open(config.MAPPING_PATH, "a", encoding="utf-8") as f:
            for entry in reversed(new_entries):
                m = re.search(r"/n/(n[a-z0-9]+)", entry.link)
                note_id = m.group(1) if m else f"gen_{random.randint(1000, 9999)}"
                t = entry.get("published_parsed") or entry.get("updated_parsed")
                try:
                    d = datetime.datetime(*t[:6], tzinfo=datetime.timezone.utc).astimezone(config.JST)
                except Exception:
                    d = datetime.datetime.now(config.JST)
                filename = f"{d.strftime('%Y-%m-%d')}-note_imported_{note_id}.md"
                f.write(f"| `{filename}` | {entry.title} | {entry.link} |\n")
                path = os.path.join(config.PUBLISHED_DIR, filename)
                if not os.path.exists(path):
                    summary = re.sub(r"<[^>]*>", "", entry.get("summary", ""))[:1000]
                    with open(path, "w", encoding="utf-8") as pf:
                        pf.write(f"# {entry.title}\n\n{summary}\n")
                print(f"  同期: {entry.title}")
        git_commit_and_push(["content/docs/retail_url_mapping.md", "content/posts/published/"],
                            "auto: sync new note articles from RSS")
    except Exception as e:
        print(f"[警告] note記事の同期中にエラーが発生しました: {e}")


# ---------------------------------------------------------------------------
# ヘッダー画像・メール
# ---------------------------------------------------------------------------
def prepare_header_image(date_str, output_path):
    """assets/headers/MM-DD.png（なければ YYYY-MM-DD-header.png）をコピーする"""
    candidates = [
        os.path.join(config.HEADERS_DIR, f"{date_str[5:10]}.png"),
        os.path.join(config.HEADERS_DIR, f"{date_str}-header.png"),
    ]
    for src in candidates:
        if os.path.exists(src):
            if os.path.abspath(src) != os.path.abspath(output_path):
                shutil.copy(src, output_path)
            return output_path
    return None


def send_email(subject, body, attachment_paths, timeout=30):
    print("メールを送信しています...")
    msg = MIMEMultipart()
    msg["From"] = config.EMAIL_SENDER
    msg["To"] = config.EMAIL_RECEIVER
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(body, "plain", "utf-8"))
    for path in attachment_paths:
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(path))
            part.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
            msg.attach(part)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=timeout) as server:
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.send_message(msg)
        print("[OK] メール送信が完了しました。")
    except Exception as e:
        print(f"[エラー] メール送信に失敗しました: {e}")
        raise
