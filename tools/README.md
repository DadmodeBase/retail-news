# 🛠️ 自作自動化ツール一覧 (Tools)

このディレクトリは、**人間やスクリプトが直接実行するPython自動化ツール**を管理する場所です。

> [!NOTE]
> AI（エージェント）が直接認識して自動実行するスキル（軍配、image-anonymizer等）は、システム側の [`.agents/skills/`](../.agents/skills/) に配置されています。

---

## 📂 収録ツール一覧

### 1. [画像処理ツール (image_tools)](./image_tools/)
- **役割**: note投稿用などに画像をリサイズ・圧縮・最適化するツール（iPhoneのHEIC形式にも対応）。
- **使い方**: 
  - `assets/raw/` に画像を置く
  - `Double_Click_Me.bat` をダブルクリック（または `python resize_images.py` を実行）
  - リサイズされた画像が `assets/headers/` に出力されます。

### 2. [ネタ収集ツール (neta_gatherer)](./neta_gatherer/)
- **役割**: PR TIMESやリテールニュースのRSSを自動巡回し、Geminiで要約レポートを作成・メール送信・note下書き作成を行うプログラム。
- **メインファイル**: `neta_gatherer.py` / `note_publisher.py`
- **保存先**: `content/reports/`, `assets/headers/`

---

## 📂 関連ディレクトリ
- **[inbox/](../inbox/)**: ユーザーからのファイル受取場所（画像・資料・メモ等）
- **[content/](../content/)**: 生成されたレポートや記事の原稿
- **[assets/](../assets/)**: 画像や資料などの素材
- **[config/](../config/)**: 各種設定ファイル・認証キー
- **[.agents/skills/](../.agents/skills/)**: AIエージェント用の組み込みスキル群
