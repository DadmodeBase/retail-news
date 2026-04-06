---
title: "部下の単純作業を「アイコン1つ」に変えた話——15分で作れる自動化ツール（コピペOK）"
date: 2026-01-24
tags: [業務効率化 自動化ツール AI活用 Python 現場DX マネジメント]
category: AI活用事例
---

## 「また同じ作業か」と思ったときに考えたこと

画像をリサイズする。ただそれだけのことに、チームが毎週何時間も費やしている。

スマホで撮った写真は重い。報告書に貼ると開けなくなる。だから1枚ずつ手作業で縮小している。

「これ、自動化できないかな」——ずっとそう思っていました。

でも、部下に「新しいツールを覚えて」とは言いたくない。現場は日々の業務で手一杯だからです。

そこで選んだのが、**自分で仕組みを作って、部下にはアイコンを渡すだけ**という方法でした。
今回は、その具体的なやり方をご紹介します。

---

## マネージャーの仕事は「翻訳」して渡すこと

結論から言います。現場には「Python」という言葉を出さない方がスムーズです。

私たちマネージャーがやるべきは、AIという優秀なエンジニアを使って、「高度な技術」を「部下が慣れ親しんだ形」に翻訳して渡すことです。

具体的には、「バッチファイル（.bat）」を使います。
部下から見れば、それはただの「新しいアイコン」です。
**「このアイコンをダブルクリックすれば、仕事が終わるよ」**
これなら、説明書すら要りません。

実際に、私が現場の「画像リサイズ作業」を自動化したときの手順を公開します。
15分もあれば作れます。ぜひこのままコピペして試してみてください。

---

## 【実践】15分で作る「画像自動リサイズ係」

やることは2つだけです。
1. **Pythonスクリプト**（本体）を作る
2. **バッチファイル**（起動スイッチ）を作る

※前提として、あなたのPCにはPythonがインストールされている必要があります。（[こちらの手順](https://www.python.jp/install/windows/install.html)を参考にしてください）

### Step 1: AIに「本体」を書かせる

まずは、画像を縮小するプログラム本体を作ります。
自分で書く必要はありません。AI（ChatGPTやGemini）にこう投げるだけです。

> **プロンプト例**：
> 「フォルダ内にある画像（JPG、PNG、iPhoneのHEIC）を、長辺800pxにリサイズして、ファイルサイズが500KB以下のJPGに変換して保存するPythonコードを書いてください」

すると、以下のようなコードが返ってきます。これをメモ帳に貼り付け、`resize_images.py` という名前で保存してください。

**ポイント**：このコードは**iPhoneで撮った写真（HEIC形式）やPNG**にも対応しています。スマホから送られてくる画像形式を気にせず、すべて軽量なJPGに統一できます。

```python
# resize_images.py
from PIL import Image
import os
import glob
import io

# HEIC対応（iPhoneの標準形式）
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    print("HEIC形式に対応しています。")
except ImportError:
    print("※ HEIC形式には対応していません（pillow-heifをインストールしてください）")

# 設定（ここを変えれば調整できます）
MAX_SIZE = 800           # 長辺の最大ピクセル数
TARGET_KB = 500          # 目標ファイルサイズ（KB）
INPUT_DIR = "target_images"
OUTPUT_DIR = "resized_images"

# 対応する拡張子
EXTENSIONS = ["*.jpg", "*.jpeg", "*.png", "*.heic", "*.HEIC", "*.JPG", "*.JPEG", "*.PNG"]

def compress_to_target(img, target_kb, min_quality=20):
    """画像を目標サイズ以下になるまで圧縮する"""
    quality = 95
    while quality >= min_quality:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        size_kb = buffer.tell() / 1024
        if size_kb <= target_kb:
            return buffer.getvalue(), quality, size_kb
        quality -= 5
    # 最低品質でも目標に届かない場合はそのまま返す
    return buffer.getvalue(), quality, size_kb

# フォルダ作成
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 画像をリストアップ（複数の拡張子に対応）
files = []
for ext in EXTENSIONS:
    files.extend(glob.glob(os.path.join(INPUT_DIR, ext)))

print(f"{len(files)}枚の画像が見つかりました。処理を開始します...")

# 1枚ずつ処理
for file_path in files:
    try:
        img = Image.open(file_path)
        # RGB変換（透過画像・HEIC対策）
        if img.mode in ("RGBA", "P", "LA") or img.mode != "RGB":
            img = img.convert("RGB")
        # アスペクト比を維持してリサイズ
        img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
        
        # 圧縮して保存（出力は全てJPG）
        data, final_quality, final_kb = compress_to_target(img, TARGET_KB)
        
        # ファイル名を.jpgに変更して保存
        basename = os.path.splitext(os.path.basename(file_path))[0] + ".jpg"
        save_path = os.path.join(OUTPUT_DIR, basename)
        with open(save_path, "wb") as f:
            f.write(data)
        print(f"完了: {basename} ({final_kb:.0f}KB, 品質{final_quality})")
    except Exception as e:
        print(f"エラー: {file_path} - {e}")

print("全ての処理が完了しました！")
```

### Step 2: AIに「スイッチ」を作らせる（ここが重要！）

ここが最大のポイントです。
先ほどのPythonファイルを部下に渡しても、「どうやって実行するんですか？」と聞かれて終わりです。
そこで、ダブルクリックだけで起動する「スイッチ」を作ります。

これもAIに頼みます。

> **プロンプト例**：
> 「このPythonスクリプトを、ダブルクリックだけで実行できるWindowsのバッチファイル（.bat）の内容を教えて」

返ってくるのはこれだけです。これもメモ帳に貼り付け、`Double_Click_Me.bat` という名前で保存してください。

```batch
@echo off
echo 画像リサイズツールを起動します...
python resize_images.py
echo.
echo 処理が完了しました。何かキーを押すと終了します。
pause
```

### Step 3: 部下に渡す

あとは、この2つのファイルと、画像を入れるためのフォルダ（`target_images`）をセットにして、部下に渡すだけです。

「このフォルダに画像を放り込んで、『Double_Click_Me』を押してみて」

これだけです。
これなら、「新しいソフトの使い方」を教える必要はありません。
部下にとっては、「フォルダにファイルを入れてクリックする」という、**いつもの業務の延長**でしかないからです。

**【注意】相手のPCにもPythonが必要です**

このツールを部下のPCで使うには、そのPCにも**Pythonと必要なライブラリ**がインストールされている必要があります。
ITリテラシーが高いメンバーであれば問題ありませんが、そうでない場合は「Pythonって何？」で止まってしまうかもしれません。

その場合は、**EXE化（実行ファイル化）**という方法があります。Pythonスクリプトを`.exe`ファイルに変換すれば、相手のPCにPythonがなくてもダブルクリックだけで動きます。こちらは次の記事で詳しく解説しますので、ぜひ続けてお読みください。

---

## 現場は「技術」ではなく「楽」を求めている

このツールを導入したとき、部下から「Pythonすごいですね！」とは言われませんでした。
代わりに言われたのは、**「うわ、もう終わった！楽！」** という言葉です。

これでいいのです。
現場にとって、裏側で動いているものがPythonであれ、VBAであれ、関係ありません。
それがAIだったとしても同じです。
重要なのは、「今の苦労がなくなるかどうか」だけ。

私たちマネージャーがAIリテラシーを高める本当の理由は、高度な分析をするためだけではありません。
複雑な技術を、**最もシンプルな形（アイコン1つ）に翻訳して、部下にプレゼントするため**です。

もしあなたの周りに、単純作業で疲弊している部下がいたら、ぜひこの週末、こっそり「自分専用ツール」を作ってみてください。
月曜日の朝、「ちょっとこれ押してみて」と言うのが楽しみになるはずです。
