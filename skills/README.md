# エージェントスキル一覧

このディレクトリは、AIアシスタント（エージェント）が利用可能なスキルや自動化ツールを管理する場所です。
「システム標準スキル」と「自作カスタムスキル」の2種類があります。

## 🛠️ 自作カスタムスキル (Custom Skills)

プロジェクト固有の自動化ツールです。

- **[ネタ収集ツール (neta_gatherer)](./neta_gatherer/)**
    - 役割: リテールニュースのRSSを収集し、Geminiでレポートを作成・メール送信する。
    - メインファイル: `neta_gatherer.py`
    - 保存先: `content/reports/`, `assets/headers/`

- **[画像処理ツール (image_tools)](./image_tools/)**
    - 役割: note投稿用に画像をリサイズ・圧縮する（HEIC対応）。
    - メインファイル: `resize_images.py`
    - 入出力: `assets/raw/` -> `assets/headers/`

---

## ⚙️ システム標準スキル (System Skills)

エージェントの基本機能を拡張するためのスキルです。
※ 動作保証のため、実体は隠しフォルダ `.agents/skills/` に配置されています。

- **firebase-basics**
    - Firebase製品（Firestore, Auth等）の操作ガイド。
- **gemini-api**
    - Google Gen AI SDK を用いた Gemini API の高度な利用ガイド。
- **google-cloud-waf-security**
    - Google Cloud のセキュリティ設計・WAF設定ガイド。

---

## 📂 関連ディレクトリ
- **[content/](../content/)**: 生成されたレポートや記事の原稿
- **[assets/](../assets/)**: 画像や資料などの素材
- **[config/](../config/)**: 各種設定ファイル・認証キー
