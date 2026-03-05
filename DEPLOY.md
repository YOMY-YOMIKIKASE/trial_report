# デプロイ・設定ガイド

## Render で公開する場合

### 1. 環境変数の設定（必須：Googleスプレッドシート連携）

Render ダッシュボードで対象の Web サービスを開き、左メニュー **「Environment」** をクリックします。

- **「+ Add Environment Variable」** で次の2つを追加してください。

| Key | Value |
|-----|--------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | サービスアカウントの JSON キーの中身を **そのまま** 貼り付け（`{` から `}` まで全体） |
| `CONFIG_SPREADSHEET_ID` | 設定用スプレッドシートの ID（URL の `/d/` と `/edit` の間の英数字） |

- 保存後、**「Save Changes」** または **「Manual Deploy」→「Clear build cache & deploy」** で再デプロイすると、  
  「Googleスプレッドシート連携が未設定です」の警告が消え、絵本・クルーの追加・削除がスプレッドシートに永続化されます。

### 2. Google 側の準備（初回のみ）

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成し、**Google Sheets API** と **Google Drive API** を有効化する。
2. **IAM と管理 → サービス アカウント** でサービスアカウントを作成し、**鍵を追加 → JSON** でキーをダウンロードする。
3. 設定用の **Google スプレッドシート** を1つ作成する。
   - シート（タブ）を **「books」** と **「crews」** の2つ用意する。
   - **books**: 1行目から A列=タイトル, B列=作者, C列=あらすじ, D列=画像URL（任意）
   - **crews**: 1行目から A列=名前, B列=写真URL, C列=好きな絵本
   - スプレッドシートを、サービスアカウントのメール（`xxx@xxx.iam.gserviceaccount.com`）に **編集者** で共有する。
4. スプレッドシートの URL から **スプレッドシート ID** をコピーし、Render の `CONFIG_SPREADSHEET_ID` に設定する。

---

## 絵本・クルーの登録項目

- **絵本**: タイトル（必須）、作者、あらすじ、画像URL（テンプレート用。未入力なら既存の Assets 画像を使用）
- **クルー**: 名前（必須）、写真URL、好きな絵本（一覧から選択）
