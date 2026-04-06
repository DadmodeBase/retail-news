---
name: Download Wikimedia Image
description: Search and download license-free images from Wikimedia Commons using a robust Python script.
---
# Wikimedia 画像ダウンロードスキル

Wikimedia Commons などのライセンスフリー（パブリックドメインやCCライセンス）の画像を検索・ダウンロードする際に、私が確実に実行するための手順・スクリプトです。

Wikipedia / Wikimedia のAPIやサーバーは、`User-Agent`（ブラウザの識別情報）が設定されていない機械的なリクエスト（Pythonのデフォルトなど）を「403 Forbidden」で弾く仕様になっています。また、環境によっては `requests` モジュールが未導入の場合があるため、**Pythonの標準ライブラリである `urllib` を使い、必ず `User-Agent` を明記したスクリプトを実行**します。

---

## 実行するPythonプログラムのテンプレート

以下のスクリプトを `run_command` で実行します。
`[検索対象のファイル名]` と `[保存先ローカルパス]` を書き換えて使います。

```python
python -c "
import urllib.request
import json
import os

# 1. 画像のURL情報をAPIから取得する
# 例: Wendy%27s%20flagship%20restaurant%20(Dublin,%20Ohio).jpg
target_filename = 'File:[検索対象のファイル名]'
url = f'https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url&titles={target_filename}'

# ★ APIへのリクエストにUser-Agentを付与
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        pages = data['query']['pages']
        page = list(pages.values())[0]
        
        if 'imageinfo' not in page:
            print('エラー: 画像が見つかりません。')
            exit(1)
            
        img_url = page['imageinfo'][0]['url']
        print('ダウンロード開始:', img_url)

        # 2. 実際の画像をダウンロードする
        # ★ 画像用のリクエストにも必ずUser-Agentを付与する
        req2 = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req2) as resp_img:
            img_data = resp_img.read()
            out_path = r'[保存先ローカルパス]'
            
            # 保存先フォルダが存在しない場合は作成
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            
            with open(out_path, 'wb') as f:
                f.write(img_data)
            print('正常に保存されました:', out_path)

except Exception as e:
    print('エラーが発生しました:', e)
"
```

## 重要ポイント（私自身への注意点）
*   必ず `urllib.request.Request(..., headers={'User-Agent': 'Mozilla/5.0'})` の形式で、User-Agentを偽装・付与すること。これを忘れると必ず失敗する。
*   `requests` などのサードパーティ製ライブラリは `ModuleNotFoundError` を起こすリスクがあるため使わないこと。
*   検索キーワード（ファイル名）にスペースや特殊文字が含まれる場合は、確実にURLエンコード（ `%20` や `%27` など）しておくこと。
