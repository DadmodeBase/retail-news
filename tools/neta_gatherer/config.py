"""
config.py
neta_gatherer 全体で使う設定値・定数を一元管理するモジュール。
挙動を変えたいときは基本的にこのファイルだけを編集すればよい。
"""

import os
import datetime
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# パス・環境変数
# ---------------------------------------------------------------------------
JST = datetime.timezone(datetime.timedelta(hours=9))
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def find_file(filename, subdirs=("config", "note", "")):
    """PROJECT_ROOT 配下の複数ディレクトリからファイルを探す"""
    for sub in subdirs:
        path = os.path.join(PROJECT_ROOT, sub, filename)
        if os.path.exists(path):
            return path
    return os.path.join(PROJECT_ROOT, filename)


_env_path = find_file(".env")
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
IS_GITHUB_ACTIONS = bool(os.getenv("GITHUB_ACTIONS"))

REPORTS_DIR = os.path.join(PROJECT_ROOT, "content", "reports")
MAPPING_PATH = os.path.join(PROJECT_ROOT, "content", "docs", "retail_url_mapping.md")
PUBLISHED_DIR = os.path.join(PROJECT_ROOT, "content", "posts", "published")
HEADERS_DIR = os.path.join(PROJECT_ROOT, "assets", "headers")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
HISTORY_FILENAME = "processed_history.json"

# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
GEMINI_MODELS = [
    "gemini-3.8-flash",      # メイン
    "gemini-3.7-flash",      # サブ1
    "gemini-3.6-flash",      # サブ2
    "gemini-3.5-flash",      # サブ3
    "gemini-flash-latest",   # サブ4：常に最新安定版を指す公式エイリアス
]

# ---------------------------------------------------------------------------
# note
# ---------------------------------------------------------------------------
NOTE_USER = "cool_hyena6987"
NOTE_RSS_URL = f"https://note.com/{NOTE_USER}/rss"
NOTE_COOKIE_PATH = os.path.join(PROJECT_ROOT, "config", "note_cookies.json")

# 追加先マガジン（名前は画面上の照合用、キーは公開後の検証用）
NOTE_MAGAZINE_NAME = "日刊リテールニュース & 流通トレンド分析"
NOTE_MAGAZINE_KEY = "mc924a8f6067c"

# ハッシュタグ設定（最大7個）
NOTE_TAG_LIMIT = 7
NOTE_MUST_TAGS = ["フィールドマーケティング"]

# 記事関連キーワード候補（本文・タイトルに出現するものを優先して抽出）
NOTE_RELEVANT_KEYWORDS = [
    # 業態・業種
    "ドラッグストア", "調剤薬局", "スーパー", "コンビニ", "ホームセンター",
    "百貨店", "外食", "EC", "ネットスーパー",
    # テーマ・業務
    "物流", "サプライチェーン", "ラストワンマイル", "配送",
    "DX", "リテールDX", "マーケティング", "リテール", "小売",
    "販促", "VMD", "売場", "棚割", "接客",
    "OMO", "リテールメディア", "決済", "コード決済", "POS",
    "フードロス", "食品ロス", "PB", "オムニチャネル",
]

# 記事からキーワードが不足した場合のフォールバック候補
NOTE_FALLBACK_TAGS = ["リテール", "DX", "小売", "マーケティング", "店舗", "流通"]
NOTE_BASE_TAGS = NOTE_FALLBACK_TAGS  # 互換性保持用

# ---------------------------------------------------------------------------
# ニュースソース
# ---------------------------------------------------------------------------
FEED_RYUTSUU = "https://www.ryutsuu.biz/feed"
FEED_DIAMOND = "https://diamond-rm.net/feed/"
FEED_LNEWS = "https://lnews.jp/feed"
FEED_PRTIMES = "https://prtimes.jp/index.rdf"

ALL_FALLBACK_FEEDS = [FEED_RYUTSUU, FEED_DIAMOND, FEED_LNEWS, FEED_PRTIMES]

# 曜日別ソース設定（0=月 ... 5=土。日曜は週間まとめ）
#   (フィード一覧, 対象日数)
FEEDS_BY_WEEKDAY = {
    0: ([FEED_LNEWS, FEED_DIAMOND, FEED_RYUTSUU], 3),   # 月曜は週末分も含める
    1: ([FEED_RYUTSUU, FEED_DIAMOND, FEED_LNEWS, FEED_PRTIMES], 1),
    2: ([FEED_RYUTSUU, FEED_LNEWS, FEED_DIAMOND], 1),
    3: ([FEED_RYUTSUU, FEED_LNEWS, FEED_DIAMOND], 1),
    4: ([FEED_LNEWS, FEED_DIAMOND, FEED_RYUTSUU], 1),
    5: ([FEED_RYUTSUU, FEED_DIAMOND, FEED_LNEWS, FEED_PRTIMES], 1),
}
MAX_ARTICLES_PER_FEED = 10

# PR TIMES のみ、以下のキーワードを含む記事に絞り込む
PRTIMES_KEYWORDS = [
    "リテール", "小売", "店舗", "流通", "EC", "コンビニ", "スーパー",
    "ドラッグストア", "DgS", "薬局", "調剤", "調剤併設", "セルフメディケーション", "電子処方箋",
    "ウエルシア", "ウエルシア薬局", "イオンハピコム",
    "ツルハ", "ツルハドラッグ", "くすりの福太郎", "レデイ薬局", "杏林堂", "B&D",
    "マツキヨ", "マツモトキヨシ", "ココカラファイン", "ココカラ",
    "コスモス", "ディスカウントドラッグコスモス", "コスモス薬品",
    "サンドラッグ", "ダイレックス",
    "スギ薬局", "スギホールディングス", "スギドラッグ", "ジャパン",
    "クスリのアオキ",
    "カワチ薬品", "カワチ",
    "クリエイトSD", "クリエイト",
    "薬王堂",
    "ゲンキー", "GENKY",
    "V・ドラッグ", "ブードラッグ", "中部薬品", "バロー",
    "キリン堂",
    "サツドラ", "サッポロドラッグストアー",
    "セキ薬品", "ドラッグストアセキ",
    "マーケティング", "DX", "OMO", "POS", "決済",
    "買い物", "販促", "棚", "売場", "売り場", "接客", "無人",
    "セルフレジ", "デジタルサイネージ", "フードロス", "食品ロス",
    "ネットスーパー", "物流", "ラストワンマイル", "配送",
]

# イベント・セミナー・PR案内等の除外キーワード（全フィード・タイトル+概要が対象）
EXCLUDE_KEYWORDS = [
    "セミナー", "ウェビナー", "WEBINAR", "オンラインセミナー", "無料セミナー",
    "開催", "参加者募集", "受講生", "受講者", "登壇", "カンファレンス", "フォーラム",
    "説明会", "内覧会", "展示会", "出展", "マルシェ", "ワークショップ",
    "体験イベント", "フェス", "フェスティバル", "相談会", "交流会", "シンポジウム",
    "【PR】", "［PR］", "[PR]", "プレゼントキャンペーン", "トークショー",
    "受講募集", "出展社募集", "記念イベント", "記念セミナー",
]

# 除外するURLパス（全フィード対象）
#   流通ニュースの /store/ は「出店・新設・開店」情報のカテゴリ
EXCLUDE_URL_PATTERNS = [
    "/seminar/", "/event/", "/webinar/",
    "ryutsuu.biz/store/",
]

# ---------------------------------------------------------------------------
# 新規出店・オープン記事の除外（タイトル判定）
#   旗艦店・新業態も含め、店舗の開店系ニュースは一律で除外する。
# ---------------------------------------------------------------------------
# タイトルにこれが含まれていれば無条件で除外
STORE_OPENING_WORDS = [
    "オープン", "OPEN", "開店", "出店", "新店", "号店", "開業",
    "グランドオープン", "リニューアルオープン", "プレオープン",
]
# 「オープン」を含んでも出店ではない語（誤除外を防ぐ）
STORE_OPENING_IGNORE = [
    "オープンイノベーション", "オープンAPI", "オープンソース", "オープンデータ",
    "オープン化", "オープンプラットフォーム", "オープンハウス", "オープンポジション",
    "OPENAI", "オープンAI", "OPEN API", "OPENSOURCE",
]
# 「新設」「開設」などは物流センター等にも使うため、店舗系の語と同時に出たときだけ除外
STORE_CONTEXT_WORDS = [
    "店", "ストア", "ショップ", "SC", "ショッピングセンター", "モール",
    "薬局", "売場", "売り場", "大型店", "大店",
]
STORE_CONTEXT_OPENING_WORDS = ["新設", "開設", "届出", "届け出", "移転"]
