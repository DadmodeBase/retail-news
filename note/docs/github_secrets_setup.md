# GitHub Secrets 設定マニュアル

GitHub Actionsで「リテールニュース自動生成」を動かすために、以下の8つの項目をGitHubリポジトリの **Settings > Secrets and variables > Actions** から 「New repository secret」として登録してください。

## 1. 認証・APIキー関連

| Secret名 | 内容 | 取得方法 |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Gemini APIキー | [Google AI Studio](https://aistudio.google.com/) から取得 |
| `GCP_SERVICE_ACCOUNT_JSON` | Google Cloud サービスアカウントのJSON | Google Cloud Consoleで作成したサービスアカウントの「キー（JSON）」の内容をすべてコピー＆ペースト |

## 2. Google Drive 連携 (重要)

GitHub上ではブラウザ認証ができないため、ローカルで生成された認証情報を渡す必要があります。

| Secret名 | 内容 | 取得方法 |
| :--- | :--- | :--- |
| `GOOGLE_CREDENTIALS_JSON` | `credentials.json` の中身 | PCにある `credentials.json` をテキストエディタで開き、中身をすべてコピー |
| `GOOGLE_TOKEN_JSON` | `token.json` の中身 | **一度PCでスクリプトを実行し、正常に終了した後に生成される** `token.json` の中身をコピー |
| `GOOGLE_DRIVE_FOLDER_ID` | 保存先フォルダのID | ブラウザでGoogle Driveのフォルダを開いた際のURL末尾（`folders/XXXXX` のXXXXX部分） |

> [!IMPORTANT]
> `GOOGLE_TOKEN_JSON` は、PCで一度実行して認証を済ませた後に「自分自身のトークン」として生成されるものです。これがないとGitHub上で「ブラウザを開いてください」というエラーで止まってしまいます。

## 3. メール通知関連

| Secret名 | 内容 | 備考 |
| :--- | :--- | :--- |
| `EMAIL_SENDER` | 送信元Gmailアドレス | 例: `your-name@gmail.com` |
| `EMAIL_PASSWORD` | Gmailアプリパスワード | Googleアカウント設定の「2段階認証 > アプリパスワード」から生成した16桁のコード |
| `EMAIL_RECEIVER` | 送信送先アドレス | 自分がレポートを受け取りたいアドレス |

## 設定後の流れ
1. これらのSecretsをすべて登録します。
2. GitHubの **Actions** タブを開きます。
3. 左側の **Daily Retail News Report** を選択します。
4. **Run workflow** ボタンを押して、手動でテスト実行してみてください。
5. 成功すれば、翌朝からJST 07:00に自動でレポートが届くようになります！
