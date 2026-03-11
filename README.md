# 体験会コメントシートメーカー

YOMY! の体験会で使用するレポート（コメントシート）を簡単に生成できる Web アプリです。

**デプロイ先**: [Render](https://render.com)

---

## 機能

- 読んだ絵本・クルー情報をもとにコメントシート画像を自動生成
- 管理パネルから絵本・クルー情報を登録・編集
- 絵本・クルーのデータは Google スプレッドシートに保存（永続化）
- 画像はドラッグ＆ドロップでアップロード（Google Drive 経由）

---

## セットアップ

### 1. Google Cloud の準備

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. **Google Sheets API** と **Google Drive API** を有効化
3. サービスアカウントを作成し、JSON キーをダウンロード
4. 対象のスプレッドシートをサービスアカウントのメールアドレスと共有（編集者権限）

### 2. Google スプレッドシートの準備

スプレッドシートに以下の 2 つのシートを作成します。

**`books` シート**（1行目はヘッダー）

| title | author | summary | image_url |
|-------|--------|---------|-----------|

**`crews` シート**（1行目はヘッダー）

| name | photo_url | favorite_book | favorite_book_author |
|------|-----------|---------------|----------------------|

### 3. Render の環境変数設定

Render の **Environment** タブに以下を設定します。

| 変数名 | 内容 |
|--------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | サービスアカウント JSON キーの中身（全文をそのままペースト） |
| `CONFIG_SPREADSHEET_ID` | スプレッドシートの ID（URL の `/d/〜/edit` の `〜` 部分） |

---

## 使い方

### メイン画面

1. **クルーを選択** — 担当クルーを選ぶ
2. **絵本を選択** — 読んだ絵本をチェックボックスで選ぶ
3. **コメントを入力** — 各絵本へのコメントを入力
4. **シートを生成** — 画像を生成してダウンロード

### 管理パネル（サイドバーまたは画面下部から開く）

- **絵本の登録**: タイトル・作者・あらすじ・表紙画像をドラッグ＆ドロップで登録
- **クルーの登録**: 名前・顔写真・好きな絵本（タイトル・作者名）を登録
- 登録内容は Google スプレッドシートに自動保存

---

## 技術スタック

- [Streamlit](https://streamlit.io/)
- [Pillow](https://pillow.readthedocs.io/)
- [gspread](https://gspread.readthedocs.io/)
- Google Sheets API / Google Drive API
- [Render](https://render.com)（ホスティング）

---

## ローカル実行

```bash
pip install streamlit pillow gspread google-auth requests

# サービスアカウントのJSONをリポジトリ直下に配置
cp /path/to/your-service-account.json service_account.json

# 環境変数でスプレッドシートIDを指定
export CONFIG_SPREADSHEET_ID=your_spreadsheet_id

streamlit run script.py
```
